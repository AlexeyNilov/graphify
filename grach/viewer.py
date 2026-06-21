from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from grach.schema import ArchitectureGraph, Entity, Relationship


def graph_to_elements(graph: ArchitectureGraph) -> list[dict[str, object]]:
    elements: list[dict[str, object]] = []
    elements.extend({"data": _node_data(entity)} for entity in graph["entities"])
    elements.extend(
        {"data": _edge_data(index, relationship)}
        for index, relationship in enumerate(graph["relationships"])
    )
    return elements


def write_viewer(graph: ArchitectureGraph, output: Path) -> None:
    template = _asset("viewer.html")
    cytoscape = _asset("cytoscape.min.js")
    graph_json = json.dumps(graph_to_elements(graph), indent=2).replace("<", r"\u003c")
    html = template.replace("/*__CYTOSCAPE__*/", cytoscape).replace("__GRAPH_JSON__", graph_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def _node_data(entity: Entity) -> dict[str, object]:
    return {
        "id": entity["id"],
        "label": entity["name"],
        "type": entity["type"],
        "aliases": entity.get("aliases", []),
        **{
            key: value
            for key, value in entity.items()
            if key not in {"id", "name", "type", "aliases"}
        },
    }


def _edge_data(index: int, relationship: Relationship) -> dict[str, object]:
    return {
        "id": f"relationship:{index}",
        "label": relationship["type"],
        **relationship,
    }


def _asset(name: str) -> str:
    return resources.files("grach").joinpath("static").joinpath(name).read_text(encoding="utf-8")
