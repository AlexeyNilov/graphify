from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, Protocol, cast

from graphify.schema import ENTITY_TYPES, RELATIONSHIP_TYPES, validate_extraction


class MarkdownExtractor(Protocol):
    def extract(self, text: str, source: str) -> dict[str, object]: ...


class ResponseOutput(Protocol):
    output_text: str


class OpenAIMarkdownExtractor:
    def __init__(
        self,
        model: str | None = None,
        *,
        create_response: Callable[..., ResponseOutput] | None = None,
    ) -> None:
        if create_response is None:
            from openai import OpenAI

            create_response = cast(Callable[..., ResponseOutput], OpenAI().responses.create)
        self._create_response = create_response
        self._model = model or os.environ.get("GRAPHIFY_OPENAI_MODEL", "gpt-4.1-mini")

    def extract(self, text: str, source: str) -> dict[str, object]:
        response = self._create_response(
            model=self._model,
            instructions=_instructions(),
            input=f"Source: {source}\n\n{text}",
            text={"format": _response_format()},
        )
        data = json.loads(response.output_text)
        validate_extraction(data)
        return data


def _instructions() -> str:
    entities = ", ".join(sorted(ENTITY_TYPES))
    relationships = ", ".join(sorted(RELATIONSHIP_TYPES))
    return (
        "Extract only explicitly stated corporate architecture facts. Return JSON with "
        "entities and relationships arrays. Entity fields: name, type, optional aliases. "
        "Relationship fields: source, source_type, type, target, target_type, confidence from 0 "
        "to 1. Entity endpoint types must match the referenced entities. "
        f"Allowed entity types: {entities}. Allowed relationship types: {relationships}. "
        "Do not invent missing services or relationships."
    )


def _response_format() -> dict[str, Any]:
    entity = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"type": "string", "enum": sorted(ENTITY_TYPES)},
            "aliases": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "type", "aliases"],
        "additionalProperties": False,
    }
    relationship = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "source_type": {"type": "string", "enum": sorted(ENTITY_TYPES)},
            "type": {"type": "string", "enum": sorted(RELATIONSHIP_TYPES)},
            "target": {"type": "string"},
            "target_type": {"type": "string", "enum": sorted(ENTITY_TYPES)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["source", "source_type", "type", "target", "target_type", "confidence"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "entities": {"type": "array", "items": entity},
            "relationships": {"type": "array", "items": relationship},
        },
        "required": ["entities", "relationships"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "name": "architecture_extraction",
        "strict": True,
        "schema": schema,
    }
