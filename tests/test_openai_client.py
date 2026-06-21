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
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "entities": [{"name": "Orders", "type": "Service"}],
                                "relationships": [],
                            }
                        )
                    )
                )
            ]
        )

    extractor = OpenAIMarkdownExtractor(create_completion=create_response)

    result = extractor.extract("Orders is a service.", "architecture.md")

    assert result["entities"] == [{"name": "Orders", "type": "Service"}]
    response_format = cast(dict[str, Any], captured["response_format"])["json_schema"]
    messages = cast(list[dict[str, str]], captured["messages"])
    assert messages[1] == {
        "role": "user",
        "content": "Source: architecture.md\n\nOrders is a service.",
    }
    assert response_format["strict"] is True
    assert response_format["schema"]["additionalProperties"] is False


def test_openai_environment_configures_lm_studio(monkeypatch) -> None:
    client_settings: dict[str, object] = {}
    request: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            request.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"entities": [], "relationships": []}')
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            client_settings.update(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("OPENAI_MODEL", "google/gemma-4-12b-qat")
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    OpenAIMarkdownExtractor().extract("Nothing", "architecture.md")

    assert client_settings == {
        "api_key": "key",
        "base_url": "http://127.0.0.1:1234/v1",
    }
    assert request["model"] == "google/gemma-4-12b-qat"
