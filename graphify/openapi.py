from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})


def load_openapi(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            import yaml

            data = yaml.safe_load(text)
    except (OSError, ValueError, ImportError):
        return None
    if not isinstance(data, dict) or not str(data.get("openapi", "")).startswith("3."):
        return None
    return data


def extract_openapi(spec: dict[str, Any], source_file: str) -> dict[str, object]:
    raw_info = spec.get("info")
    info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}
    title = str(info.get("title") or "Unnamed API")
    api: dict[str, object] = {
        "name": title,
        "type": "API",
        "version": str(info.get("version") or ""),
        "server_urls": _server_urls(spec),
    }
    entities: list[dict[str, object]] = [api]
    relationships: list[dict[str, object]] = []
    for route, method, operation in _operations(spec):
        operation_name = str(operation.get("operationId") or f"{method} {route}")
        endpoint: dict[str, object] = {
            "name": operation_name,
            "type": "Endpoint",
            "method": method.upper(),
            "path": route,
        }
        entities.append(endpoint)
        relationships.append(
            _relationship(title, "API", "EXPOSES", operation_name, "Endpoint", source_file, route)
        )
        for tag in operation.get("tags", []):
            if not isinstance(tag, str) or not tag.strip():
                continue
            service: dict[str, object] = {"name": tag, "type": "Service"}
            entities.append(service)
            relationships.append(
                _relationship(tag, "Service", "EXPOSES", title, "API", source_file, route)
            )
    return {"entities": entities, "relationships": relationships}


def _server_urls(spec: dict[str, Any]) -> list[str]:
    raw_servers = spec.get("servers")
    servers: list[Any] = raw_servers if isinstance(raw_servers, list) else []
    return [
        str(server["url"]) for server in servers if isinstance(server, dict) and server.get("url")
    ]


def _operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    raw_paths = spec.get("paths")
    paths: dict[Any, Any] = raw_paths if isinstance(raw_paths, dict) else {}
    result: list[tuple[str, str, dict[str, Any]]] = []
    for route, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() in _METHODS and isinstance(operation, dict):
                result.append((str(route), method.lower(), operation))
    return result


def _relationship(
    source: str,
    source_type: str,
    relation: str,
    target: str,
    target_type: str,
    source_file: str,
    location: str,
) -> dict[str, object]:
    return {
        "source": source,
        "source_type": source_type,
        "type": relation,
        "target": target,
        "target_type": target_type,
        "confidence": 1.0,
        "provenance": {
            "source_file": source_file,
            "source_location": location,
            "method": "openapi",
        },
    }
