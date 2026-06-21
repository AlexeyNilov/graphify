from __future__ import annotations

import json
from pathlib import Path

from grach.pipeline import build_architecture_graph
from grach.query import affected_entities, find_paths


class FakeMarkdownExtractor:
    def extract(self, text: str, source: str) -> dict[str, object]:
        assert "Order Service" in text
        return {
            "entities": [
                {"name": "OrderService", "type": "Service", "aliases": ["order-service"]},
                {"name": "Orders", "type": "Database"},
            ],
            "relationships": [
                {
                    "source": "OrderService",
                    "source_type": "Service",
                    "type": "USES_DATABASE",
                    "target": "Orders",
                    "target_type": "Database",
                    "confidence": 0.9,
                }
            ],
        }


def _write_openapi(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "info": {"title": "Orders API", "version": "1.2.0"},
                "servers": [{"url": "https://orders.example.test"}],
                "paths": {
                    "/orders": {
                        "post": {
                            "operationId": "createOrder",
                            "tags": ["Order Service"],
                            "responses": {"201": {"description": "Created"}},
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_build_combines_openapi_and_markdown_with_stable_provenance(tmp_path: Path) -> None:
    _write_openapi(tmp_path / "openapi.json")
    (tmp_path / "architecture.md").write_text(
        "The Order Service stores orders in the Orders database.", encoding="utf-8"
    )

    graph = build_architecture_graph(tmp_path, markdown_extractor=FakeMarkdownExtractor())

    entities = {entity["id"]: entity for entity in graph["entities"]}
    assert entities["service:order-service"]["aliases"] == ["OrderService", "order-service"]
    assert entities["api:orders-api"]["version"] == "1.2.0"
    assert entities["endpoint:create-order"]["method"] == "POST"

    relationships = graph["relationships"]
    exposes = next(item for item in relationships if item["type"] == "EXPOSES")
    assert exposes["source"] == "api:orders-api"
    assert exposes["target"] == "endpoint:create-order"
    assert exposes["confidence"] == 1.0
    assert exposes["provenance"]["method"] == "openapi"
    assert exposes["provenance"]["source_file"] == "openapi.json"

    uses_database = next(item for item in relationships if item["type"] == "USES_DATABASE")
    assert uses_database["source"] == "service:order-service"
    assert uses_database["provenance"]["method"] == "openai"


def test_queries_cover_paths_and_reverse_impact(tmp_path: Path) -> None:
    _write_openapi(tmp_path / "openapi.json")
    (tmp_path / "architecture.md").write_text("Order Service architecture", encoding="utf-8")
    graph = build_architecture_graph(tmp_path, markdown_extractor=FakeMarkdownExtractor())

    assert find_paths(graph, "api:orders-api", "endpoint:create-order") == [
        ["api:orders-api", "endpoint:create-order"]
    ]
    assert affected_entities(graph, "database:orders") == ["service:order-service"]


def test_unsupported_files_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("raise RuntimeError", encoding="utf-8")
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "instructions.md").write_text("hidden", encoding="utf-8")
    (tmp_path / "grach-out").mkdir()
    (tmp_path / "grach-out" / "report.md").write_text("generated", encoding="utf-8")

    graph = build_architecture_graph(tmp_path, markdown_extractor=FakeMarkdownExtractor())

    assert graph == {"schema_version": "1.0", "entities": [], "relationships": []}


def test_same_name_entities_remain_distinct_when_relationships_are_resolved(tmp_path: Path) -> None:
    class SameNameExtractor:
        def extract(self, text: str, source: str) -> dict[str, object]:
            return {
                "entities": [
                    {"name": "Orders", "type": "Service"},
                    {"name": "Orders", "type": "Database"},
                ],
                "relationships": [
                    {
                        "source": "Orders",
                        "source_type": "Service",
                        "type": "USES_DATABASE",
                        "target": "Orders",
                        "target_type": "Database",
                        "confidence": 1.0,
                    }
                ],
            }

    (tmp_path / "architecture.md").write_text("Orders uses Orders", encoding="utf-8")

    graph = build_architecture_graph(tmp_path, markdown_extractor=SameNameExtractor())

    relationship = graph["relationships"][0]
    assert relationship["source"] == "service:orders"
    assert relationship["target"] == "database:orders"


def test_openapi_yaml_is_extracted_without_using_the_llm(tmp_path: Path) -> None:
    (tmp_path / "catalog.yaml").write_text(
        """openapi: 3.0.3
info:
  title: Catalog API
  version: 1.0.0
paths:
  /items:
    get:
      operationId: listItems
      responses:
        '200':
          description: OK
""",
        encoding="utf-8",
    )

    graph = build_architecture_graph(tmp_path)

    assert {entity["id"] for entity in graph["entities"]} == {
        "api:catalog-api",
        "endpoint:list-items",
    }


def test_mermaid_owns_edges_restore_ownership_omitted_by_model(tmp_path: Path) -> None:
    class OwnershipOmittingExtractor:
        def extract(self, text: str, source: str) -> dict[str, object]:
            return {
                "entities": [
                    {"name": "Web Store", "type": "Service"},
                    {"name": "Order Service", "type": "Service"},
                    {"name": "Commerce Team", "type": "Team"},
                ],
                "relationships": [],
            }

    (tmp_path / "architecture.md").write_text(
        """```mermaid
flowchart LR
    Web[Web Store] --> Orders[Order Service]
    Team[Commerce Team] -. owns .-> Web
    Team -. owns .-> Orders
```
""",
        encoding="utf-8",
    )

    graph = build_architecture_graph(tmp_path, markdown_extractor=OwnershipOmittingExtractor())

    ownership = {
        (relationship["source"], relationship["target"])
        for relationship in graph["relationships"]
        if relationship["type"] == "OWNED_BY"
    }
    assert ownership == {
        ("service:order-service", "team:commerce-team"),
        ("service:web-store", "team:commerce-team"),
    }
    assert {
        relationship["provenance"]["method"]
        for relationship in graph["relationships"]
        if relationship["type"] == "OWNED_BY"
    } == {"mermaid"}
