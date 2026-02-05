"""Tests for ScenarioStore — in-memory draft scenario management."""

import pytest

from site_calc_investment.mcp.scenario import ScenarioStore


class TestScenarioCreate:
    """Tests for creating scenarios."""

    def test_create_returns_id(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test")
        assert sid.startswith("sc_")
        assert len(sid) == 11  # "sc_" + 8 hex chars

    def test_create_with_description(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test", description="A test scenario")
        scenario = store.get(sid)
        assert scenario.name == "Test"
        assert scenario.description == "A test scenario"

    def test_create_multiple_unique_ids(self, store: ScenarioStore) -> None:
        ids = {store.create(name=f"S{i}") for i in range(10)}
        assert len(ids) == 10

    def test_get_nonexistent_raises(self, store: ScenarioStore) -> None:
        with pytest.raises(KeyError, match="not found"):
            store.get("sc_nonexistent")


class TestScenarioAddDevice:
    """Tests for adding devices to scenarios."""

    def test_add_battery(self, store: ScenarioStore, scenario_id: str) -> None:
        summary = store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="Bat1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        assert "10.0 MWh" in summary
        assert "5.0 MW" in summary

    def test_add_chp(self, store: ScenarioStore, scenario_id: str) -> None:
        summary = store.add_device(
            scenario_id=scenario_id,
            device_type="chp",
            name="CHP1",
            properties={"gas_input": 4.0, "el_output": 2.0, "heat_output": 1.5},
        )
        assert "gas" in summary.lower()
        assert "el" in summary.lower() or "2.0" in summary

    def test_add_electricity_import_flat_price(self, store: ScenarioStore, scenario_id: str) -> None:
        summary = store.add_device(
            scenario_id=scenario_id,
            device_type="electricity_import",
            name="Grid",
            properties={"price": 50.0, "max_import": 10.0},
        )
        assert "10.0 MW" in summary or "10.0" in summary

    def test_add_electricity_import_array_price(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="electricity_import",
            name="Grid",
            properties={"price": [30.0, 40.0, 80.0, 50.0], "max_import": 10.0},
        )
        scenario = store.get(scenario_id)
        assert len(scenario.devices) == 1

    def test_add_device_invalid_type(self, store: ScenarioStore, scenario_id: str) -> None:
        with pytest.raises(ValueError, match="Unknown device type"):
            store.add_device(
                scenario_id=scenario_id,
                device_type="nuclear_reactor",
                name="NR1",
                properties={},
            )

    def test_add_device_duplicate_name(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="Bat1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        with pytest.raises(ValueError, match="already exists"):
            store.add_device(
                scenario_id=scenario_id,
                device_type="battery",
                name="Bat1",
                properties={"capacity": 20.0, "max_power": 10.0, "efficiency": 0.95},
            )

    def test_add_device_nonexistent_scenario(self, store: ScenarioStore) -> None:
        with pytest.raises(KeyError, match="not found"):
            store.add_device(
                scenario_id="sc_fake",
                device_type="battery",
                name="B1",
                properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
            )

    def test_add_device_case_insensitive_type(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="Battery",
            name="Bat1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        scenario = store.get(scenario_id)
        assert scenario.devices[0].device_type == "battery"

    def test_add_device_with_schedule(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="Bat1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
            schedule={"max_hours_per_day": 12},
        )
        scenario = store.get(scenario_id)
        assert scenario.devices[0].schedule == {"max_hours_per_day": 12}

    def test_add_all_device_types(self, store: ScenarioStore, scenario_id: str) -> None:
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
            store.add_device(scenario_id=scenario_id, device_type=dtype, name=name, properties=props)
        scenario = store.get(scenario_id)
        assert len(scenario.devices) == 10


class TestScenarioRemoveDevice:
    """Tests for removing devices from scenarios."""

    def test_remove_device(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="Bat1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        store.remove_device(scenario_id, "Bat1")
        scenario = store.get(scenario_id)
        assert len(scenario.devices) == 0

    def test_remove_nonexistent_device(self, store: ScenarioStore, scenario_id: str) -> None:
        with pytest.raises(KeyError, match="not found"):
            store.remove_device(scenario_id, "NoSuchDevice")


class TestScenarioTimespan:
    """Tests for setting timespan."""

    def test_set_timespan(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test")
        result = store.set_timespan(sid, start_year=2025, years=1)
        assert "8760" in result
        assert "2025" in result

    def test_set_timespan_multi_year(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test")
        result = store.set_timespan(sid, start_year=2025, years=5)
        assert "43800" in result  # 5 * 8760

    def test_set_timespan_overwrite(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test")
        store.set_timespan(sid, start_year=2025, years=1)
        store.set_timespan(sid, start_year=2026, years=2)
        scenario = store.get(sid)
        assert scenario.timespan is not None
        assert scenario.timespan.start_year == 2026
        assert scenario.timespan.years == 2

    def test_set_timespan_with_intervals(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test")
        result = store.set_timespan(sid, start_year=2026, intervals=864)
        assert "864" in result
        assert "2026" in result
        scenario = store.get(sid)
        assert scenario.timespan is not None
        assert scenario.timespan.intervals == 864

    def test_set_timespan_intervals_overrides_years(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test")
        store.set_timespan(sid, start_year=2026, years=2, intervals=500)
        scenario = store.get(sid)
        assert scenario.timespan is not None
        assert scenario.timespan.intervals == 500

    def test_set_timespan_intervals_validation(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test")
        with pytest.raises(ValueError, match="between 1 and 100,000"):
            store.set_timespan(sid, start_year=2026, intervals=0)
        with pytest.raises(ValueError, match="between 1 and 100,000"):
            store.set_timespan(sid, start_year=2026, intervals=100_001)

    def test_set_timespan_intervals_backward_compat(self, store: ScenarioStore) -> None:
        sid = store.create(name="Test")
        result = store.set_timespan(sid, start_year=2025, years=1)
        assert "8760" in result
        scenario = store.get(sid)
        assert scenario.timespan is not None
        assert scenario.timespan.intervals is None


class TestScenarioInvestmentParams:
    """Tests for setting investment parameters."""

    def test_set_basic_params(self, store: ScenarioStore, scenario_id: str) -> None:
        result = store.set_investment_params(scenario_id, discount_rate=0.08)
        assert "8.0%" in result

    def test_set_full_params(self, store: ScenarioStore, scenario_id: str) -> None:
        result = store.set_investment_params(
            scenario_id,
            discount_rate=0.05,
            project_lifetime_years=20,
            device_capital_costs={"B1": 500000},
            device_annual_opex={"B1": 10000},
        )
        assert "5.0%" in result
        assert "20y" in result
        assert "500,000" in result
        assert "10,000" in result


class TestScenarioReview:
    """Tests for reviewing scenarios."""

    def test_review_empty_scenario(self, store: ScenarioStore) -> None:
        sid = store.create(name="Empty")
        review = store.review(sid)
        assert review["name"] == "Empty"
        assert len(review["devices"]) == 0
        assert "Not ready" in review["validation"]

    def test_review_valid_scenario(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        review = store.review(scenario_id)
        assert "Valid" in review["validation"]
        assert len(review["devices"]) == 1
        assert review["devices"][0]["name"] == "B1"

    def test_review_no_timespan(self, store: ScenarioStore) -> None:
        sid = store.create(name="No TS")
        store.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        review = store.review(sid)
        assert "Not ready" in review["validation"]
        assert "timespan" in review["validation"].lower()

    def test_review_with_custom_intervals(self, store: ScenarioStore) -> None:
        sid = store.create(name="Custom")
        store.set_timespan(sid, start_year=2026, intervals=864)
        store.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        review = store.review(sid)
        assert "864" in review["timespan"]
        assert "custom" in review["timespan"].lower()

    def test_review_with_investment_params(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        store.set_investment_params(scenario_id, discount_rate=0.05, device_capital_costs={"B1": 500000})
        review = store.review(scenario_id)
        assert "5.0%" in review["investment_params"]


class TestScenarioBuildRequest:
    """Tests for building InvestmentPlanningRequest from a scenario."""

    def test_build_basic_request(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        store.add_device(
            scenario_id=scenario_id,
            device_type="electricity_import",
            name="Grid",
            properties={"price": 50.0, "max_import": 10.0},
        )
        request = store.build_request(scenario_id)
        assert len(request.sites) == 1
        assert len(request.sites[0].devices) == 2
        assert request.timespan.intervals == 8760

    def test_build_request_no_devices_raises(self, store: ScenarioStore) -> None:
        sid = store.create(name="Empty")
        store.set_timespan(sid, start_year=2025)
        with pytest.raises(ValueError, match="no devices"):
            store.build_request(sid)

    def test_build_request_no_timespan_raises(self, store: ScenarioStore) -> None:
        sid = store.create(name="No TS")
        store.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        with pytest.raises(ValueError, match="no timespan"):
            store.build_request(sid)

    def test_build_request_with_objective(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        request = store.build_request(scenario_id, objective="minimize_cost")
        assert request.optimization_config.objective == "minimize_cost"

    def test_build_request_with_investment_params(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        store.set_investment_params(
            scenario_id,
            discount_rate=0.05,
            project_lifetime_years=10,
            device_capital_costs={"B1": 500000},
        )
        request = store.build_request(scenario_id)
        assert request.investment_parameters is not None
        assert request.investment_parameters.discount_rate == 0.05
        assert request.investment_parameters.device_capital_costs == {"B1": 500000}

    def test_build_request_expands_scalar_price(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="electricity_import",
            name="Grid",
            properties={"price": 50.0, "max_import": 10.0},
        )
        request = store.build_request(scenario_id)
        device = request.sites[0].devices[0]
        assert len(device.properties.price) == 8760
        assert all(p == 50.0 for p in device.properties.price)

    def test_build_request_solver_timeout_capped(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        request = store.build_request(scenario_id, solver_timeout=2000)
        assert request.optimization_config.time_limit_seconds == 900

    def test_build_request_with_pv_location_dict(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="photovoltaic",
            name="PV1",
            properties={
                "peak_power_mw": 5.0,
                "location": {"latitude": 50.07, "longitude": 14.44},
                "tilt": 35,
                "azimuth": 180,
            },
        )
        request = store.build_request(scenario_id)
        pv = request.sites[0].devices[0]
        assert pv.properties.location.latitude == 50.07

    def test_build_request_with_custom_intervals(self, store: ScenarioStore) -> None:
        sid = store.create(name="Custom Intervals")
        store.set_timespan(sid, start_year=2026, intervals=864)
        store.add_device(
            scenario_id=sid,
            device_type="electricity_import",
            name="Grid",
            properties={"price": [50.0] * 864, "max_import": 10.0},
        )
        request = store.build_request(sid)
        assert request.timespan.intervals == 864

    def test_build_request_with_schedule(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(
            scenario_id=scenario_id,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
            schedule={"max_hours_per_day": 12},
        )
        request = store.build_request(scenario_id)
        device = request.sites[0].devices[0]
        assert device.schedule is not None
        assert device.schedule.max_hours_per_day == 12


class TestScenarioDelete:
    """Tests for deleting scenarios."""

    def test_delete_scenario(self, store: ScenarioStore) -> None:
        sid = store.create(name="To Delete")
        store.delete(sid)
        with pytest.raises(KeyError):
            store.get(sid)

    def test_delete_nonexistent(self, store: ScenarioStore) -> None:
        with pytest.raises(KeyError):
            store.delete("sc_nonexistent")


class TestScenarioList:
    """Tests for listing scenarios."""

    def test_list_empty(self, store: ScenarioStore) -> None:
        assert store.list() == []

    def test_list_multiple(self, store: ScenarioStore) -> None:
        store.create(name="S1")
        store.create(name="S2")
        result = store.list()
        assert len(result) == 2
        names = {s.name for s in result}
        assert names == {"S1", "S2"}

    def test_list_with_devices(self, store: ScenarioStore) -> None:
        sid = store.create(name="WithDevices")
        store.set_timespan(sid, start_year=2025)
        store.add_device(
            scenario_id=sid,
            device_type="battery",
            name="B1",
            properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9},
        )
        result = store.list()
        assert result[0].device_count == 1
        assert result[0].has_timespan is True


class TestScenarioRecordJob:
    """Tests for recording job submissions."""

    def test_record_job(self, store: ScenarioStore, scenario_id: str) -> None:
        store.record_job(scenario_id, "job_123")
        scenario = store.get(scenario_id)
        assert "job_123" in scenario.jobs

    def test_record_multiple_jobs(self, store: ScenarioStore, scenario_id: str) -> None:
        store.record_job(scenario_id, "job_1")
        store.record_job(scenario_id, "job_2")
        scenario = store.get(scenario_id)
        assert len(scenario.jobs) == 2
