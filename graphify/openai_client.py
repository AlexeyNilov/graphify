from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, Protocol, cast

from graphify.schema import ENTITY_TYPES, RELATIONSHIP_TYPES, validate_extraction


class MarkdownExtractor(Protocol):
    def extract(self, text: str, source: str) -> dict[str, object]: ...


class OpenAIMarkdownExtractor:
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

    def extract(self, text: str, source: str) -> dict[str, object]:
        response = self._create_completion(
            model=self._model,
            messages=[
                {"role": "system", "content": _instructions()},
                {"role": "user", "content": f"Source: {source}\n\n{text}"},
            ],
            response_format=_response_format(),
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI-compatible provider returned no message content")
        data = json.loads(content)
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
        "json_schema": {
            "name": "architecture_extraction",
            "strict": True,
            "schema": schema,
        },
    }
