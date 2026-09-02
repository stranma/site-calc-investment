"""MCP scenario flow for ``electricity_import_with_overflow``."""

import pytest

from site_calc_investment.mcp import server as mcp_server
from site_calc_investment.mcp.scenario import ScenarioStore


def _add_sugar(store: ScenarioStore, scenario_id: str, **extra) -> str:
    props = {"import_price": 90.0, "overflow_price": 120.0, "max_import": 2.0}
    props.update(extra)
    return store.add_device(scenario_id, "electricity_import_with_overflow", "Grid", props)


class TestOverflowScenario:
    def test_scalar_prices_expand_to_the_timespan(self, store: ScenarioStore, scenario_id: str) -> None:
        _add_sugar(store, scenario_id)
        request = store.build_request(scenario_id)
        wire = request.model_dump_for_api()["sites"][0]["devices"]
        assert [d["type"] for d in wire] == ["electricity_import", "electricity_export"]
        assert len(wire[0]["properties"]["price"]) == 8760
        assert len(wire[1]["properties"]["price"]) == 8760
        assert wire[1]["properties"]["exclusive_with"] == "Grid"
        assert wire[1]["properties"]["max_export"] == 2.0

    def test_summary_names_the_derived_export_device(self, store: ScenarioStore, scenario_id: str) -> None:
        summary = _add_sugar(store, scenario_id)
        assert "Grid_overflow" in summary
        review = store.review(scenario_id)
        assert "Grid_overflow" in review["devices"][0]["summary"]

    def test_add_device_rejects_a_reserved_overflow_name(self, store: ScenarioStore, scenario_id: str) -> None:
        _add_sugar(store, scenario_id)
        with pytest.raises(ValueError, match="reserved"):
            store.add_device(scenario_id, "electricity_import", "Grid_overflow", {"price": 50.0, "max_import": 1.0})

    def test_add_sugar_rejects_a_taken_overflow_name(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(scenario_id, "electricity_import", "Grid_overflow", {"price": 50.0, "max_import": 1.0})
        with pytest.raises(ValueError, match="already exists"):
            _add_sugar(store, scenario_id)

    def test_summary_marks_a_capacity_reservation(self, store: ScenarioStore, scenario_id: str) -> None:
        reservation = {
            "periods": "calendar_month",
            "tariffs": [{"name": "T1", "reserved_price": 1000.0, "peak_price": 10.0}],
            "reserved": 2.0,
        }
        summary = _add_sugar(store, scenario_id, capacity_reservation=reservation)
        assert "capacity reservation" in summary

    def test_relaxed_flag_is_forwarded(self, store: ScenarioStore, scenario_id: str) -> None:
        _add_sugar(store, scenario_id, no_simultaneous_flow=False)
        wire = store.build_request(scenario_id).model_dump_for_api()["sites"][0]["devices"]
        assert "exclusive_with" not in wire[1]["properties"]


class TestOverflowSchema:
    def test_sugar_device_schema(self) -> None:
        schema = mcp_server.get_device_schema("electricity_import_with_overflow")
        props = schema["properties"]
        for key in ("import_price", "overflow_price", "max_import", "max_overflow", "no_simultaneous_flow"):
            assert key in props, key
        assert props["import_price"]["required"] is True
        assert props["max_overflow"]["required"] is False
        assert schema["example"]["max_import"] > 0

    def test_electricity_export_schema_lists_the_pairing_field(self) -> None:
        schema = mcp_server.get_device_schema("electricity_export")
        assert schema["properties"]["exclusive_with"]["required"] is False


class TestOverflowMcpFeedback:
    """Mistakes are reported at add time or in review, not first at submit."""

    def test_exclusive_with_on_an_import_is_rejected_at_add_time(self, store: ScenarioStore, scenario_id: str) -> None:
        with pytest.raises(ValueError, match="put exclusive_with on the electricity_export"):
            store.add_device(
                scenario_id, "electricity_import", "Grid", {"price": 50.0, "max_import": 1.0, "exclusive_with": "X"}
            )

    def test_unknown_property_is_rejected_at_add_time(self, store: ScenarioStore, scenario_id: str) -> None:
        with pytest.raises(ValueError, match="unknown property"):
            _add_sugar(store, scenario_id, price=1.0)

    def test_hand_built_pairing_through_the_store(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(scenario_id, "electricity_import", "DSO", {"price": 50.0, "max_import": 2.0})
        summary = store.add_device(
            scenario_id, "electricity_export", "Overflow", {"price": 80.0, "max_export": 2.0, "exclusive_with": "DSO"}
        )
        assert "paired with 'DSO'" in summary
        wire = store.build_request(scenario_id).model_dump_for_api()["sites"][0]["devices"]
        assert wire[1]["properties"]["exclusive_with"] == "DSO"
        assert store.review(scenario_id)["validation"].startswith("Valid")

    def test_review_reports_a_missing_pairing_target(self, store: ScenarioStore, scenario_id: str) -> None:
        store.add_device(scenario_id, "electricity_import", "DSO", {"price": 50.0, "max_import": 2.0})
        store.add_device(
            scenario_id, "electricity_export", "Overflow", {"price": 80.0, "max_export": 2.0, "exclusive_with": "Nope"}
        )
        validation = store.review(scenario_id)["validation"]
        assert validation.startswith("Not ready")
        assert "Nope" in validation
