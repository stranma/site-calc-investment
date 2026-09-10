"""Public storage opening-stock opt-in and explicit state-index wire contract."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from site_calc_investment.models.devices import BatteryProperties, HeatAccumulatorProperties
from site_calc_investment.models.requests import InvestmentPlanningRequest, Site, TimeSpanInvestment


def sizing() -> dict:
    return {
        "periods": "horizon",
        "tariffs": [{"name": "energy", "reserved_price": 1.0, "peak_price": 0.0}],
    }


@pytest.mark.parametrize("model", [BatteryProperties, HeatAccumulatorProperties])
def test_explicit_initial_basis_and_state_boundaries(model) -> None:
    props = model(
        capacity=10.0,
        max_power=2.0,
        efficiency=1.0,
        initial_soc=0.5,
        initial_soc_basis="built_capacity",
        soc_anchor_indices=[2, 4],
    )
    assert props.initial_soc == 0.5
    assert props.initial_soc_basis == "built_capacity"
    assert props.soc_anchor_indices == [2, 4]
    assert props.soc_anchor_target == 0.5


@pytest.mark.parametrize("basis", [None, "default", "built_capacity"])
def test_optimized_battery_still_defaults_to_zero(basis) -> None:
    extra = {} if basis is None else {"initial_soc_basis": basis}
    props = BatteryProperties(capacity=10, max_power=2, efficiency=1, capacity_sizing=sizing(), **extra)
    assert props.initial_soc == 0.0


def test_sized_battery_accepts_positive_soc_only_with_explicit_opt_in() -> None:
    args = dict(capacity=10, max_power=2, efficiency=1, capacity_sizing=sizing(), initial_soc=0.5)
    with pytest.raises(ValidationError, match="built_capacity"):
        BatteryProperties(**args)
    props = BatteryProperties(**args, initial_soc_basis="built_capacity", soc_anchor_indices=[2, 4])
    assert props.initial_soc == 0.5


@pytest.mark.parametrize("kind", ["battery", "heat_accumulator"])
def test_public_request_serializes_explicit_controls(kind) -> None:
    properties = {
        "capacity": 10.0,
        "max_power": 2.0,
        "efficiency": 1.0,
        "initial_soc": 0.5,
        "initial_soc_basis": "built_capacity",
        "soc_anchor_indices": [2, 4],
    }
    if kind == "battery":
        properties["capacity_sizing"] = sizing()
    request = InvestmentPlanningRequest(
        sites=[Site(site_id="site", devices=[{"name": "storage", "type": kind, "properties": properties}])],
        timespan=TimeSpanInvestment(start=datetime(2026, 1, 31, 22, tzinfo=ZoneInfo("Europe/Prague")), intervals=4),
    )
    wire = json.loads(json.dumps(request.model_dump_for_api(), allow_nan=False))
    props = wire["sites"][0]["devices"][0]["properties"]
    assert props["initial_soc_basis"] == "built_capacity"
    assert props["initial_soc"] == 0.5
    assert props["soc_anchor_indices"] == [2, 4]


@pytest.mark.parametrize("model", [BatteryProperties, HeatAccumulatorProperties])
@pytest.mark.parametrize(
    "options",
    [
        {"initial_soc_basis": "ceiling"},
        {"initial_soc_basis": None},
        {"soc_anchor_indices": [True]},
        {"soc_anchor_indices": [1.0]},
        {"soc_anchor_indices": ["1"]},
        {"soc_anchor_indices": [0]},
        {"soc_anchor_indices": [-1]},
        {"soc_anchor_indices": [2, 2]},
        {"soc_anchor_indices": [2, 1]},
        {"soc_anchor_indices": None},
        {"soc_anchor_indices": [1], "soc_anchor_interval_hours": 0},
        {"soc_anchor_target": True},
        {"soc_anchor_target": float("nan")},
        {"soc_anchor_target": float("inf")},
        {"soc_anchor_target": 1.1},
        {"soc_anchor_interval_hours": True},
        {"soc_anchor_interval_hours": float("inf")},
    ],
)
def test_invalid_soc_controls_rejected(model, options) -> None:
    with pytest.raises(ValidationError):
        model(capacity=10, max_power=2, efficiency=1, **options)
