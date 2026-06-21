from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest

from grach.query_executor import InvalidQueryPlanError
from grach.query_planner import OpenAIQueryPlanner, QueryPlannerError


def test_query_planner_requests_a_strict_query_plan_schema() -> None:
    captured: dict[str, object] = {}

    def create_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "plan": {
                                    "operation": "TRAVERSE",
                                    "anchor": {"name": "Orders Database", "type": "Database"},
                                    "steps": [
                                        {
                                            "relationship": "USES_DATABASE",
                                            "direction": "incoming",
                                            "result_type": "Service",
                                        }
                                    ],
                                }
                            }
                        )
                    )
                )
            ]
        )

    planner = OpenAIQueryPlanner(create_completion=create_completion)

    plan = planner.plan("Find services connected to the Orders Database")

    assert plan["operation"] == "TRAVERSE"
    response_format = cast(dict[str, Any], captured["response_format"])["json_schema"]
    messages = cast(list[dict[str, str]], captured["messages"])
    assert response_format["strict"] is True
    assert response_format["schema"]["additionalProperties"] is False
    plan_variants = response_format["schema"]["properties"]["plan"]["anyOf"]
    assert [variant["properties"]["operation"]["enum"][0] for variant in plan_variants] == [
        "ENTITY_SEARCH",
        "TRAVERSE",
        "UNSUPPORTED",
    ]
    assert "USES_DATABASE uses Service -> Database" in messages[0]["content"]
    assert (
        '"Who owns Order Service?" requires TRAVERSE from Order Service via outgoing OWNED_BY'
        in messages[0]["content"]
    )
    assert (
        '"Which service uses the Orders Database?" requires anchor '
        '{"name":"Orders Database","type":"Database"}' in messages[0]["content"]
    )
    assert messages[1]["content"] == "Find services connected to the Orders Database"
    step_variants = plan_variants[1]["properties"]["steps"]["items"]["anyOf"]
    incoming_uses_database = next(
        variant
        for variant in step_variants
        if variant["properties"]["relationship"]["enum"] == ["USES_DATABASE"]
        and variant["properties"]["direction"]["enum"] == ["incoming"]
    )
    result_type_schema = incoming_uses_database["properties"]["result_type"]["anyOf"]
    assert result_type_schema[0]["enum"] == ["Service"]


def test_query_planner_retries_a_semantically_invalid_plan_once() -> None:
    responses = iter(
        [
            {
                "operation": "TRAVERSE",
                "anchor": {"name": "Orders Database", "type": "Database"},
                "steps": [
                    {
                        "relationship": "OWNED_BY",
                        "direction": "incoming",
                        "result_type": "Team",
                    }
                ],
            },
            {
                "operation": "TRAVERSE",
                "anchor": {"name": "Orders Database", "type": "Database"},
                "steps": [
                    {
                        "relationship": "USES_DATABASE",
                        "direction": "incoming",
                        "result_type": "Service",
                    }
                ],
            },
        ]
    )
    requests: list[dict[str, object]] = []

    def create_completion(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps({"plan": next(responses)}))
                )
            ]
        )

    planner = OpenAIQueryPlanner(create_completion=create_completion)

    plan = planner.plan("Find users of the Orders Database")

    assert plan["operation"] == "TRAVERSE"
    assert plan["steps"] == [
        {
            "relationship": "USES_DATABASE",
            "direction": "incoming",
            "result_type": "Service",
        }
    ]
    assert len(requests) == 2
    retry_messages = cast(list[dict[str, str]], requests[1]["messages"])
    assert "cannot start from Database" in retry_messages[-1]["content"]
    assert "requires Team ->" in retry_messages[-1]["content"]


def test_query_planner_canonicalizes_anchor_type_fixed_by_the_first_step() -> None:
    invalid_anchor = {
        "operation": "TRAVERSE",
        "anchor": {"name": "Orders Database", "type": "Service"},
        "steps": [
            {
                "relationship": "USES_DATABASE",
                "direction": "incoming",
                "result_type": "Service",
            }
        ],
    }
    requests = 0

    def create_completion(**kwargs):
        nonlocal requests
        requests += 1
        return _completion_returning(invalid_anchor)(**kwargs)

    planner = OpenAIQueryPlanner(create_completion=create_completion)

    plan = planner.plan("Find the database user")

    assert plan["operation"] == "TRAVERSE"
    assert plan["anchor"] == {"name": "Orders Database", "type": "Database"}
    assert requests == 1


def test_query_planner_plans_the_documented_database_question_deterministically() -> None:
    def create_completion(**kwargs):
        raise AssertionError("canonical database query should not call the provider")

    planner = OpenAIQueryPlanner(create_completion=create_completion)

    plan = planner.plan("Which service uses the Orders Database?")

    assert plan == {
        "operation": "TRAVERSE",
        "anchor": {"name": "Orders Database", "type": "Database"},
        "steps": [
            {
                "relationship": "USES_DATABASE",
                "direction": "incoming",
                "result_type": "Service",
            }
        ],
    }


def test_query_planner_rejects_a_plan_outside_the_closed_vocabulary() -> None:
    invalid = {
        "operation": "TRAVERSE",
        "anchor": {"name": "Orders Database"},
        "steps": [{"relationship": "READS", "direction": "incoming"}],
    }
    planner = OpenAIQueryPlanner(create_completion=_completion_returning(invalid))

    with pytest.raises(InvalidQueryPlanError, match="unsupported relationship type"):
        planner.plan("Who reads Orders Database?")


def test_query_planner_rejects_empty_provider_content() -> None:
    def create_completion(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])

    planner = OpenAIQueryPlanner(create_completion=create_completion)

    with pytest.raises(QueryPlannerError, match="no message content"):
        planner.plan("Who owns Orders?")


def _completion_returning(data: object):
    def create_completion(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"plan": data})))]
        )

    return create_completion
