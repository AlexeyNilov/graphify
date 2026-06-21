# Relationship-aware natural-language querying plan

## Goal

Make `graphify query` answer bounded natural-language questions about relationships in the local
architecture graph while preserving deterministic graph traversal and the existing closed schema.

For example:

```bash
graphify query "Which service uses the Orders Database?"
```

The command should identify `Orders Database` as the anchor entity, traverse incoming
`USES_DATABASE` relationships, and return the matching `Service` entities.

## Scope boundary

This feature is a constrained natural-language query planner, not general Graph RAG. The language
model translates a question into a validated graph operation. It does not answer from its own
knowledge, infer missing architecture facts, or generate relationships that are absent from
`graph.json`.

Initial questions should include:

- Which service uses the Orders Database?
- What does Web Store call?
- Who owns Order Service?
- Which services consume Order Submitted?
- Which team owns the service that uses Orders Database?
- Which services are affected by Commerce Event Bus?

## Query plan

Introduce a typed, validated query plan. A plan for the motivating question would be equivalent to:

```json
{
  "operation": "TRAVERSE",
  "anchor": {
    "name": "Orders Database",
    "type": "Database"
  },
  "steps": [
    {
      "relationship": "USES_DATABASE",
      "direction": "incoming",
      "result_type": "Service"
    }
  ]
}
```

The plan vocabulary must be restricted to Graphify's supported entity and relationship types.
Traversal direction must be explicit. Multiple steps allow bounded questions such as finding the
team that owns the service that uses a particular database.

An `ENTITY_SEARCH` operation should preserve existing searches such as:

```bash
graphify query "orders database"
```

## Data flow

```text
question
  -> structured query planner
  -> query plan validation
  -> deterministic entity resolution
  -> deterministic graph traversal
  -> matching graph entities
```

The configured OpenAI-compatible model is responsible only for producing the structured query
plan. Entity resolution, alias handling, traversal, filtering, and result ordering remain local and
deterministic.

## Entity resolution

The executor resolves plan anchors against entity IDs, canonical names, and aliases in
`graph.json`.

- A unique match becomes the traversal anchor.
- No match produces an actionable error naming the unresolved selector.
- Multiple matches produce an ambiguity error listing the candidate entity IDs.
- Type constraints narrow candidates but must not silently override contradictory graph data.

## Execution

Each traversal step specifies:

- A relationship from the closed relationship vocabulary.
- `outgoing` or `incoming` direction.
- An optional result entity type.

Execution starts from the resolved anchor set and applies steps in order. Results come only from
relationships present in the graph. Duplicate entities are removed, and final entities are sorted
by stable ID.

The `query` command should continue returning entity objects so existing callers that consume
successful search results retain the same output shape. The `path`, `affected`, and `inspect`
commands remain unchanged.

## Failure behavior

Graphify must distinguish these outcomes instead of representing all of them as an empty list:

- The planner does not support the question.
- The anchor entity cannot be resolved.
- The anchor is ambiguous.
- The model returns an invalid query plan.
- The plan is valid but traversal finds no matching entities.

Errors should identify the failed stage and suggest a usable entity name or a more specific
question where possible. A valid query with no graph results may still return `[]`.

## Testing strategy

Follow TDD and cover behavior rather than prompt implementation details.

1. A reverse relationship query returns the service using a named database.
2. A forward relationship query returns what a named service calls.
3. A multi-step query returns the team owning a service that uses a named database.
4. An alias resolves to its canonical entity.
5. An ambiguous entity name produces a clear error rather than selecting arbitrarily.
6. An unsupported question produces a clear planner error.
7. A valid traversal without matches returns an empty result.
8. A simple entity search retains the current behavior.
9. Invalid model output is rejected before graph execution.

Planner tests should inject fixed structured responses. Executor tests must not call a language
model or mock internal traversal logic.

## Implementation sequence

1. Add failing behavioral tests for direct, reverse, multi-step, alias, ambiguous, unsupported,
   empty-result, and entity-search queries.
2. Add typed query-plan structures and strict boundary validation.
3. Implement deterministic entity resolution and plan execution.
4. Add an injectable OpenAI-compatible planner that requests structured output.
5. Integrate planning and execution into `graphify query`.
6. Add actionable CLI error reporting and exit behavior.
7. Update `README.md` and `ARCHITECTURE.md` with the new query data flow and scope boundary.
8. Bump the minor project version to `1.2.0`.
9. Run `make format`, `make test`, `make lint`, and `make mypy`.

## Tradeoffs and deferred optimization

Natural-language questions require the configured model, so query latency and availability depend
on the OpenAI-compatible endpoint. The graph answer remains deterministic once a valid plan exists,
but plan generation can still fail.

A later optimization may recognize common relationship phrases locally before invoking the model.
That hybrid parser should be added only when measured query latency justifies the additional parsing
and consistency rules.
