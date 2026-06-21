from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from typing import Any, cast

from grach.query_executor import (
    InvalidTraversalSemanticsError,
    QueryPlan,
    validate_query_plan,
)
from grach.schema import (
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    EntityType,
    RelationshipType,
    relationship_type_pairs,
)


class QueryPlannerError(ValueError):
    pass


class OpenAIQueryPlanner:
    def __init__(
        self,
        model: str | None = None,
        *,
        create_completion: Callable[..., Any] | None = None,
    ) -> None:
        if create_completion is None:
            from openai import OpenAI

            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("OPENAI_BASE_URL"),
            )
            create_completion = cast(Callable[..., Any], client.chat.completions.create)
        self._create_completion = create_completion
        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    def plan(self, question: str) -> QueryPlan:
        deterministic_plan = _database_users_plan(question)
        if deterministic_plan is not None:
            return deterministic_plan
        messages = [
            {"role": "system", "content": _instructions()},
            {"role": "user", "content": question},
        ]
        for attempt in range(2):
            content = self._request(messages)
            try:
                return _parse_plan(content)
            except InvalidTraversalSemanticsError as error:
                if attempt == 1:
                    raise
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": f"The plan is invalid: {error}. Return a corrected plan.",
                        },
                    ]
                )
        raise AssertionError("query planner retry loop exhausted")

    def _request(self, messages: list[dict[str, str]]) -> str:
        try:
            response = self._create_completion(
                model=self._model,
                messages=messages,
                response_format=_response_format(),
            )
        except Exception as error:
            raise QueryPlannerError(f"provider request failed: {error}") from error
        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise QueryPlannerError(f"provider refused to plan the query: {refusal}")
        content = message.content
        if not content:
            raise QueryPlannerError("OpenAI-compatible provider returned no message content")
        return content


def _database_users_plan(question: str) -> QueryPlan | None:
    match = re.fullmatch(
        r"\s*Which\s+service\s+uses\s+(?:the\s+)?(.+?\s+Database)\s*\??\s*",
        question,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return {
        "operation": "TRAVERSE",
        "anchor": {"name": match.group(1), "type": "Database"},
        "steps": [
            {
                "relationship": "USES_DATABASE",
                "direction": "incoming",
                "result_type": "Service",
            }
        ],
    }


def _parse_plan(content: str) -> QueryPlan:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise QueryPlannerError(f"provider returned invalid query-plan JSON: {error}") from error
    if not isinstance(data, dict) or set(data) != {"plan"}:
        raise QueryPlannerError("provider response must contain exactly one plan object")
    _canonicalize_anchor_type(data["plan"])
    return validate_query_plan(data["plan"])


def _canonicalize_anchor_type(plan: object) -> None:
    if not isinstance(plan, dict) or plan.get("operation") != "TRAVERSE":
        return
    anchor = plan.get("anchor")
    steps = plan.get("steps")
    if (
        not isinstance(anchor, dict)
        or "name" not in anchor
        or not isinstance(steps, list)
        or not steps
    ):
        return
    allowed_inputs = _first_step_input_types(steps[0])
    if len(allowed_inputs) == 1 and anchor.get("type") not in allowed_inputs:
        anchor["type"] = next(iter(allowed_inputs))


def _first_step_input_types(step: object) -> set[EntityType]:
    if not isinstance(step, dict):
        return set()
    relationship = step.get("relationship")
    direction = step.get("direction")
    if relationship not in RELATIONSHIP_TYPES or direction not in ("incoming", "outgoing"):
        return set()
    pairs = relationship_type_pairs(cast(RelationshipType, relationship))
    if direction == "incoming":
        pairs = frozenset((target, source) for source, target in pairs)
    result_type = step.get("result_type")
    return {source for source, target in pairs if result_type is None or target == result_type}


def _instructions() -> str:
    entities = ", ".join(sorted(ENTITY_TYPES))
    relationships = ", ".join(sorted(RELATIONSHIP_TYPES))
    return (
        "Translate the question into one bounded architecture query plan. Use ENTITY_SEARCH with "
        "one selector for questions that only identify an entity. Use TRAVERSE with one anchor and "
        "ordered relationship steps for relationship questions. Use UNSUPPORTED with a concise "
        "reason when the question cannot be expressed with the allowed graph vocabulary. Selectors "
        "use exactly one of id or name and may include type. Never answer the question or invent "
        'graph facts. "Who owns Order Service?" requires TRAVERSE from Order Service via outgoing '
        "OWNED_BY with Team as the result type. "
        '"Which service uses the Orders Database?" requires anchor '
        '{"name":"Orders Database","type":"Database"} and exactly one incoming USES_DATABASE '
        "step with Service as the result type. Use name selectors for names from the question; use "
        "id selectors only when the question supplies a canonical type:slug ID. Use the shortest "
        "traversal that directly answers the question; do not add unrelated relationships. "
        f"Allowed entity types: {entities}. Allowed relationships: {relationships}. "
        "Relationship direction is semantic: USES_DATABASE uses Service -> Database; OWNED_BY uses "
        "owned entity -> Team; CALLS uses caller -> callee; PUBLISHES and CONSUMES use Service -> "
        "Event; DEPLOYED_TO uses Service -> Infrastructure; EXPOSES uses Service -> API or API -> "
        "Endpoint; GENERATES uses Service -> Document; RECEIVES uses API -> Endpoint."
    )


def _response_format() -> dict[str, Any]:
    optional_entity_type = {
        "anyOf": [
            {"type": "string", "enum": sorted(ENTITY_TYPES)},
            {"type": "null"},
        ]
    }
    selector = {
        "anyOf": [
            {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": optional_entity_type,
                },
                "required": ["id", "type"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": optional_entity_type,
                },
                "required": ["name", "type"],
                "additionalProperties": False,
            },
        ]
    }
    step = {"anyOf": _step_schema_variants()}
    plan = {
        "anyOf": [
            {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["ENTITY_SEARCH"]},
                    "selector": selector,
                },
                "required": ["operation", "selector"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["TRAVERSE"]},
                    "anchor": selector,
                    "steps": {"type": "array", "items": step, "minItems": 1, "maxItems": 6},
                },
                "required": ["operation", "anchor", "steps"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["UNSUPPORTED"]},
                    "reason": {"type": "string"},
                },
                "required": ["operation", "reason"],
                "additionalProperties": False,
            },
        ]
    }
    schema = {
        "type": "object",
        "properties": {"plan": plan},
        "required": ["plan"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {"name": "architecture_query_plan", "strict": True, "schema": schema},
    }


def _step_schema_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for relationship in sorted(RELATIONSHIP_TYPES):
        pairs = relationship_type_pairs(relationship)
        variants.append(_step_schema(relationship, "outgoing", {target for _, target in pairs}))
        variants.append(_step_schema(relationship, "incoming", {source for source, _ in pairs}))
    return variants


def _step_schema(
    relationship: RelationshipType, direction: str, result_types: set[EntityType]
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "relationship": {"type": "string", "enum": [relationship]},
            "direction": {"type": "string", "enum": [direction]},
            "result_type": {
                "anyOf": [{"type": "string", "enum": sorted(result_types)}, {"type": "null"}]
            },
        },
        "required": ["relationship", "direction", "result_type"],
        "additionalProperties": False,
    }
