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
| `query_executor.py` | Runtime query-plan validation, entity resolution, and typed traversal |
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

Typed query execution is deterministic and local:

```text
validated query plan -> resolve one anchor -> apply typed directional steps -> sorted entities
```

`ENTITY_SEARCH` plans preserve the existing entity search behavior. `TRAVERSE` plans use only
relationships present in `graph.json`; each step names a relationship type, direction, and optional
result entity type. Query-plan validation rejects unsupported vocabulary, ambiguous anchors are
reported rather than selected arbitrarily, and a valid traversal with no matches returns an empty
list. Natural-language planning and CLI integration are separate concerns and are not part of the
executor.

`graph.html` is also derived. It embeds the graph and the packaged Cytoscape.js runtime so viewing
architecture data requires neither a server nor an external network request. Filtering and visual
state remain presentation concerns and do not alter `graph.json`.
