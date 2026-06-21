from __future__ import annotations

import html
import json
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path
from typing import cast

import pytest

from grach.schema import ArchitectureGraph
from grach.viewer import graph_to_elements, write_viewer


def _render_in_browser(command: list[str]) -> str:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, _ = process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        pytest.skip("Chromium timed out in this environment")
    if process.returncode != 0:
        pytest.skip("Chromium cannot run headless in this environment")
    return stdout


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


def test_ownership_preset_shows_owned_service_and_team(tmp_path: Path) -> None:
    output = tmp_path / "graph.html"
    graph = _graph()
    graph["entities"].append({"id": "team:commerce", "name": "Commerce Team", "type": "Team"})
    graph["relationships"].append(
        {
            "source": "service:orders",
            "type": "OWNED_BY",
            "target": "team:commerce",
            "confidence": 1.0,
            "provenance": {
                "source_file": "architecture.md",
                "source_location": "line 8",
                "method": "openai",
            },
        }
    )

    write_viewer(graph, output)
    verification = """
      <script>
        document.querySelector('[data-preset="Ownership"]').click();
        document.body.dataset.snapshot = JSON.stringify({
          nodes: displayed(cy.nodes()).map(node => node.data('label')).sort(),
          edges: displayed(cy.edges()).map(edge => edge.data('label')).sort()
        });
      </script>
    """
    output.write_text(
        output.read_text(encoding="utf-8").replace("</body>", f"{verification}</body>"),
        encoding="utf-8",
    )

    browser = next(
        (
            path
            for name in ("google-chrome", "chromium", "chromium-browser")
            if (path := shutil.which(name))
        ),
        None,
    )
    if browser is None:
        pytest.skip("A Chromium browser is required for viewer behavior tests")
    rendered = _render_in_browser(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--disable-extensions",
            "--no-sandbox",
            f"--user-data-dir={tmp_path / 'chrome-profile'}",
            "--virtual-time-budget=1000",
            "--dump-dom",
            output.as_uri(),
        ]
    )

    match = re.search(r'data-snapshot="([^"]+)"', rendered)
    assert match is not None
    snapshot = json.loads(html.unescape(match.group(1)))
    assert snapshot == {
        "nodes": ["Commerce Team", "Orders </script>"],
        "edges": ["OWNED_BY"],
    }
