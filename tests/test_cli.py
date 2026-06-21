from __future__ import annotations

import json
from pathlib import Path

from graphify.cli import main


def _graph(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "entities": [{"id": "service:orders", "name": "Orders", "type": "Service"}],
                "relationships": [],
            }
        ),
        encoding="utf-8",
    )


def test_query_command_reads_local_graph(tmp_path: Path, capsys) -> None:
    graph_path = tmp_path / "graph.json"
    _graph(graph_path)

    exit_code = main(["query", "orders service", "--graph", str(graph_path)])

    assert exit_code == 0
    assert "service:orders" in capsys.readouterr().out


def test_codex_install_creates_only_codex_skill(tmp_path: Path) -> None:
    exit_code = main(["codex", "install", "--project-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / ".codex/skills/graphify/SKILL.md").is_file()
    assert not (tmp_path / ".claude").exists()
    assert "graphify build" in (tmp_path / ".codex/skills/graphify/SKILL.md").read_text()
