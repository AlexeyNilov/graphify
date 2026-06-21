# Architecture

Grach has one pipeline:

```text
discover -> extract -> validate -> normalize -> merge -> graph.json -> query/view
```

## Responsibilities

| Module | Responsibility |
|---|---|
| `schema.py` | Closed entity and relationship vocabulary plus boundary validation |
| `openapi.py` | Deterministic OpenAPI 3.x extraction |
| `openai_client.py` | OpenAI-compatible Markdown extraction, including local LM Studio |
| `normalize.py` | Stable canonical names and typed IDs |
| `pipeline.py` | Discovery, extraction orchestration, normalization, and merge |
| `query.py` | Entity search, directed paths, and reverse impact |
| `viewer.py` | Viewer projection and self-contained offline HTML generation |
| `cli.py` | CLI and project-local Codex skill installation |

OpenAPI relationships have confidence `1.0`. Markdown relationships receive confidence from the
model and are labeled with extraction method `openai`. The adapter uses Chat Completions with a
strict JSON schema so LM Studio and OpenAI share one extraction path. Both paths retain source
provenance.

When a Markdown extraction violates graph validation, the adapter makes one corrective request
with the rejected JSON and validation error. A second invalid result fails the build rather than
weakening relationship constraints or silently dropping data.

`graph.json` is a derived local artifact. There is no graph database or vector index in the first
simplified release.

`graph.html` is also derived. It embeds the graph and the packaged Cytoscape.js runtime so viewing
architecture data requires neither a server nor an external network request. Filtering and visual
state remain presentation concerns and do not alter `graph.json`.
