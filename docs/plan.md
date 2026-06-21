# Simplified architecture knowledge graph plan

## First release

The simplified release is intentionally limited to these phases:

1. Use a closed architecture schema.
2. Read Markdown and OpenAPI 3.x documents from a local directory.
3. Represent corporate architecture entities rather than code symbols.
4. Extract Markdown facts with OpenAI using structured JSON.
5. Extract OpenAPI facts deterministically.
6. Normalize entity names and retain aliases.
7. Store numeric confidence and provenance on every relationship.
8. Support entity search, dependency paths, and reverse impact queries over local `graph.json`.
9. Generate a self-contained local viewer with semantic filters, entity inspection, confidence,
   and provenance.

The canonical types and relationships are documented in `README.md` and enforced in
`grach/schema.py`.

## Explicitly deferred

- Graph RAG and vector databases
- Neo4j, Memgraph, FalkorDB, or other remote graph stores
- Confluence and GitHub synchronization
- Continuous/watch-based refresh
- Terraform and Kubernetes extractors
- Non-OpenAI providers
- Non-Codex assistant integrations
- Saved viewer layouts and graph editing
- Path and impact highlighting in the viewer

Deferred features should be added only after a concrete use case demonstrates that the local graph
cannot answer the required architecture questions.
