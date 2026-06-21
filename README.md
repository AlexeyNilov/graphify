# Graphify

Graphify builds a local corporate architecture knowledge graph from two source types:

- OpenAPI 3.x JSON or YAML, parsed deterministically
- Markdown, interpreted with OpenAI

The result is `graphify-out/graph.json`. Graphify intentionally does not provide general code
analysis, multiple LLM providers, graph databases, vector search, or non-Codex integrations.

## Install

```bash
python -m pip install -e ".[dev]"
export OPENAI_API_KEY="..."
```

`GRAPHIFY_OPENAI_MODEL` optionally overrides the default `gpt-4.1-mini` model.

## Use

```bash
graphify build ./architecture
graphify query "orders database"
graphify path api:orders-api endpoint:create-order
graphify affected database:orders
graphify inspect service:order-service
```

Install the project-local Codex skill with:

```bash
graphify codex install
```

## Graph schema

Entity types are `Service`, `Database`, `API`, `Endpoint`, `Event`, `Team`, `Document`, and
`Infrastructure`.

Relationship types are `CALLS`, `USES_DATABASE`, `PUBLISHES`, `CONSUMES`, `DEPLOYED_TO`,
`OWNED_BY`, `DESCRIBED_IN`, `DEPENDS_ON`, `EXPOSES`, `GENERATES`, and `RECEIVES`.

Every relationship records numeric confidence and provenance containing its source file,
source location, and extraction method. IDs are stable, typed slugs such as
`service:order-service`.

## Development

```bash
make test
make format
make lint
make mypy
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the data flow and [docs/plan.md](docs/plan.md) for the
scope boundary.
