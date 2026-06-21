from __future__ import annotations

import pytest

from grach.query_executor import (
    AmbiguousEntityError,
    EntityNotFoundError,
    InvalidQueryPlanError,
    UnsupportedQueryError,
    execute_query_plan,
    validate_query_plan,
)
from grach.schema import ArchitectureGraph


def _graph() -> ArchitectureGraph:
    return {
        "schema_version": "1.0",
        "entities": [
            {
                "id": "service:web-store",
                "name": "Web Store",
                "type": "Service",
                "aliases": ["WebStore"],
            },
            {
                "id": "service:order-service",
                "name": "Order Service",
                "type": "Service",
                "aliases": ["OrderSvc"],
            },
            {"id": "service:checkout", "name": "Checkout", "type": "Service"},
            {
                "id": "database:orders-database",
                "name": "Orders Database",
                "type": "Database",
                "aliases": ["orders-db"],
            },
            {"id": "team:commerce", "name": "Commerce", "type": "Team"},
            {"id": "event:orders", "name": "Orders", "type": "Event"},
            {"id": "service:orders", "name": "Orders", "type": "Service"},
        ],
        "relationships": [
            {
                "source": "service:web-store",
                "type": "CALLS",
                "target": "service:order-service",
                "confidence": 1.0,
                "provenance": {
                    "source_file": "architecture.md",
                    "source_location": "Web Store",
                    "method": "openai",
                },
            },
            {
                "source": "service:checkout",
                "type": "CALLS",
                "target": "service:order-service",
                "confidence": 1.0,
                "provenance": {
                    "source_file": "architecture.md",
                    "source_location": "Checkout",
                    "method": "openai",
                },
            },
            {
                "source": "service:order-service",
                "type": "USES_DATABASE",
                "target": "database:orders-database",
                "confidence": 1.0,
                "provenance": {
                    "source_file": "architecture.md",
                    "source_location": "Order Service",
                    "method": "openai",
                },
            },
            {
                "source": "service:order-service",
                "type": "OWNED_BY",
                "target": "team:commerce",
                "confidence": 1.0,
                "provenance": {
                    "source_file": "architecture.md",
                    "source_location": "Order Service",
                    "method": "openai",
                },
            },
            {
                "source": "service:order-service",
                "type": "CALLS",
                "target": "service:web-store",
                "confidence": 1.0,
                "provenance": {
                    "source_file": "architecture.md",
                    "source_location": "Order Service",
                    "method": "openai",
                },
            },
        ],
    }


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        ({"operation": "UNKNOWN"}, "unsupported query operation"),
        ({"operation": "ENTITY_SEARCH", "selector": {}}, "exactly one of id or name"),
        (
            {
                "operation": "TRAVERSE",
                "anchor": {"id": "service:web-store", "name": "Web Store"},
                "steps": [{"relationship": "CALLS", "direction": "outgoing"}],
            },
            "exactly one of id or name",
        ),
        (
            {
                "operation": "TRAVERSE",
                "anchor": {"name": "Web Store"},
                "steps": [{"relationship": "UNKNOWN", "direction": "outgoing"}],
            },
            "unsupported relationship type",
        ),
        (
            {
                "operation": "TRAVERSE",
                "anchor": {"name": "Web Store"},
                "steps": [{"relationship": "CALLS", "direction": "sideways"}],
            },
            "direction must be incoming or outgoing",
        ),
        (
            {"operation": "TRAVERSE", "anchor": {"name": "Web Store"}, "steps": []},
            "between 1 and 6",
        ),
        (
            {
                "operation": "TRAVERSE",
                "anchor": {"name": "Web Store", "type": ["Service"]},
                "steps": [{"relationship": "CALLS", "direction": "outgoing"}],
            },
            "unsupported entity type",
        ),
        (
            {
                "operation": "ENTITY_SEARCH",
                "selector": {"name": "Orders"},
                "extra": True,
            },
            "unexpected fields",
        ),
    ],
)
def test_query_plan_validation_rejects_invalid_boundary_data(
    plan: dict[str, object], message: str
) -> None:
    with pytest.raises(InvalidQueryPlanError, match=message):
        validate_query_plan(plan)


def test_entity_search_plan_resolves_a_typed_alias() -> None:
    results = execute_query_plan(
        _graph(),
        {
            "operation": "ENTITY_SEARCH",
            "selector": {"name": "orders-db", "type": "Database"},
        },
    )

    assert [entity["id"] for entity in results] == ["database:orders-database"]


def test_unsupported_plan_reports_why_the_question_cannot_be_executed() -> None:
    plan = {"operation": "UNSUPPORTED", "reason": "The question asks for deployment cost."}

    with pytest.raises(UnsupportedQueryError, match="deployment cost"):
        execute_query_plan(_graph(), plan)


def test_incoming_traversal_returns_entities_that_use_named_database() -> None:
    plan = {
        "operation": "TRAVERSE",
        "anchor": {"name": "orders-db", "type": "Database"},
        "steps": [
            {
                "relationship": "USES_DATABASE",
                "direction": "incoming",
                "result_type": "Service",
            }
        ],
    }

    assert [entity["id"] for entity in execute_query_plan(_graph(), plan)] == [
        "service:order-service"
    ]


def test_multi_step_traversal_applies_steps_in_order() -> None:
    plan = {
        "operation": "TRAVERSE",
        "anchor": {"id": "database:orders-database"},
        "steps": [
            {"relationship": "USES_DATABASE", "direction": "incoming"},
            {
                "relationship": "OWNED_BY",
                "direction": "outgoing",
                "result_type": "Team",
            },
        ],
    }

    assert [entity["id"] for entity in execute_query_plan(_graph(), plan)] == ["team:commerce"]


def test_traversal_respects_direction_and_returns_empty_for_no_edges() -> None:
    plan = {
        "operation": "TRAVERSE",
        "anchor": {"name": "Orders Database", "type": "Database"},
        "steps": [{"relationship": "USES_DATABASE", "direction": "outgoing"}],
    }

    assert execute_query_plan(_graph(), plan) == []


def test_traversal_returns_multiple_entities_in_stable_id_order() -> None:
    plan = {
        "operation": "TRAVERSE",
        "anchor": {"name": "Order Service"},
        "steps": [{"relationship": "CALLS", "direction": "incoming"}],
    }

    assert [entity["id"] for entity in execute_query_plan(_graph(), plan)] == [
        "service:checkout",
        "service:web-store",
    ]


def test_traversal_deduplicates_cycle_results_and_sorts_by_id() -> None:
    plan = {
        "operation": "TRAVERSE",
        "anchor": {"name": "Order Service", "type": "Service"},
        "steps": [
            {"relationship": "CALLS", "direction": "outgoing"},
            {"relationship": "CALLS", "direction": "outgoing"},
        ],
    }

    assert [entity["id"] for entity in execute_query_plan(_graph(), plan)] == [
        "service:order-service"
    ]


def test_ambiguous_name_reports_candidate_ids() -> None:
    plan = {
        "operation": "TRAVERSE",
        "anchor": {"name": "Orders"},
        "steps": [{"relationship": "CALLS", "direction": "outgoing"}],
    }

    with pytest.raises(AmbiguousEntityError) as error:
        execute_query_plan(_graph(), plan)

    assert error.value.candidate_ids == ("event:orders", "service:orders")


def test_type_constraint_resolves_otherwise_ambiguous_name() -> None:
    plan = {
        "operation": "TRAVERSE",
        "anchor": {"name": "Orders", "type": "Service"},
        "steps": [{"relationship": "CALLS", "direction": "outgoing"}],
    }

    assert execute_query_plan(_graph(), plan) == []


def test_missing_entity_reports_selector() -> None:
    plan = {
        "operation": "TRAVERSE",
        "anchor": {"name": "Missing Service", "type": "Service"},
        "steps": [{"relationship": "CALLS", "direction": "outgoing"}],
    }

    with pytest.raises(EntityNotFoundError, match="Missing Service"):
        execute_query_plan(_graph(), plan)
