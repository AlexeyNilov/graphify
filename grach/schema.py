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


class Provenance(TypedDict):
    source_file: str
    source_location: str
    method: Literal["openapi", "openai"]


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
        confidence = relationship.get("confidence")
        if not isinstance(confidence, int | float) or not 0 <= confidence <= 1:
            raise ValueError("relationship confidence must be between 0 and 1")
