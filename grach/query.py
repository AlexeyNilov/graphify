from __future__ import annotations

from collections import defaultdict, deque
from grach.schema import ArchitectureGraph


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
