from __future__ import annotations

import re
from typing import Any, cast

from grach.normalize import canonical_name

_MERMAID_BLOCK = re.compile(r"```mermaid\s*\n(?P<body>.*?)```", re.DOTALL | re.IGNORECASE)
_NODE = re.compile(
    r"\b(?P<id>[A-Za-z_][\w-]*)\s*"
    r"(?:\[\((?P<database>[^]]+)\)\]|\[(?P<square>[^]]+)\]|"
    r"\((?P<round>[^)]+)\)|\{(?P<brace>[^}]+)\})"
)
_OWNS_EDGE = re.compile(
    r"^\s*(?P<owner>[A-Za-z_][\w-]*)(?:\s*[\[({][^\])}]*[\])}])?"
    r"\s*-\.\s*owns\s*\.-+>\s*(?P<owned>[A-Za-z_][\w-]*)",
    re.IGNORECASE | re.MULTILINE,
)


def add_mermaid_ownership(data: dict[str, object], text: str, source: str) -> None:
    entities = cast(list[dict[str, Any]], data["entities"])
    relationships = cast(list[dict[str, Any]], data["relationships"])
    for match in _MERMAID_BLOCK.finditer(text):
        for owner_name, owned_name in _ownership_pairs(match.group("body")):
            owner = _resolve_entity(entities, owner_name, team=True)
            owned = _resolve_entity(entities, owned_name, team=False)
            if owner is None or owned is None or _has_ownership(relationships, owned, owner):
                continue
            relationships.append(_ownership(owned, owner, source))


def _ownership_pairs(block: str) -> list[tuple[str, str]]:
    labels = _node_labels(block)
    return [
        (labels.get(edge["owner"], edge["owner"]), labels.get(edge["owned"], edge["owned"]))
        for edge in _OWNS_EDGE.finditer(block)
    ]


def _node_labels(block: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for match in _NODE.finditer(block):
        label = next(
            match[group]
            for group in ("database", "square", "round", "brace")
            if match[group] is not None
        )
        labels[match["id"]] = label.strip().strip('"')
    return labels


def _resolve_entity(
    entities: list[dict[str, Any]], name: str, *, team: bool
) -> dict[str, Any] | None:
    matches = [entity for entity in entities if _matches_name(entity, name)]
    matches = [entity for entity in matches if (entity["type"] == "Team") is team]
    return matches[0] if len(matches) == 1 else None


def _matches_name(entity: dict[str, Any], name: str) -> bool:
    expected = canonical_name(name)
    names = [entity["name"], *entity.get("aliases", [])]
    return any(canonical_name(candidate) == expected for candidate in names)


def _has_ownership(
    relationships: list[dict[str, Any]], owned: dict[str, Any], owner: dict[str, Any]
) -> bool:
    expected = (canonical_name(owned["name"]), canonical_name(owner["name"]))
    return any(
        relationship.get("type") == "OWNED_BY"
        and (canonical_name(relationship["source"]), canonical_name(relationship["target"]))
        == expected
        for relationship in relationships
    )


def _ownership(owned: dict[str, Any], owner: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "source": owned["name"],
        "source_type": owned["type"],
        "type": "OWNED_BY",
        "target": owner["name"],
        "target_type": "Team",
        "confidence": 1.0,
        "provenance": {
            "source_file": source,
            "source_location": "Mermaid owns edge",
            "method": "mermaid",
        },
    }
