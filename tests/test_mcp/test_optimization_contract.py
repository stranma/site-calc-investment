"""MCP controls and certificates through the public HTTP client, without a solver."""

import copy
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from site_calc_investment.api.client import InvestmentClient
from site_calc_investment.mcp import server
from site_calc_investment.mcp.scenario import ScenarioStore

Wire = tuple[list[httpx.Request], dict[str, Any]]

CERTIFICATE = {
    "objective_lower_bound": -125.0,
    "objective_upper_bound": -100.0,
    "absolute_gap": 25.0,
    "requested_strategy": "auto",
    "used_strategy": "monolithic",
    "fallback_reason": "Requested model is unsupported by decomposed strategy",
    "soc_boundary_policy": "monthly_fixed",
    "elapsed_time_seconds": 12.0,
}


@pytest.fixture
def ready_scenario(monkeypatch: pytest.MonkeyPatch) -> str:
    store = ScenarioStore()
    monkeypatch.setattr(server, "_store", store)
    scenario_id = store.create(name="Contract test")
    store.set_timespan(scenario_id, start_year=2025, intervals=1)
    store.add_device(
        scenario_id,
        device_type="electricity_import",
        name="Grid",
        properties={"price": 50.0, "max_import": 1.0},
    )
    return scenario_id


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch, mock_result_response: dict) -> Iterator[Wire]:
    """Use real client serialization with an in-memory HTTP transport."""
    calls: list[httpx.Request] = []
    response = copy.deepcopy(mock_result_response)

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "contract_job", "status": "pending"})
        return httpx.Response(200, json=response)

    with InvestmentClient("https://api.example.com", "inv_test") as client:
        client._client.close()
        client._client = httpx.Client(base_url=client.base_url, transport=httpx.MockTransport(handle))
        monkeypatch.setattr(server, "_client", client)
        yield calls, response


def parsed(result: Any) -> dict:
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options,expected",
    [
        ({}, {"mip_gap": 0.01}),
        ({"mip_gap": 0.01}, {"mip_gap": 0.01}),
        ({"abs_gap": 25.0}, {"mip_gap": 0.01, "abs_gap": 25.0}),
        ({"mip_gap": None}, {}),
        ({"strategy": None, "abs_gap": None, "soc_boundary_policy": None, "mip_gap": None}, {}),
        (
            {"strategy": "auto", "soc_boundary_policy": "monthly_fixed"},
            {"strategy": "auto", "soc_boundary_policy": "monthly_fixed", "mip_gap": 0.01},
        ),
        (
            {"strategy": "decomposed", "soc_boundary_policy": "monthly_fixed", "mip_gap": None, "abs_gap": 0.0},
            {"strategy": "decomposed", "soc_boundary_policy": "monthly_fixed", "abs_gap": 0.0},
        ),
        (
            {"strategy": "monolithic", "soc_boundary_policy": "preserve", "mip_gap": 0.0, "abs_gap": 25.0},
            {"strategy": "monolithic", "soc_boundary_policy": "preserve", "mip_gap": 0.0, "abs_gap": 25.0},
        ),
    ],
)
async def test_submit_controls_reach_http_payload(
    ready_scenario: str, wire: Wire, options: dict, expected: dict
) -> None:
    calls, _ = wire
    async with Client(server.mcp) as client:
        result = parsed(await client.call_tool("submit_scenario", {"scenario_id": ready_scenario, **options}))
    assert result == {"job_id": "contract_job", "status": "pending"}
    assert len(calls) == 1
    assert calls[0].method == "POST" and calls[0].url.path == "/api/v1/jobs/device-planning"
    assert json.loads(calls[0].content)["optimization_config"] == {
        "objective": "maximize_profit",
        "time_limit_seconds": 300,
        "relax_binary_variables": True,
        **expected,
    }
    assert server._store.get(ready_scenario).jobs == ["contract_job"]


@pytest.mark.asyncio
async def test_submission_schema_keeps_new_controls_optional() -> None:
    async with Client(server.mcp) as client:
        tool = next(tool for tool in await client.list_tools() if tool.name == "submit_scenario")
    assert tool.inputSchema["required"] == ["scenario_id"]
    fields = tool.inputSchema["properties"]
    assert fields["mip_gap"]["default"] == 0.01
    for name in ("strategy", "abs_gap", "soc_boundary_policy"):
        assert fields[name]["default"] is None
        assert {"type": "null"} in fields[name]["anyOf"]
    assert {"type": "null"} in fields["mip_gap"]["anyOf"]


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [{"strategy": "invalid"}, {"soc_boundary_policy": "invalid"}, {"abs_gap": -1}])
async def test_invalid_controls_do_not_submit(ready_scenario: str, wire: Wire, options: dict) -> None:
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("submit_scenario", {"scenario_id": ready_scenario, **options})
    assert wire[0] == []
    assert server._store.get(ready_scenario).jobs == []


@pytest.mark.parametrize("field", ["mip_gap", "abs_gap"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_builder_rejects_nonfinite_tolerances(ready_scenario: str, field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        server._store.build_request(ready_scenario, **{field: value})


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["summary", "monthly", "full"])
@pytest.mark.parametrize("certificate_state", ["present", "missing", "null"])
async def test_all_detail_levels_preserve_certificates(wire: Wire, level: str, certificate_state: str) -> None:
    calls, response = wire
    response_summary = response["result"]["summary"]
    if certificate_state == "present":
        response_summary.update(
            CERTIFICATE,
            is_optimal=True,
            termination_reason="time_limit",
            optimality_gap=0.2,
        )
    elif certificate_state == "null":
        response_summary.update(dict.fromkeys(CERTIFICATE))
    async with Client(server.mcp) as client:
        result = parsed(await client.call_tool("get_job_result", {"job_id": "contract_job", "detail_level": level}))
    assert len(calls) == 1
    assert calls[0].url.path == "/api/v1/jobs/contract_job/result"
    summary = result["summary"]
    expected = CERTIFICATE if certificate_state == "present" else dict.fromkeys(CERTIFICATE)
    assert {key: summary[key] for key in CERTIFICATE} == expected
    assert summary["solve_time_seconds"] == response_summary["solve_time_seconds"]
    assert summary["solver_status"] == response_summary["solver_status"]
    assert summary["is_optimal"] is (True if certificate_state == "present" else None)
    assert summary["termination_reason"] == ("time_limit" if certificate_state == "present" else None)
    assert "warning" not in summary
    assert all(not isinstance(value, (dict, list)) for value in summary.values())


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["summary", "monthly", "full"])
async def test_uncertified_result_warns_without_inventing_bounds(wire: Wire, level: str) -> None:
    _, response = wire
    response["result"]["summary"].update(is_optimal=False, termination_reason="time_limit")
    async with Client(server.mcp) as client:
        result = parsed(await client.call_tool("get_job_result", {"job_id": "contract_job", "detail_level": level}))
    summary = result["summary"]
    assert all(summary[name] is None for name in CERTIFICATE)
    assert summary["is_optimal"] is False
    assert "not certified" in summary["warning"]
    assert "neither guarantees" in summary["warning"]
