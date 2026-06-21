from __future__ import annotations

from pathlib import Path
from typing import Any

from grach.markdown import add_mermaid_ownership
from grach.normalize import canonical_name, entity_id
from grach.openapi import extract_openapi, load_openapi
from grach.openai_client import MarkdownExtractor, OpenAIMarkdownExtractor
from grach.schema import (
    ArchitectureGraph,
    Entity,
    Provenance,
    Relationship,
    validate_extraction,
)


def build_architecture_graph(
    root: Path, *, markdown_extractor: MarkdownExtractor | None = None
) -> ArchitectureGraph:
    extractor = markdown_extractor
    extractions: list[tuple[dict[str, Any], str, str]] = []
    for path in _source_files(root):
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".md":
            extractor = extractor or OpenAIMarkdownExtractor()
            text = path.read_text(encoding="utf-8")
            data = extractor.extract(text, relative)
            validate_extraction(data)
            add_mermaid_ownership(data, text, relative)
            validate_extraction(data)
            extractions.append((data, relative, "openai"))
            continue
        spec = load_openapi(path)
        if spec is not None:
            data = extract_openapi(spec, relative)
            validate_extraction(data)
            extractions.append((data, relative, "openapi"))
    return _merge(extractions)


def _source_files(root: Path) -> list[Path]:
    supported = {".md", ".json", ".yaml", ".yml"}
    return sorted(path for path in root.rglob("*") if _supported_source(path, root, supported))


def _supported_source(path: Path, root: Path, supported: set[str]) -> bool:
    if not path.is_file() or path.suffix.lower() not in supported:
        return False
    relative = path.relative_to(root)
    return not any(part.startswith(".") or part == "grach-out" for part in relative.parts[:-1])


def _merge(extractions: list[tuple[dict[str, Any], str, str]]) -> ArchitectureGraph:
    entities: dict[str, Entity] = {}
    pending_relationships: list[tuple[dict[str, Any], str, str]] = []
    name_index: dict[tuple[str, str], str] = {}
    for extraction, source_file, method in extractions:
        for raw in extraction["entities"]:
            _merge_entity(entities, name_index, raw)
        pending_relationships.extend(
            (relationship, source_file, method) for relationship in extraction["relationships"]
        )
    relationships = [
        _normalize_relationship(raw, name_index, source_file, method)
        for raw, source_file, method in pending_relationships
    ]
    unique_relationships = {_relationship_key(item): item for item in relationships}
    return {
        "schema_version": "1.0",
        "entities": sorted(entities.values(), key=lambda item: item["id"]),
        "relationships": sorted(unique_relationships.values(), key=_relationship_key),
    }


def _merge_entity(
    entities: dict[str, Entity], name_index: dict[tuple[str, str], str], raw: dict[str, Any]
) -> None:
    entity_type = raw["type"]
    name = raw["name"].strip()
    identifier = entity_id(entity_type, name)
    name_index[(canonical_name(name), entity_type)] = identifier
    current = entities.setdefault(
        identifier, {"id": identifier, "name": _display_name(name), "type": entity_type}
    )
    aliases = {alias for alias in current.get("aliases", [])}
    aliases.update(str(alias) for alias in raw.get("aliases", []) if str(alias).strip())
    if name != current["name"]:
        aliases.add(name)
    if aliases:
        current["aliases"] = sorted(aliases)
        for alias in aliases:
            name_index[(canonical_name(alias), entity_type)] = identifier
    for key in ("version", "method", "path", "server_urls"):
        if raw.get(key):
            current[key] = raw[key]


def _display_name(name: str) -> str:
    words = canonical_name(name).split()
    return " ".join(word.upper() if word == "api" else word.capitalize() for word in words)


def _normalize_relationship(
    raw: dict[str, Any],
    name_index: dict[tuple[str, str], str],
    source_file: str,
    method: str,
) -> Relationship:
    provenance = _provenance(raw.get("provenance"), source_file, method)
    return {
        "source": name_index[(canonical_name(raw["source"]), raw["source_type"])],
        "type": raw["type"],
        "target": name_index[(canonical_name(raw["target"]), raw["target_type"])],
        "confidence": float(raw["confidence"]),
        "provenance": provenance,
    }


def _provenance(raw: object, source_file: str, method: str) -> Provenance:
    if isinstance(raw, dict):
        source_file = str(raw.get("source_file", source_file))
        location = str(raw.get("source_location", "document"))
        method = str(raw.get("method", method))
    else:
        location = "document"
    if method == "openapi":
        return {"source_file": source_file, "source_location": location, "method": "openapi"}
    if method == "mermaid":
        return {"source_file": source_file, "source_location": location, "method": "mermaid"}
    return {"source_file": source_file, "source_location": location, "method": "openai"}


def _relationship_key(item: Relationship) -> tuple[str, str, str, str, str]:
    provenance = item["provenance"]
    return (
        item["source"],
        item["type"],
        item["target"],
        provenance["source_file"],
        provenance["source_location"],
    )
