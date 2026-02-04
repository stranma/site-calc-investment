"""Tests for MCP tool integration — end-to-end tool calls with mocked client."""

import os
from unittest.mock import MagicMock, patch

import pytest

from site_calc_investment.mcp import server as mcp_server
from site_calc_investment.mcp.scenario import ScenarioStore
from site_calc_investment.models.responses import Job


@pytest.fixture(autouse=True)
def reset_server_state() -> None:
    """Reset server-level state between tests."""
    mcp_server._store = ScenarioStore()
    mcp_server._client = None


class TestCreateScenario:
    """Tests for create_scenario tool."""

    def test_create_returns_id_and_name(self) -> None:
        result = mcp_server.create_scenario(name="Test Scenario")
        assert "scenario_id" in result
        assert result["name"] == "Test Scenario"
        assert result["scenario_id"].startswith("sc_")

    def test_create_with_description(self) -> None:
        result = mcp_server.create_scenario(name="Test", description="A description")
        scenario = mcp_server._store.get(result["scenario_id"])
        assert scenario.description == "A description"


class TestAddDevice:
    """Tests for add_device tool."""

    def test_add_battery(self) -> None:
        sc = mcp_server.create_scenario(name="Test")
        sid = sc["scenario_id"]
        mcp_server.set_timespan(scenario_id=sid, start_year=2025)
        result = mcp_server.add_device(
            scenario_id=sid,
            device_type="battery",
            name="Bat1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        assert isinstance(result, str)
        assert "10.0" in result

    def test_add_invalid_device_type(self) -> None:
        sc = mcp_server.create_scenario(name="Test")
        with pytest.raises(ValueError, match="Unknown device type"):
            mcp_server.add_device(
                scenario_id=sc["scenario_id"],
                device_type="wind_turbine",
                name="W1",
                properties={},
            )


class TestSetTimespan:
    """Tests for set_timespan tool."""

    def test_set_timespan(self) -> None:
        sc = mcp_server.create_scenario(name="Test")
        result = mcp_server.set_timespan(scenario_id=sc["scenario_id"], start_year=2025, years=1)
        assert "8760" in result
        assert "2025" in result


class TestSetInvestmentParams:
    """Tests for set_investment_params tool."""

    def test_set_params(self) -> None:
        sc = mcp_server.create_scenario(name="Test")
        result = mcp_server.set_investment_params(
            scenario_id=sc["scenario_id"],
            discount_rate=0.08,
            device_capital_costs={"B1": 500000},
        )
        assert "8.0%" in result
        assert "500,000" in result


class TestReviewScenario:
    """Tests for review_scenario tool."""

    def test_review_valid(self) -> None:
        sc = mcp_server.create_scenario(name="Test")
        sid = sc["scenario_id"]
        mcp_server.set_timespan(scenario_id=sid, start_year=2025)
        mcp_server.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        review = mcp_server.review_scenario(scenario_id=sid)
        assert review["name"] == "Test"
        assert "Valid" in review["validation"]
        assert len(review["devices"]) == 1


class TestRemoveDevice:
    """Tests for remove_device tool."""

    def test_remove(self) -> None:
        sc = mcp_server.create_scenario(name="Test")
        sid = sc["scenario_id"]
        mcp_server.set_timespan(scenario_id=sid, start_year=2025)
        mcp_server.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        result = mcp_server.remove_device(scenario_id=sid, device_name="B1")
        assert "Removed" in result


class TestDeleteScenario:
    """Tests for delete_scenario tool."""

    def test_delete(self) -> None:
        sc = mcp_server.create_scenario(name="Test")
        result = mcp_server.delete_scenario(scenario_id=sc["scenario_id"])
        assert "Deleted" in result
        assert mcp_server._store.list() == []


class TestListScenarios:
    """Tests for list_scenarios tool."""

    def test_list_empty(self) -> None:
        result = mcp_server.list_scenarios()
        assert result == []

    def test_list_with_scenarios(self) -> None:
        mcp_server.create_scenario(name="S1")
        mcp_server.create_scenario(name="S2")
        result = mcp_server.list_scenarios()
        assert len(result) == 2


class TestSubmitScenario:
    """Tests for submit_scenario tool with mocked InvestmentClient."""

    def test_submit(self, mock_job_response: dict) -> None:
        mock_client = MagicMock()
        mock_client.create_planning_job.return_value = Job(**mock_job_response)
        mcp_server._client = mock_client

        sc = mcp_server.create_scenario(name="Test")
        sid = sc["scenario_id"]
        mcp_server.set_timespan(scenario_id=sid, start_year=2025)
        mcp_server.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        mcp_server.add_device(
            scenario_id=sid,
            device_type="electricity_import",
            name="Grid",
            properties={"price": 50.0, "max_import": 10.0},
        )

        result = mcp_server.submit_scenario(scenario_id=sid)
        assert result["job_id"] == "test_job_mcp_123"
        assert result["status"] == "pending"
        mock_client.create_planning_job.assert_called_once()

    def test_submit_records_job(self, mock_job_response: dict) -> None:
        mock_client = MagicMock()
        mock_client.create_planning_job.return_value = Job(**mock_job_response)
        mcp_server._client = mock_client

        sc = mcp_server.create_scenario(name="Test")
        sid = sc["scenario_id"]
        mcp_server.set_timespan(scenario_id=sid, start_year=2025)
        mcp_server.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        mcp_server.submit_scenario(scenario_id=sid)
        scenario = mcp_server._store.get(sid)
        assert "test_job_mcp_123" in scenario.jobs

    def test_submit_invalid_scenario_raises(self) -> None:
        sc = mcp_server.create_scenario(name="Empty")
        mcp_server.set_timespan(scenario_id=sc["scenario_id"], start_year=2025)
        with pytest.raises(ValueError, match="no devices"):
            mcp_server.submit_scenario(scenario_id=sc["scenario_id"])


class TestGetJobStatus:
    """Tests for get_job_status tool."""

    def test_get_status(self) -> None:
        mock_client = MagicMock()
        mock_client.get_job_status.return_value = Job(
            job_id="job_123",
            status="running",
            progress=60,
            message="Solving...",
        )
        mcp_server._client = mock_client

        result = mcp_server.get_job_status(job_id="job_123")
        assert result["status"] == "running"
        assert result["progress"] == 60


class TestGetJobResult:
    """Tests for get_job_result tool."""

    def test_get_result_summary(self, mock_result_response: dict) -> None:
        mock_client = MagicMock()
        # Simulate what InvestmentClient.get_job_result does
        from site_calc_investment.models.responses import InvestmentPlanningResponse

        result_data = {
            "job_id": str(mock_result_response["job_id"]),
            "status": mock_result_response["status"],
            **mock_result_response["result"],
        }
        mock_client.get_job_result.return_value = InvestmentPlanningResponse(**result_data)
        mcp_server._client = mock_client

        result = mcp_server.get_job_result(job_id="test_job_mcp_123", detail_level="summary")
        assert result["status"] == "completed"
        assert result["summary"]["expected_profit"] == 100000.0
        assert result["summary"]["solver_status"] == "optimal"
        assert result["investment_metrics"]["npv"] == 850000.0
        assert "device_summaries" not in result  # summary level has no device details

    def test_get_result_monthly(self, mock_result_response: dict) -> None:
        mock_client = MagicMock()
        from site_calc_investment.models.responses import InvestmentPlanningResponse

        result_data = {
            "job_id": str(mock_result_response["job_id"]),
            "status": mock_result_response["status"],
            **mock_result_response["result"],
        }
        mock_client.get_job_result.return_value = InvestmentPlanningResponse(**result_data)
        mcp_server._client = mock_client

        result = mcp_server.get_job_result(job_id="test_job_mcp_123", detail_level="monthly")
        assert "device_summaries" in result
        assert "Battery1" in result["device_summaries"]

    def test_get_result_invalid_detail_level(self) -> None:
        with pytest.raises(ValueError, match="Invalid detail_level"):
            mcp_server.get_job_result(job_id="job_123", detail_level="detailed")

    def test_get_result_full(self, mock_result_response: dict) -> None:
        mock_client = MagicMock()
        from site_calc_investment.models.responses import InvestmentPlanningResponse

        result_data = {
            "job_id": str(mock_result_response["job_id"]),
            "status": mock_result_response["status"],
            **mock_result_response["result"],
        }
        mock_client.get_job_result.return_value = InvestmentPlanningResponse(**result_data)
        mcp_server._client = mock_client

        result = mcp_server.get_job_result(job_id="test_job_mcp_123", detail_level="full")
        assert "sites" in result
        assert "device_summaries" in result


class TestCancelJob:
    """Tests for cancel_job tool."""

    def test_cancel(self) -> None:
        mock_client = MagicMock()
        mock_client.cancel_job.return_value = Job(job_id="job_123", status="cancelled")
        mcp_server._client = mock_client

        result = mcp_server.cancel_job(job_id="job_123")
        assert result["status"] == "cancelled"


class TestListJobs:
    """Tests for list_jobs tool."""

    def test_list_empty(self) -> None:
        result = mcp_server.list_jobs()
        assert result == []

    def test_list_with_jobs(self, mock_job_response: dict) -> None:
        mock_client = MagicMock()
        mock_client.create_planning_job.return_value = Job(**mock_job_response)
        mcp_server._client = mock_client

        sc = mcp_server.create_scenario(name="Test")
        sid = sc["scenario_id"]
        mcp_server.set_timespan(scenario_id=sid, start_year=2025)
        mcp_server.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        mcp_server.submit_scenario(scenario_id=sid)

        result = mcp_server.list_jobs()
        assert len(result) == 1
        assert result[0]["job_count"] == 1


class TestGetDeviceSchema:
    """Tests for get_device_schema tool."""

    def test_battery_schema(self) -> None:
        schema = mcp_server.get_device_schema("battery")
        assert "properties" in schema
        assert "capacity" in schema["properties"]
        assert schema["properties"]["capacity"]["required"] is True

    def test_all_device_types_have_schemas(self) -> None:
        types = [
            "battery",
            "chp",
            "heat_accumulator",
            "photovoltaic",
            "electricity_import",
            "electricity_export",
            "gas_import",
            "heat_export",
            "electricity_demand",
            "heat_demand",
        ]
        for dtype in types:
            schema = mcp_server.get_device_schema(dtype)
            assert "properties" in schema, f"No properties for {dtype}"

    def test_unknown_type_returns_error(self) -> None:
        result = mcp_server.get_device_schema("fusion_reactor")
        assert "error" in result
        assert "valid_types" in result

    def test_case_insensitive(self) -> None:
        schema = mcp_server.get_device_schema("Battery")
        assert "properties" in schema


class TestEndToEndWorkflow:
    """End-to-end integration tests for the full workflow."""

    def test_battery_arbitrage_workflow(self, mock_job_response: dict, mock_result_response: dict) -> None:
        """Full workflow: create -> add devices -> set timespan -> review -> submit -> get result."""
        mock_client = MagicMock()
        mock_client.create_planning_job.return_value = Job(**mock_job_response)

        from site_calc_investment.models.responses import InvestmentPlanningResponse

        result_data = {
            "job_id": str(mock_result_response["job_id"]),
            "status": mock_result_response["status"],
            **mock_result_response["result"],
        }
        mock_client.get_job_result.return_value = InvestmentPlanningResponse(**result_data)
        mcp_server._client = mock_client

        # Create scenario
        sc = mcp_server.create_scenario(name="Battery 10MWh evaluation")
        sid = sc["scenario_id"]

        # Add devices
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

        # Set timespan
        mcp_server.set_timespan(scenario_id=sid, start_year=2025, years=1)

        # Review
        review = mcp_server.review_scenario(scenario_id=sid)
        assert "Valid" in review["validation"]
        assert len(review["devices"]) == 3

        # Submit
        submit_result = mcp_server.submit_scenario(scenario_id=sid)
        assert submit_result["status"] == "pending"

        # Get result
        job_result = mcp_server.get_job_result(job_id=submit_result["job_id"])
        assert job_result["summary"]["expected_profit"] == 100000.0

    def test_scenario_reuse_workflow(self, mock_job_response: dict) -> None:
        """Test that scenarios can be modified and resubmitted."""
        mock_client = MagicMock()
        mock_client.create_planning_job.return_value = Job(**mock_job_response)
        mcp_server._client = mock_client

        sc = mcp_server.create_scenario(name="Reuse Test")
        sid = sc["scenario_id"]
        mcp_server.set_timespan(scenario_id=sid, start_year=2025)
        mcp_server.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )

        # First submission
        mcp_server.submit_scenario(scenario_id=sid)

        # Add more devices and resubmit
        mcp_server.add_device(
            scenario_id=sid,
            device_type="electricity_import",
            name="Grid",
            properties={"price": 50.0, "max_import": 10.0},
        )
        mcp_server.submit_scenario(scenario_id=sid)

        scenario = mcp_server._store.get(sid)
        assert len(scenario.jobs) == 2
        assert len(scenario.devices) == 2


class TestSaveDataFile:
    """Tests for save_data_file tool."""

    def test_save_basic(self, tmp_path: object) -> None:
        """Tool returns dict with file_path, columns, rows, message."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "tool_test.csv"
        with patch("site_calc_investment.mcp.server.get_data_dir", return_value=None):
            result = mcp_server.save_data_file(
                file_path=str(out),
                columns={"hour": [0.0, 1.0, 2.0], "price": [30.0, 40.0, 80.0]},
            )
        assert result["file_path"] == str(out)
        assert result["columns"] == ["hour", "price"]
        assert result["rows"] == 3
        assert "3 rows" in result["message"]
        assert os.path.isfile(result["file_path"])

    def test_save_and_use_in_add_device(self, tmp_path: object) -> None:
        """End-to-end: save file, then use it in add_device via file reference."""
        import pathlib

        out = pathlib.Path(str(tmp_path)) / "prices.csv"
        prices = [50.0] * 8760
        with patch("site_calc_investment.mcp.server.get_data_dir", return_value=None):
            save_result = mcp_server.save_data_file(
                file_path=str(out),
                columns={"price_eur": prices},
            )

        # Create scenario and use the saved file
        sc = mcp_server.create_scenario(name="SaveAndUse")
        sid = sc["scenario_id"]
        mcp_server.set_timespan(scenario_id=sid, start_year=2025)
        result = mcp_server.add_device(
            scenario_id=sid,
            device_type="electricity_import",
            name="Grid",
            properties={"price": {"file": save_result["file_path"], "column": "price_eur"}, "max_import": 10.0},
        )
        assert isinstance(result, str)

        review = mcp_server.review_scenario(scenario_id=sid)
        assert len(review["devices"]) == 1
