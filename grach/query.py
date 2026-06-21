from __future__ import annotations

import re
from collections import defaultdict, deque
from grach.schema import ArchitectureGraph, Entity

_WORD = re.compile(r"[a-z0-9]+")


def query_graph(graph: ArchitectureGraph, question: str) -> list[Entity]:
    terms = set(_WORD.findall(question.lower()))
    matches: list[tuple[int, Entity]] = []
    for entity in graph["entities"]:
        text = " ".join([entity["name"], entity["type"], *entity.get("aliases", [])]).lower()
        words = set(_WORD.findall(text))
        score = len(terms & words)
        if terms and terms <= words:
            matches.append((score, entity))
    return [entity for _, entity in sorted(matches, key=lambda item: (-item[0], item[1]["id"]))]


def find_paths(
    graph: ArchitectureGraph, source: str, target: str, *, max_depth: int = 6
) -> list[list[str]]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for relationship in graph["relationships"]:
        adjacency[relationship["source"]].append(relationship["target"])
    queue: deque[list[str]] = deque([[source]])
    paths: list[list[str]] = []
    while queue:
        path = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        for neighbor in sorted(adjacency[path[-1]]):
            if neighbor in path:
                continue
            next_path = [*path, neighbor]
            if neighbor == target:
                paths.append(next_path)
            else:
                queue.append(next_path)
    return paths


def affected_entities(graph: ArchitectureGraph, entity_id: str) -> list[str]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for relationship in graph["relationships"]:
        reverse[relationship["target"]].add(relationship["source"])
    return sorted(reverse[entity_id])
