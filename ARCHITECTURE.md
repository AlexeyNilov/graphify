# Architecture

Graphify has one pipeline:

```text
discover -> extract -> normalize -> validate -> merge -> graph.json -> query
```

## Responsibilities

| Module | Responsibility |
|---|---|
| `schema.py` | Closed entity and relationship vocabulary plus boundary validation |
| `openapi.py` | Deterministic OpenAPI 3.x extraction |
| `openai_client.py` | OpenAI-backed Markdown extraction |
| `normalize.py` | Stable canonical names and typed IDs |
| `pipeline.py` | Discovery, extraction orchestration, normalization, and merge |
| `query.py` | Entity search, directed paths, and reverse impact |
| `cli.py` | CLI and project-local Codex skill installation |

OpenAPI relationships have confidence `1.0`. Markdown relationships receive confidence from the
model and are labeled with extraction method `openai`. Both paths retain source provenance.

`graph.json` is a derived local artifact. There is no graph database or vector index in the first
simplified release.
