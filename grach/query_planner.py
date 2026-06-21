from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, cast

from grach.query_executor import QueryPlan, validate_query_plan
from grach.schema import ENTITY_TYPES, RELATIONSHIP_TYPES


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
        try:
            response = self._create_completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": _instructions()},
                    {"role": "user", "content": question},
                ],
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
        try:
            data = json.loads(content)
        except json.JSONDecodeError as error:
            raise QueryPlannerError(
                f"provider returned invalid query-plan JSON: {error}"
            ) from error
        if not isinstance(data, dict) or set(data) != {"plan"}:
            raise QueryPlannerError("provider response must contain exactly one plan object")
        return validate_query_plan(data["plan"])


def _instructions() -> str:
    entities = ", ".join(sorted(ENTITY_TYPES))
    relationships = ", ".join(sorted(RELATIONSHIP_TYPES))
    return (
        "Translate the question into one bounded architecture query plan. Use ENTITY_SEARCH with "
        "one selector for questions that only identify an entity. Use TRAVERSE with one anchor and "
        "ordered relationship steps for relationship questions. Use UNSUPPORTED with a concise "
        "reason when the question cannot be expressed with the allowed graph vocabulary. Selectors "
        "use exactly one of id or name and may include type. Never answer the question or invent "
        "graph facts. "
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
    step = {
        "type": "object",
        "properties": {
            "relationship": {"type": "string", "enum": sorted(RELATIONSHIP_TYPES)},
            "direction": {"type": "string", "enum": ["incoming", "outgoing"]},
            "result_type": optional_entity_type,
        },
        "required": ["relationship", "direction", "result_type"],
        "additionalProperties": False,
    }
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
