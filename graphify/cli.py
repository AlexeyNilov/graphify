from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from graphify.pipeline import build_architecture_graph
from graphify.query import affected_entities, find_paths, query_graph
from graphify.schema import ArchitectureGraph

_DEFAULT_GRAPH = Path("graphify-out/graph.json")
_SKILL = """---
name: graphify
description: Build and query a corporate architecture graph from Markdown and OpenAPI files.
---

# Graphify

- Run `graphify build <path>` to create `graphify-out/graph.json`.
- Run `graphify query "<question>"` before searching source documents manually.
- Use `graphify path <source-id> <target-id>` for dependencies.
- Use `graphify affected <entity-id>` for direct reverse impact.
- Treat inferred relationships according to their confidence and provenance.
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        graph = build_architecture_graph(args.path)
        _write_graph(graph, args.out)
        print(f"Wrote {args.out}")
        return 0
    if args.command == "query":
        _print_json(query_graph(_read_graph(args.graph), args.question))
        return 0
    if args.command == "path":
        _print_json(find_paths(_read_graph(args.graph), args.source, args.target))
        return 0
    if args.command == "affected":
        _print_json(affected_entities(_read_graph(args.graph), args.entity))
        return 0
    if args.command == "inspect":
        graph = _read_graph(args.graph)
        entity = next((item for item in graph["entities"] if item["id"] == args.entity), None)
        _print_json(entity)
        return 0 if entity else 1
    if args.command == "codex":
        return _codex(args.action, args.project_dir)
    parser.print_help()
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="graphify")
    subparsers = parser.add_subparsers(dest="command")
    build = subparsers.add_parser("build", help="build graph.json from Markdown and OpenAPI")
    build.add_argument("path", type=Path)
    build.add_argument("--out", type=Path, default=_DEFAULT_GRAPH)
    query = subparsers.add_parser("query", help="search graph entities")
    query.add_argument("question")
    _graph_argument(query)
    path = subparsers.add_parser("path", help="find directed paths between entities")
    path.add_argument("source")
    path.add_argument("target")
    _graph_argument(path)
    affected = subparsers.add_parser("affected", help="find direct reverse dependencies")
    affected.add_argument("entity")
    _graph_argument(affected)
    inspect = subparsers.add_parser("inspect", help="show one entity")
    inspect.add_argument("entity")
    _graph_argument(inspect)
    codex = subparsers.add_parser("codex", help="manage the Codex skill")
    codex.add_argument("action", choices=("install", "uninstall"))
    codex.add_argument("--project-dir", type=Path, default=Path.cwd())
    return parser


def _graph_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--graph", type=Path, default=_DEFAULT_GRAPH)


def _read_graph(path: Path) -> ArchitectureGraph:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_graph(graph: ArchitectureGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2))


def _codex(action: str, project_dir: Path) -> int:
    skill = project_dir / ".codex" / "skills" / "graphify" / "SKILL.md"
    if action == "install":
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(_SKILL, encoding="utf-8")
        print(f"Installed {skill}")
        return 0
    if skill.exists():
        skill.unlink()
    print(f"Uninstalled {skill}")
    return 0
