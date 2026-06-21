# Grach

Grach (GRaph ArCHitecture) builds a local corporate architecture knowledge graph from two source
types:

- OpenAPI 3.x JSON or YAML, parsed deterministically
- Markdown, interpreted with OpenAI

The result is `grach-out/graph.json`. Grach intentionally does not provide general code
analysis, multiple LLM providers, graph databases, vector search, or non-Codex integrations.

## Install

```bash
python -m pip install -e ".[dev]"
export OPENAI_API_KEY="key"
export OPENAI_BASE_URL="http://127.0.0.1:1234/v1"
export OPENAI_MODEL="google/gemma-4-12b-qat"
```

These settings point Grach at LM Studio's OpenAI-compatible API. Start the local server and
load the configured model before building a graph. When `OPENAI_BASE_URL` and `OPENAI_MODEL` are
unset, the OpenAI SDK endpoint and `gpt-4.1-mini` are used.

## Use

```bash
grach build ./architecture
grach query "Which service uses the Orders Database?"
grach query "Who owns Order Service?"
grach path api:orders-api endpoint:create-order
grach affected database:orders-database
grach inspect service:order-service
grach view
```

`grach query` sends the question, but not `graph.json`, to the configured OpenAI-compatible model.
The model returns a typed query plan; Grach validates that plan and executes it deterministically
against the local graph. Successful output contains both the plan and the matching entities:

```json
{
  "plan": {
    "operation": "TRAVERSE",
    "anchor": {"name": "Order Service", "type": "Service"},
    "steps": [
      {
        "relationship": "OWNED_BY",
        "direction": "outgoing",
        "result_type": "Team"
      }
    ]
  },
  "entities": [{"id": "team:commerce-team", "name": "Commerce Team", "type": "Team"}]
}
```

Relationship questions use typed, directional traversal. Unsupported questions, invalid plans,
missing anchors, and ambiguous anchors fail explicitly instead of returning a guessed result.
Explicit Mermaid edges labeled `owns` are extracted deterministically so ownership queries do not
depend on the model reproducing those diagram edges.

`grach view` writes `grach-out/graph.html`, a self-contained interactive viewer that works
offline. Its presets separate runtime dependencies, event flows, ownership, deployment, and API
surface views. Entity and relationship filters, confidence filtering, search, selection, and the
details panel expose the graph's metadata and relationship provenance without changing
`graph.json`.

For a fast, easy-to-read extraction example, run:

```bash
grach build examples/architecture-simple
```

The [Simple Order System](examples/architecture-simple/order-system.md) contains four entities and
four explicit relationships.

For a comprehensive extraction input containing every supported entity and relationship type, run:

```bash
grach build examples/architecture
```

The fictional [Atlas Commerce Platform](examples/architecture/complex-commerce-platform.md)
includes aliases, synchronous calls, event flows, deployment topology, ownership, and operational
dependencies.

Install the project-local Codex skill with:

```bash
grach codex install
```

## Development

```bash
make test
make format
make lint
make mypy
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the data flow and [grach/schema.py](grach/schema.py)
for the authoritative graph schema.
