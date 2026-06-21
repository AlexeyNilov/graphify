from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

from graphify.openai_client import OpenAIMarkdownExtractor


def test_openai_extractor_requests_strict_architecture_json_schema() -> None:
    captured: dict[str, object] = {}

    def create_response(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            output_text=json.dumps(
                {
                    "entities": [{"name": "Orders", "type": "Service"}],
                    "relationships": [],
                }
            )
        )

    extractor = OpenAIMarkdownExtractor(create_response=create_response)

    result = extractor.extract("Orders is a service.", "architecture.md")

    assert result["entities"] == [{"name": "Orders", "type": "Service"}]
    response_format = cast(dict[str, Any], captured["text"])["format"]
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert response_format["schema"]["additionalProperties"] is False
