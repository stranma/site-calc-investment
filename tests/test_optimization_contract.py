"""Public strategy, tolerance, and result-certificate wire contracts."""

import copy
import json
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from site_calc_investment.api.client import InvestmentClient
from site_calc_investment.models.requests import InvestmentPlanningRequest, OptimizationConfig, Site, TimeSpanInvestment
from site_calc_investment.models.responses import Summary


@pytest.fixture
def planning_request() -> InvestmentPlanningRequest:
    """Small public request with no solver or private-core dependency."""
    return InvestmentPlanningRequest(
        sites=[
            Site(
                site_id="site",
                devices=[
                    {"name": "grid", "type": "electricity_import", "properties": {"price": [50.0], "max_import": 1.0}}
                ],
            )
        ],
        timespan=TimeSpanInvestment(start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")), intervals=1),
    )


@pytest.mark.parametrize("field", ["mip_gap", "abs_gap"])
@pytest.mark.parametrize("value", [True, False, -0.01, float("nan"), float("inf"), float("-inf")])
def test_reject_invalid_tolerances(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        OptimizationConfig(**{field: value})


@pytest.mark.parametrize("field", ["mip_gap", "abs_gap"])
@pytest.mark.parametrize("value", [None, 0.0, 2, 1250.5])
def test_accept_optional_nonnegative_tolerances(field: str, value: float | None) -> None:
    assert getattr(OptimizationConfig(**{field: value}), field) == value


@pytest.mark.parametrize("strategy", [None, "auto", "monolithic", "decomposed"])
@pytest.mark.parametrize("policy", [None, "preserve", "monthly_fixed"])
def test_strategy_and_policy_values(strategy: str | None, policy: str | None) -> None:
    config = OptimizationConfig(strategy=strategy, soc_boundary_policy=policy)
    assert config.strategy == strategy
    assert config.soc_boundary_policy == policy


@pytest.mark.parametrize("field", ["strategy", "soc_boundary_policy"])
@pytest.mark.parametrize("value", ["unsupported", True])
def test_reject_unknown_strategy_or_policy(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        OptimizationConfig(**{field: value})


@pytest.mark.parametrize(
    "options,expected",
    [
        ({}, {}),
        ({"strategy": None, "mip_gap": None, "abs_gap": None, "soc_boundary_policy": None}, {}),
        ({"mip_gap": 0.01}, {"mip_gap": 0.01}),
        ({"abs_gap": 0.0}, {"abs_gap": 0.0}),
        ({"mip_gap": 0.0, "abs_gap": 25.0}, {"mip_gap": 0.0, "abs_gap": 25.0}),
        (
            {"strategy": "decomposed", "soc_boundary_policy": "monthly_fixed", "abs_gap": 25.0},
            {"strategy": "decomposed", "soc_boundary_policy": "monthly_fixed", "abs_gap": 25.0},
        ),
    ],
)
def test_submit_preserves_only_selected_options(
    planning_request: InvestmentPlanningRequest, mock_job_response: dict, options: dict, expected: dict
) -> None:
    planning_request.optimization_config = OptimizationConfig(**options)
    response = Mock(status_code=202)
    response.json.return_value = mock_job_response
    with patch("httpx.Client.request", return_value=response) as send:
        with InvestmentClient("https://api.example.com", "inv_test") as client:
            assert client.create_planning_job(planning_request).status == "pending"
    assert send.call_args.args == ("POST", "/api/v1/jobs/device-planning")
    payload = send.call_args.kwargs["json"]
    # This is the actual HTTP body, including explicit zeroes and no null options.
    wire = json.loads(json.dumps(payload, allow_nan=False))
    assert wire["optimization_config"] == {
        "objective": "maximize_profit",
        "time_limit_seconds": 300,
        "relax_binary_variables": True,
        **expected,
    }


CERTIFICATE_FIELDS = (
    "objective_lower_bound",
    "objective_upper_bound",
    "requested_strategy",
    "used_strategy",
    "fallback_reason",
    "soc_boundary_policy",
    "absolute_gap",
    "elapsed_time_seconds",
)


@pytest.mark.parametrize("explicit_nulls", [False, True])
def test_older_or_null_summary_does_not_invent_certificates(explicit_nulls: bool) -> None:
    data = {"solver_status": "Optimal", "solve_time_seconds": 1.0, "is_optimal": True}
    if explicit_nulls:
        data.update(dict.fromkeys(CERTIFICATE_FIELDS))
    summary = Summary.model_validate_json(json.dumps(data))
    assert all(getattr(summary, name) is None for name in CERTIFICATE_FIELDS)


@pytest.mark.parametrize(
    "lower,upper,gap",
    [
        (None, None, None),
        (-500.0, None, None),
        (None, -450.0, None),
        (-500.0, -450.0, 50.0),
        (450.0, 500.0, 50.0),
        (0.0, 0.0, 0.0),
    ],
)
def test_get_result_retains_bounds_fallback_and_actual_stop_reason(
    mock_job_result_api_response: dict, lower: float | None, upper: float | None, gap: float | None
) -> None:
    data = copy.deepcopy(mock_job_result_api_response)
    data["result"]["summary"].update(
        objective_lower_bound=lower,
        objective_upper_bound=upper,
        absolute_gap=gap,
        requested_strategy="auto",
        used_strategy="monolithic",
        fallback_reason="Requested model is unsupported by decomposed strategy",
        soc_boundary_policy="monthly_fixed",
        elapsed_time_seconds=135.0,
        is_optimal=gap is not None,
        termination_reason="time_limit",
    )
    response = Mock(status_code=200)
    response.json.return_value = data
    with patch("httpx.Client.request", return_value=response) as get:
        with InvestmentClient("https://api.example.com", "inv_test") as client:
            summary = client.get_job_result("test_job_123").summary
    assert get.call_args.args == ("GET", "/api/v1/jobs/test_job_123/result")
    assert summary.objective_lower_bound == lower
    assert summary.objective_upper_bound == upper
    assert summary.absolute_gap == gap
    assert summary.requested_strategy == "auto"
    assert summary.used_strategy == "monolithic"
    assert summary.fallback_reason == data["result"]["summary"]["fallback_reason"]
    assert summary.soc_boundary_policy == "monthly_fixed"
    assert summary.elapsed_time_seconds == 135.0
    assert summary.solve_time_seconds == 127.3
    assert summary.is_optimal is (gap is not None)
    assert summary.termination_reason == "time_limit"


@pytest.mark.parametrize(
    "field", ["objective_lower_bound", "objective_upper_bound", "absolute_gap", "elapsed_time_seconds"]
)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_certificates_are_not_unknown_nulls(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        Summary(solver_status="Feasible", solve_time_seconds=1.0, **{field: value})
