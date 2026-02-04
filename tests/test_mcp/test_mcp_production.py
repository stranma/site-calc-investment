"""Production integration tests for MCP server against a live API.

Requires environment variables:
- INVESTMENT_API_URL: Base URL of the API
- INVESTMENT_API_KEY: API key with 'inv_' prefix

Tests are skipped if credentials are not available.

IMPORTANT: Large tasks are created and immediately cancelled to minimize costs.
"""

import os
import time

import pytest

from site_calc_investment.mcp import server as mcp_server
from site_calc_investment.mcp.scenario import ScenarioStore


def _credentials_available() -> bool:
    return bool(os.environ.get("INVESTMENT_API_URL") and os.environ.get("INVESTMENT_API_KEY"))


pytestmark = [
    pytest.mark.production,
    pytest.mark.skipif(not _credentials_available(), reason="Production API credentials not available"),
]


@pytest.fixture(autouse=True)
def reset_server_state() -> None:
    """Reset server-level state between tests."""
    mcp_server._store = ScenarioStore()
    mcp_server._client = None


@pytest.fixture
def scenario_with_battery() -> str:
    """Create a scenario with a battery and grid connections, ready to submit."""
    sc = mcp_server.create_scenario(name="Production MCP Test")
    sid = sc["scenario_id"]
    mcp_server.set_timespan(scenario_id=sid, start_year=2025, years=0)
    # Use a 4-hour horizon (minimal cost)
    mcp_server._store.get(sid).timespan.years = 0
    # Manually set a tiny timespan for cost reasons
    from site_calc_investment.mcp.scenario import TimespanConfig

    mcp_server._store.get(sid).timespan = TimespanConfig(start_year=2025, years=1)

    mcp_server.add_device(
        scenario_id=sid,
        device_type="battery",
        name="Battery1",
        properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.90, "initial_soc": 0.5},
    )
    mcp_server.add_device(
        scenario_id=sid,
        device_type="electricity_import",
        name="GridImport",
        properties={"price": 50.0, "max_import": 10.0},
    )
    mcp_server.add_device(
        scenario_id=sid,
        device_type="electricity_export",
        name="GridExport",
        properties={"price": 50.0, "max_export": 10.0},
    )
    return sid


class TestMCPProductionSubmit:
    """Test scenario submission through MCP tools against live API."""

    def test_submit_and_get_result(self, scenario_with_battery: str) -> None:
        """Submit via MCP tools, wait for completion, get result."""
        sid = scenario_with_battery

        # Review before submit
        review = mcp_server.review_scenario(scenario_id=sid)
        assert "Valid" in review["validation"]

        # Submit
        submit_result = mcp_server.submit_scenario(scenario_id=sid, objective="maximize_profit")
        job_id = submit_result["job_id"]
        assert submit_result["status"] in ("pending", "running", "completed")

        # Poll until completion
        for _ in range(60):
            status = mcp_server.get_job_status(job_id=job_id)
            if status["status"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(5)

        assert status["status"] == "completed", f"Job did not complete: {status}"

        # Get result at summary level
        result = mcp_server.get_job_result(job_id=job_id, detail_level="summary")
        assert result["status"] == "completed"
        assert result["summary"]["solver_status"].lower() == "optimal"
        assert result["summary"]["expected_profit"] is not None

    def test_submit_and_cancel(self, scenario_with_battery: str) -> None:
        """Submit a job and cancel it immediately."""
        sid = scenario_with_battery
        submit_result = mcp_server.submit_scenario(scenario_id=sid)
        job_id = submit_result["job_id"]

        cancel_result = mcp_server.cancel_job(job_id=job_id)
        assert cancel_result["status"] == "cancelled"

    def test_list_jobs_after_submit(self, scenario_with_battery: str) -> None:
        """list_jobs returns submitted job IDs."""
        sid = scenario_with_battery
        submit_result = mcp_server.submit_scenario(scenario_id=sid)
        job_id = submit_result["job_id"]

        jobs = mcp_server.list_jobs()
        assert len(jobs) == 1
        assert job_id in jobs[0]["job_ids"]

        # Cleanup
        mcp_server.cancel_job(job_id=job_id)

    def test_scenario_resubmit(self, scenario_with_battery: str) -> None:
        """Scenario can be modified and resubmitted."""
        sid = scenario_with_battery

        # First submit
        result1 = mcp_server.submit_scenario(scenario_id=sid)
        mcp_server.cancel_job(job_id=result1["job_id"])

        # Add a CHP and resubmit
        mcp_server.add_device(
            scenario_id=sid,
            device_type="chp",
            name="CHP1",
            properties={"gas_input": 4.0, "el_output": 2.0, "heat_output": 1.5},
        )
        mcp_server.add_device(
            scenario_id=sid,
            device_type="gas_import",
            name="Gas",
            properties={"price": 35.0, "max_import": 5.0},
        )
        mcp_server.add_device(
            scenario_id=sid,
            device_type="heat_export",
            name="Heat",
            properties={"price": 40.0, "max_export": 2.0},
        )

        result2 = mcp_server.submit_scenario(scenario_id=sid)
        assert result2["job_id"] != result1["job_id"]

        # Cleanup
        mcp_server.cancel_job(job_id=result2["job_id"])

        # Verify both jobs are tracked
        scenario = mcp_server._store.get(sid)
        assert len(scenario.jobs) == 2


class TestMCPProductionResultLevels:
    """Test different result detail levels against live API."""

    def test_monthly_detail_level(self, scenario_with_battery: str) -> None:
        """Get result with monthly breakdown."""
        sid = scenario_with_battery
        submit_result = mcp_server.submit_scenario(scenario_id=sid)
        job_id = submit_result["job_id"]

        for _ in range(60):
            status = mcp_server.get_job_status(job_id=job_id)
            if status["status"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(5)

        if status["status"] != "completed":
            pytest.skip("Job did not complete in time")

        result = mcp_server.get_job_result(job_id=job_id, detail_level="monthly")
        assert "device_summaries" in result
        assert "Battery1" in result["device_summaries"]
        battery_summary = result["device_summaries"]["Battery1"]
        assert "monthly" in battery_summary
        assert len(battery_summary["monthly"]) == 12
