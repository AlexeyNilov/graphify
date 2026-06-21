from __future__ import annotations

import json
from pathlib import Path

from grach.cli import main


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


def test_query_command_plans_and_executes_against_local_graph(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    graph_path = tmp_path / "graph.json"
    _graph(graph_path)

    class FakePlanner:
        def plan(self, question: str) -> dict[str, object]:
            assert question == "find orders service"
            return {
                "operation": "ENTITY_SEARCH",
                "selector": {"name": "Orders", "type": "Service"},
            }

    monkeypatch.setattr("grach.query_planner.OpenAIQueryPlanner", FakePlanner)

    exit_code = main(["query", "find orders service", "--graph", str(graph_path)])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["plan"]["operation"] == "ENTITY_SEARCH"
    assert [entity["id"] for entity in output["entities"]] == ["service:orders"]


def test_query_command_reports_ambiguous_anchor(tmp_path: Path, capsys, monkeypatch) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "entities": [
                    {"id": "service:orders", "name": "Orders", "type": "Service"},
                    {"id": "database:orders", "name": "Orders", "type": "Database"},
                ],
                "relationships": [],
            }
        ),
        encoding="utf-8",
    )

    class FakePlanner:
        def plan(self, question: str) -> dict[str, object]:
            return {"operation": "ENTITY_SEARCH", "selector": {"name": "Orders"}}

    monkeypatch.setattr("grach.query_planner.OpenAIQueryPlanner", FakePlanner)

    exit_code = main(["query", "find orders", "--graph", str(graph_path)])

    assert exit_code == 2
    error = capsys.readouterr().err
    assert "ambiguous" in error
    assert "database:orders" in error
    assert "service:orders" in error


def test_query_command_reports_planner_failure(tmp_path: Path, capsys, monkeypatch) -> None:
    from grach.query_planner import QueryPlannerError

    graph_path = tmp_path / "graph.json"
    _graph(graph_path)

    class FakePlanner:
        def plan(self, question: str) -> dict[str, object]:
            raise QueryPlannerError("provider returned invalid query-plan JSON")

    monkeypatch.setattr("grach.query_planner.OpenAIQueryPlanner", FakePlanner)

    exit_code = main(["query", "find orders", "--graph", str(graph_path)])

    assert exit_code == 2
    assert "invalid query-plan JSON" in capsys.readouterr().err


def test_codex_install_creates_only_codex_skill(tmp_path: Path) -> None:
    exit_code = main(["codex", "install", "--project-dir", str(tmp_path)])

    assert exit_code == 0
    skill = tmp_path / ".codex/skills/grach/SKILL.md"
    assert skill.is_file()
    assert not (tmp_path / ".claude").exists()
    assert "grach build" in skill.read_text()


def test_build_command_writes_to_grach_output_by_default(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.chdir(tmp_path)

    exit_code = main(["build", str(source)])

    assert exit_code == 0
    assert (tmp_path / "grach-out/graph.json").is_file()
    assert "grach-out/graph.json" in capsys.readouterr().out


def test_view_command_writes_offline_html_from_local_graph(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    graph_path = tmp_path / "graph.json"
    _graph(graph_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["view", "--graph", str(graph_path)])

    assert exit_code == 0
    output = tmp_path / "grach-out/graph.html"
    assert output.is_file()
    assert "service:orders" in output.read_text(encoding="utf-8")
    assert "grach-out/graph.html" in capsys.readouterr().out
