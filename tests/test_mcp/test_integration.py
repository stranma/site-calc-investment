"""Integration tests for MCP server -- tests tools via the MCP protocol.

These tests use fastmcp's Client to call tools through the actual MCP protocol,
validating that tool registration, parameter serialization, and response
formatting all work correctly end-to-end.

For production integration tests (against live API), see test_mcp_production.py.
"""

import json
from typing import Any

import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError

from site_calc_investment.mcp import server as mcp_server
from site_calc_investment.mcp.scenario import ScenarioStore
from site_calc_investment.mcp.server import mcp


def _parse_result(result: Any) -> Any:
    """Extract parsed data from a CallToolResult."""
    if result.content:
        text = result.content[0].text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
    # FastMCP may use structured_content for empty collections
    if hasattr(result, "structured_content") and result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    return None


@pytest.fixture(autouse=True)
def reset_server_state() -> None:
    """Reset server-level state between tests."""
    mcp_server._store = ScenarioStore()
    mcp_server._client = None


@pytest_asyncio.fixture
async def client():
    """MCP client connected to the in-process server."""
    async with Client(mcp) as c:
        yield c


@pytest.mark.asyncio
async def test_list_tools(client: Client) -> None:
    """All 16 tools are registered and discoverable via MCP protocol."""
    tools = await client.list_tools()
    tool_names = {t.name for t in tools}
    expected = {
        "get_version",
        "create_scenario",
        "add_device",
        "set_timespan",
        "set_investment_params",
        "review_scenario",
        "remove_device",
        "delete_scenario",
        "list_scenarios",
        "submit_scenario",
        "get_job_status",
        "get_job_result",
        "cancel_job",
        "list_jobs",
        "get_device_schema",
        "save_data_file",
    }
    assert tool_names == expected, f"Missing tools: {expected - tool_names}, Extra: {tool_names - expected}"


@pytest.mark.asyncio
async def test_create_scenario_via_mcp(client: Client) -> None:
    """create_scenario returns scenario_id via MCP protocol."""
    result = await client.call_tool("create_scenario", {"name": "MCP Integration Test"})
    data = _parse_result(result)
    assert "scenario_id" in data
    assert data["scenario_id"].startswith("sc_")
    assert data["name"] == "MCP Integration Test"


@pytest.mark.asyncio
async def test_get_device_schema_via_mcp(client: Client) -> None:
    """get_device_schema returns valid schema via MCP protocol."""
    result = await client.call_tool("get_device_schema", {"device_type": "battery"})
    schema = _parse_result(result)
    assert schema["device_type"] == "battery"
    assert "capacity" in schema["properties"]
    assert schema["properties"]["capacity"]["required"] is True


@pytest.mark.asyncio
async def test_full_scenario_assembly_via_mcp(client: Client) -> None:
    """Full scenario assembly workflow via MCP protocol (no submission -- no API needed)."""
    # Create scenario
    data = _parse_result(await client.call_tool("create_scenario", {"name": "Full Assembly Test"}))
    sid = data["scenario_id"]

    # Set timespan
    text = _parse_result(await client.call_tool("set_timespan", {"scenario_id": sid, "start_year": 2025, "years": 1}))
    assert "8760" in str(text)

    # Add battery
    text = _parse_result(
        await client.call_tool(
            "add_device",
            {
                "scenario_id": sid,
                "device_type": "battery",
                "name": "Battery1",
                "properties": {"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
            },
        )
    )
    assert "10.0" in str(text)

    # Add grid import
    await client.call_tool(
        "add_device",
        {
            "scenario_id": sid,
            "device_type": "electricity_import",
            "name": "GridImport",
            "properties": {"price": 50.0, "max_import": 10.0},
        },
    )

    # Add grid export
    await client.call_tool(
        "add_device",
        {
            "scenario_id": sid,
            "device_type": "electricity_export",
            "name": "GridExport",
            "properties": {"price": 50.0, "max_export": 10.0},
        },
    )

    # Set investment params
    await client.call_tool(
        "set_investment_params",
        {
            "scenario_id": sid,
            "discount_rate": 0.05,
            "device_capital_costs": {"Battery1": 500000},
        },
    )

    # Review
    review = _parse_result(await client.call_tool("review_scenario", {"scenario_id": sid}))
    assert review["name"] == "Full Assembly Test"
    assert len(review["devices"]) == 3
    assert "Valid" in review["validation"]

    # List scenarios
    scenarios = _parse_result(await client.call_tool("list_scenarios", {}))
    assert any(s["id"] == sid for s in scenarios)

    # Remove a device
    text = _parse_result(await client.call_tool("remove_device", {"scenario_id": sid, "device_name": "GridExport"}))
    assert "Removed" in str(text)

    # Review again -- should have 2 devices
    review = _parse_result(await client.call_tool("review_scenario", {"scenario_id": sid}))
    assert len(review["devices"]) == 2

    # Delete scenario
    text = _parse_result(await client.call_tool("delete_scenario", {"scenario_id": sid}))
    assert "Deleted" in str(text)

    # List should be empty now
    scenarios = _parse_result(await client.call_tool("list_scenarios", {}))
    assert scenarios == []


@pytest.mark.asyncio
async def test_all_device_types_via_mcp(client: Client) -> None:
    """All 10 device types can be added via MCP protocol."""
    data = _parse_result(await client.call_tool("create_scenario", {"name": "All Devices Test"}))
    sid = data["scenario_id"]

    await client.call_tool("set_timespan", {"scenario_id": sid, "start_year": 2025, "years": 1})

    device_configs = [
        ("battery", "B1", {"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9}),
        ("chp", "CHP1", {"gas_input": 4.0, "el_output": 2.0, "heat_output": 1.5}),
        ("heat_accumulator", "HA1", {"capacity": 50.0, "max_power": 10.0, "efficiency": 0.95}),
        (
            "photovoltaic",
            "PV1",
            {
                "peak_power_mw": 5.0,
                "location": {"latitude": 50.07, "longitude": 14.44},
                "tilt": 35,
                "azimuth": 180,
            },
        ),
        ("electricity_import", "EI1", {"price": 50.0, "max_import": 10.0}),
        ("electricity_export", "EE1", {"price": 50.0, "max_export": 10.0}),
        ("gas_import", "GI1", {"price": 35.0, "max_import": 5.0}),
        ("heat_export", "HE1", {"price": 40.0, "max_export": 2.0}),
        ("electricity_demand", "ED1", {"max_demand_profile": 5.0}),
        ("heat_demand", "HD1", {"max_demand_profile": 3.0}),
    ]

    for dtype, name, props in device_configs:
        await client.call_tool(
            "add_device",
            {"scenario_id": sid, "device_type": dtype, "name": name, "properties": props},
        )

    review = _parse_result(await client.call_tool("review_scenario", {"scenario_id": sid}))
    assert len(review["devices"]) == 10
    assert "Valid" in review["validation"]


@pytest.mark.asyncio
async def test_save_data_file_via_mcp(client: Client, tmp_path: object) -> None:
    """save_data_file writes CSV and returns metadata via MCP protocol."""
    import pathlib
    from unittest.mock import patch

    out = pathlib.Path(str(tmp_path)) / "mcp_save_test.csv"
    with patch("site_calc_investment.mcp.server.get_data_dir", return_value=None):
        result = await client.call_tool(
            "save_data_file",
            {
                "file_path": str(out),
                "columns": {"hour": [0.0, 1.0, 2.0], "price_eur": [30.5, 42.1, 55.0]},
            },
        )
    data = _parse_result(result)
    assert data["rows"] == 3
    assert data["columns"] == ["hour", "price_eur"]
    assert pathlib.Path(data["file_path"]).exists()


@pytest.mark.asyncio
async def test_error_handling_via_mcp(client: Client) -> None:
    """Errors are propagated correctly through MCP protocol."""
    # Unknown device type -- returns error in data, not an MCP error
    result = await client.call_tool("get_device_schema", {"device_type": "fusion_reactor"})
    data = _parse_result(result)
    assert "error" in data

    # Nonexistent scenario -- FastMCP Client raises ToolError
    with pytest.raises(ToolError, match="not found"):
        await client.call_tool("review_scenario", {"scenario_id": "sc_nonexistent"})
