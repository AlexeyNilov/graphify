from __future__ import annotations

from typing import Any, Literal, TypedDict, get_args

from grach.normalize import canonical_name

EntityType = Literal[
    "Service", "Database", "API", "Endpoint", "Event", "Team", "Document", "Infrastructure"
]
RelationshipType = Literal[
    "CALLS",
    "USES_DATABASE",
    "PUBLISHES",
    "CONSUMES",
    "DEPLOYED_TO",
    "OWNED_BY",
    "DESCRIBED_IN",
    "DEPENDS_ON",
    "EXPOSES",
    "GENERATES",
    "RECEIVES",
]

ENTITY_TYPES: frozenset[EntityType] = frozenset(get_args(EntityType))
RELATIONSHIP_TYPES: frozenset[RelationshipType] = frozenset(get_args(RelationshipType))

_NON_TEAM_TYPES = ENTITY_TYPES - {"Team"}
_NON_DOCUMENT_TYPES = ENTITY_TYPES - {"Document"}
_RELATIONSHIP_ENDPOINTS: dict[
    RelationshipType, tuple[frozenset[EntityType], frozenset[EntityType]]
] = {
    "CALLS": (frozenset({"Service", "API"}), frozenset({"Service", "API"})),
    "USES_DATABASE": (frozenset({"Service"}), frozenset({"Database"})),
    "PUBLISHES": (frozenset({"Service"}), frozenset({"Event"})),
    "CONSUMES": (frozenset({"Service"}), frozenset({"Event"})),
    "DEPLOYED_TO": (frozenset({"Service"}), frozenset({"Infrastructure"})),
    "OWNED_BY": (_NON_TEAM_TYPES, frozenset({"Team"})),
    "DESCRIBED_IN": (_NON_DOCUMENT_TYPES, frozenset({"Document"})),
    "DEPENDS_ON": (ENTITY_TYPES, ENTITY_TYPES),
    "EXPOSES": (frozenset({"Service", "API"}), frozenset({"API", "Endpoint"})),
    "GENERATES": (frozenset({"Service"}), frozenset({"Document"})),
    "RECEIVES": (frozenset({"API"}), frozenset({"Endpoint"})),
}
_RELATIONSHIP_PAIRS: dict[RelationshipType, frozenset[tuple[EntityType, EntityType]]] = {
    "EXPOSES": frozenset({("Service", "API"), ("API", "Endpoint")}),
}


def relationship_type_pairs(
    relationship_type: RelationshipType,
) -> frozenset[tuple[EntityType, EntityType]]:
    constrained_pairs = _RELATIONSHIP_PAIRS.get(relationship_type)
    if constrained_pairs is not None:
        return constrained_pairs
    source_types, target_types = _RELATIONSHIP_ENDPOINTS[relationship_type]
    return frozenset((source, target) for source in source_types for target in target_types)


class Provenance(TypedDict):
    source_file: str
    source_location: str
    method: Literal["openapi", "openai", "mermaid"]


class Entity(TypedDict, total=False):
    id: str
    name: str
    type: EntityType
    aliases: list[str]
    version: str
    method: str
    path: str
    server_urls: list[str]


class Relationship(TypedDict):
    source: str
    type: RelationshipType
    target: str
    confidence: float
    provenance: Provenance


class ArchitectureGraph(TypedDict):
    schema_version: str
    entities: list[Entity]
    relationships: list[Relationship]


def validate_extraction(data: dict[str, Any]) -> None:
    entities = data.get("entities")
    relationships = data.get("relationships")
    if not isinstance(entities, list) or not isinstance(relationships, list):
        raise ValueError("extraction must contain entity and relationship lists")
    references: set[tuple[str, str]] = set()
    for entity in entities:
        if not isinstance(entity, dict) or entity.get("type") not in ENTITY_TYPES:
            raise ValueError(f"unsupported entity type: {entity!r}")
        if not isinstance(entity.get("name"), str) or not entity["name"].strip():
            raise ValueError("every entity requires a non-empty name")
        references.add((canonical_name(entity["name"]), entity["type"]))
        references.update(
            (canonical_name(alias), entity["type"]) for alias in entity.get("aliases", [])
        )
    for relationship in relationships:
        if not isinstance(relationship, dict) or relationship.get("type") not in RELATIONSHIP_TYPES:
            raise ValueError(f"unsupported relationship type: {relationship!r}")
        if not all(isinstance(relationship.get(key), str) for key in ("source", "target")):
            raise ValueError("every relationship requires source and target names")
        if relationship.get("source_type") not in ENTITY_TYPES:
            raise ValueError("every relationship requires a supported source_type")
        if relationship.get("target_type") not in ENTITY_TYPES:
            raise ValueError("every relationship requires a supported target_type")
        source_reference = (canonical_name(relationship["source"]), relationship["source_type"])
        target_reference = (canonical_name(relationship["target"]), relationship["target_type"])
        if source_reference not in references:
            raise ValueError("relationship source must reference an extracted entity")
        if target_reference not in references:
            raise ValueError("relationship target must reference an extracted entity")
        _validate_relationship_endpoints(relationship)
        confidence = relationship.get("confidence")
        if not isinstance(confidence, int | float) or not 0 <= confidence <= 1:
            raise ValueError("relationship confidence must be between 0 and 1")


def _validate_relationship_endpoints(relationship: dict[str, Any]) -> None:
    relationship_type = relationship["type"]
    source_types, target_types = _RELATIONSHIP_ENDPOINTS[relationship_type]
    source_type = relationship["source_type"]
    target_type = relationship["target_type"]
    allowed_pairs = _RELATIONSHIP_PAIRS.get(relationship_type)
    if allowed_pairs is not None:
        if (source_type, target_type) in allowed_pairs:
            return
        expected = " or ".join(f"{source} -> {target}" for source, target in sorted(allowed_pairs))
        raise ValueError(
            f"{relationship_type} requires {expected}; received {source_type} -> {target_type}"
        )
    if source_type in source_types and target_type in target_types:
        return
    expected_sources = " | ".join(sorted(source_types))
    expected_targets = " | ".join(sorted(target_types))
    raise ValueError(
        f"{relationship_type} requires {expected_sources} -> {expected_targets}; "
        f"received {source_type} -> {target_type}"
    )
