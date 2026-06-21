from __future__ import annotations

from pathlib import Path
from typing import cast

from grach.schema import ArchitectureGraph
from grach.viewer import graph_to_elements, write_viewer


def _graph() -> ArchitectureGraph:
    return {
        "schema_version": "1.0",
        "entities": [
            {
                "id": "service:orders",
                "name": "Orders </script>",
                "type": "Service",
                "aliases": ["OMS"],
            },
            {"id": "database:orders", "name": "Orders DB", "type": "Database"},
        ],
        "relationships": [
            {
                "source": "service:orders",
                "type": "USES_DATABASE",
                "target": "database:orders",
                "confidence": 0.8,
                "provenance": {
                    "source_file": "architecture.md",
                    "source_location": "line 4",
                    "method": "openai",
                },
            }
        ],
    }


def test_graph_projection_preserves_graph_semantics_and_evidence() -> None:
    elements = graph_to_elements(_graph())
    edge = cast(dict[str, object], elements[2]["data"])
    provenance = cast(dict[str, str], edge["provenance"])

    assert elements[0]["data"] == {
        "id": "service:orders",
        "label": "Orders </script>",
        "type": "Service",
        "aliases": ["OMS"],
    }
    assert edge["source"] == "service:orders"
    assert edge["target"] == "database:orders"
    assert edge["confidence"] == 0.8
    assert provenance["source_file"] == "architecture.md"


def test_write_viewer_creates_offline_html_without_unescaped_script_data(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "graph.html"

    write_viewer(_graph(), output)

    html = output.read_text(encoding="utf-8")
    assert "cytoscape" in html
    assert "https://" not in html
    assert "Orders </script>" not in html
    assert r"Orders \u003c/script>" in html
    assert '"source_file": "architecture.md"' in html
