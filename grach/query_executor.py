from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

from grach.normalize import canonical_name
from grach.schema import (
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    ArchitectureGraph,
    Entity,
    EntityType,
    Relationship,
    RelationshipType,
    relationship_type_pairs,
)

TraversalDirection = Literal["incoming", "outgoing"]


class EntitySelector(TypedDict, total=False):
    id: str
    name: str
    type: EntityType | None


class TraversalStep(TypedDict, total=False):
    relationship: RelationshipType
    direction: TraversalDirection
    result_type: EntityType | None


class EntitySearchPlan(TypedDict):
    operation: Literal["ENTITY_SEARCH"]
    selector: EntitySelector


class TraversePlan(TypedDict):
    operation: Literal["TRAVERSE"]
    anchor: EntitySelector
    steps: list[TraversalStep]


class UnsupportedPlan(TypedDict):
    operation: Literal["UNSUPPORTED"]
    reason: str


QueryPlan = EntitySearchPlan | TraversePlan | UnsupportedPlan


class QueryPlanError(ValueError):
    pass


class InvalidQueryPlanError(QueryPlanError):
    pass


class InvalidTraversalSemanticsError(InvalidQueryPlanError):
    pass


class EntityNotFoundError(QueryPlanError):
    pass


class UnsupportedQueryError(QueryPlanError):
    pass


class AmbiguousEntityError(QueryPlanError):
    def __init__(self, selector: EntitySelector, candidate_ids: list[str]) -> None:
        self.candidate_ids = tuple(sorted(candidate_ids))
        super().__init__(
            f"entity selector {_describe_selector(selector)} is ambiguous; "
            f"candidates: {', '.join(self.candidate_ids)}"
        )


def validate_query_plan(data: object) -> QueryPlan:
    if not isinstance(data, dict):
        raise InvalidQueryPlanError("query plan must be an object")
    operation = data.get("operation")
    if operation == "ENTITY_SEARCH":
        _require_keys(data, {"operation", "selector"}, "entity search plan")
        _validate_selector(data.get("selector"), label="selector")
        return cast(EntitySearchPlan, data)
    if operation == "TRAVERSE":
        _require_keys(data, {"operation", "anchor", "steps"}, "traverse plan")
        _validate_selector(data.get("anchor"), label="anchor")
        _validate_steps(data.get("steps"))
        _validate_traversal_types(
            cast(EntitySelector, data["anchor"]), cast(list[TraversalStep], data["steps"])
        )
        return cast(TraversePlan, data)
    if operation == "UNSUPPORTED":
        _require_keys(data, {"operation", "reason"}, "unsupported plan")
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidQueryPlanError("unsupported plan requires a non-empty reason")
        return cast(UnsupportedPlan, data)
    raise InvalidQueryPlanError(f"unsupported query operation: {operation!r}")


def execute_query_plan(graph: ArchitectureGraph, plan_data: object) -> list[Entity]:
    plan = validate_query_plan(plan_data)
    if plan["operation"] == "ENTITY_SEARCH":
        return [_resolve_entity(graph["entities"], plan["selector"])]
    if plan["operation"] == "UNSUPPORTED":
        raise UnsupportedQueryError(plan["reason"])
    entities_by_id = {entity["id"]: entity for entity in graph["entities"]}
    current_ids = {_resolve_entity(graph["entities"], plan["anchor"])["id"]}
    for step in plan["steps"]:
        current_ids = _traverse_step(graph, entities_by_id, current_ids, step)
    return [entities_by_id[entity_id] for entity_id in sorted(current_ids)]


def _validate_selector(value: object, *, label: str) -> None:
    if not isinstance(value, dict):
        raise InvalidQueryPlanError(f"{label} must be an object")
    _require_keys(value, {"id", "name", "type"}, label, required=set())
    identifiers = [key for key in ("id", "name") if key in value]
    if len(identifiers) != 1:
        raise InvalidQueryPlanError(f"{label} requires exactly one of id or name")
    identifier = value[identifiers[0]]
    if not isinstance(identifier, str) or not identifier.strip():
        raise InvalidQueryPlanError(f"{label} {identifiers[0]} must be a non-empty string")
    entity_type = value.get("type")
    if entity_type is not None and (
        not isinstance(entity_type, str) or entity_type not in ENTITY_TYPES
    ):
        raise InvalidQueryPlanError(f"unsupported entity type: {entity_type!r}")


def _validate_steps(value: object) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= 6:
        raise InvalidQueryPlanError("traverse plan requires between 1 and 6 steps")
    for index, step in enumerate(value):
        _validate_step(step, index)


def _validate_step(value: object, index: int) -> None:
    if not isinstance(value, dict):
        raise InvalidQueryPlanError(f"step {index} must be an object")
    _require_keys(
        value,
        {"relationship", "direction", "result_type"},
        f"step {index}",
        required={"relationship", "direction"},
    )
    relationship = value.get("relationship")
    if not isinstance(relationship, str) or relationship not in RELATIONSHIP_TYPES:
        raise InvalidQueryPlanError(f"unsupported relationship type: {relationship!r}")
    if value.get("direction") not in ("incoming", "outgoing"):
        raise InvalidQueryPlanError("step direction must be incoming or outgoing")
    result_type = value.get("result_type")
    if result_type is not None and (
        not isinstance(result_type, str) or result_type not in ENTITY_TYPES
    ):
        raise InvalidQueryPlanError(f"unsupported result entity type: {result_type!r}")


def _validate_traversal_types(anchor: EntitySelector, steps: list[TraversalStep]) -> None:
    anchor_type = anchor.get("type")
    possible_types = set(ENTITY_TYPES if anchor_type is None else {anchor_type})
    for index, step in enumerate(steps):
        possible_types = _step_result_types(possible_types, step, index)


def _step_result_types(
    possible_types: set[EntityType], step: TraversalStep, index: int
) -> set[EntityType]:
    pairs = _directed_type_pairs(step)
    result_type = step.get("result_type")
    valid_pairs = {
        pair
        for pair in pairs
        if pair[0] in possible_types and (result_type is None or pair[1] == result_type)
    }
    if valid_pairs:
        return {output_type for _, output_type in valid_pairs}
    inputs = ", ".join(sorted(possible_types))
    output = "" if result_type is None else f" and produce {result_type}"
    raise InvalidTraversalSemanticsError(
        f"step {index} {step['relationship']} {step['direction']} cannot start from {inputs}{output}; "
        f"requires {_describe_type_pairs(pairs)}"
    )


def _directed_type_pairs(
    step: TraversalStep,
) -> frozenset[tuple[EntityType, EntityType]]:
    pairs = relationship_type_pairs(step["relationship"])
    if step["direction"] == "incoming":
        return frozenset((target, source) for source, target in pairs)
    return pairs


def _describe_type_pairs(pairs: frozenset[tuple[EntityType, EntityType]]) -> str:
    outputs_by_input: dict[EntityType, set[EntityType]] = {}
    for input_type, output_type in pairs:
        outputs_by_input.setdefault(input_type, set()).add(output_type)
    return " or ".join(
        f"{input_type} -> {', '.join(sorted(output_types))}"
        for input_type, output_types in sorted(outputs_by_input.items())
    )


def _require_keys(
    value: dict[Any, Any],
    allowed: set[str],
    label: str,
    *,
    required: set[str] | None = None,
) -> None:
    unexpected = set(value) - allowed
    if unexpected:
        fields = ", ".join(repr(field) for field in sorted(unexpected, key=repr))
        raise InvalidQueryPlanError(f"{label} has unexpected fields: {fields}")
    missing = (allowed if required is None else required) - set(value)
    if missing:
        raise InvalidQueryPlanError(f"{label} is missing fields: {', '.join(sorted(missing))}")


def _resolve_entity(entities: list[Entity], selector: EntitySelector) -> Entity:
    candidates = [entity for entity in entities if _matches_selector(entity, selector)]
    if not candidates:
        raise EntityNotFoundError(f"no entity matches {_describe_selector(selector)}")
    if len(candidates) > 1:
        raise AmbiguousEntityError(selector, [entity["id"] for entity in candidates])
    return candidates[0]


def _matches_selector(entity: Entity, selector: EntitySelector) -> bool:
    if selector.get("type") is not None and entity["type"] != selector["type"]:
        return False
    if "id" in selector:
        return entity["id"] == selector["id"]
    expected = canonical_name(selector["name"])
    names = [entity["name"], *entity.get("aliases", [])]
    return any(canonical_name(name) == expected for name in names)


def _describe_selector(selector: EntitySelector) -> str:
    identifier = f"id={selector['id']!r}" if "id" in selector else f"name={selector['name']!r}"
    if selector.get("type") is not None:
        return f"{identifier}, type={selector['type']!r}"
    return identifier


def _traverse_step(
    graph: ArchitectureGraph,
    entities_by_id: dict[str, Entity],
    current_ids: set[str],
    step: TraversalStep,
) -> set[str]:
    result_ids: set[str] = set()
    for relationship in graph["relationships"]:
        if relationship["type"] != step["relationship"]:
            continue
        endpoint = _matching_endpoint(relationship, current_ids, step["direction"])
        if endpoint is None:
            continue
        entity = entities_by_id.get(endpoint)
        if entity is None:
            continue
        result_type = step.get("result_type")
        if result_type is None or entity["type"] == result_type:
            result_ids.add(endpoint)
    return result_ids


def _matching_endpoint(
    relationship: Relationship, current_ids: set[str], direction: TraversalDirection
) -> str | None:
    if direction == "outgoing" and relationship["source"] in current_ids:
        return relationship["target"]
    if direction == "incoming" and relationship["target"] in current_ids:
        return relationship["source"]
    return None
