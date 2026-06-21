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

    plan = planner.plan("Which service uses the Orders Database?")

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
    assert messages[1]["content"] == "Which service uses the Orders Database?"


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
