"""Shared fixtures for visualization tests."""

from typing import Dict, List, Optional

import pytest

from site_calc_investment.models.responses import (
    DeviceSchedule,
    InvestmentMetrics,
    InvestmentPlanningResponse,
    SiteResult,
    Summary,
)


def _make_response(
    job_id: str = "viz_test_001",
    num_intervals: int = 8760,
    device_schedules: Optional[Dict[str, DeviceSchedule]] = None,
    grid_flows: Optional[Dict[str, List[float]]] = None,
    investment_metrics: Optional[InvestmentMetrics] = None,
    expected_profit: float = 100000.0,
    total_da_revenue: float = 142500.0,
    total_cost: float = 42500.0,
) -> InvestmentPlanningResponse:
    """Helper to build an InvestmentPlanningResponse for testing."""
    if device_schedules is None:
        device_schedules = {
            "Battery1": DeviceSchedule(
                flows={"electricity": [1.0] * num_intervals},
                soc=[0.5] * num_intervals,
            ),
        }

    if grid_flows is None:
        grid_flows = {
            "import": [0.5] * num_intervals,
            "export": [1.5] * num_intervals,
        }

    sites = {
        "site_1": SiteResult(
            device_schedules=device_schedules,
            grid_flows=grid_flows,
        )
    }

    summary = Summary(
        total_da_revenue=total_da_revenue,
        total_cost=total_cost,
        expected_profit=expected_profit,
        solver_status="optimal",
        solve_time_seconds=2.5,
        sites_count=1,
    )

    return InvestmentPlanningResponse(
        job_id=job_id,
        sites=sites,
        summary=summary,
        investment_metrics=investment_metrics,
    )


@pytest.fixture
def response_1year() -> InvestmentPlanningResponse:
    """1-year optimization response with investment metrics."""
    metrics = InvestmentMetrics(
        npv=850000.0,
        irr=0.15,
        payback_period_years=4.5,
        total_revenue_10y=1425000.0,
        total_costs_10y=425000.0,
        annual_revenue_by_year=[142500.0] * 10,
        annual_costs_by_year=[42500.0] * 10,
    )
    return _make_response(
        num_intervals=8760,
        investment_metrics=metrics,
    )


@pytest.fixture
def response_10year() -> InvestmentPlanningResponse:
    """10-year optimization response with investment metrics."""
    metrics = InvestmentMetrics(
        npv=850000.0,
        irr=0.15,
        payback_period_years=4.5,
        total_revenue_10y=1425000.0,
        total_costs_10y=425000.0,
        annual_revenue_by_year=[142500.0] * 10,
        annual_costs_by_year=[42500.0] * 10,
    )
    return _make_response(
        num_intervals=8760 * 10,
        investment_metrics=metrics,
    )


@pytest.fixture
def response_no_investment() -> InvestmentPlanningResponse:
    """1-year response without investment metrics (profit only)."""
    return _make_response(
        num_intervals=8760,
        investment_metrics=None,
    )


@pytest.fixture
def response_multi_device() -> InvestmentPlanningResponse:
    """1-year response with multiple devices."""
    num = 8760
    metrics = InvestmentMetrics(
        npv=1200000.0,
        irr=0.18,
        payback_period_years=3.8,
        total_revenue_10y=2000000.0,
        total_costs_10y=600000.0,
        annual_revenue_by_year=[200000.0] * 10,
        annual_costs_by_year=[60000.0] * 10,
    )
    devices = {
        "Battery1": DeviceSchedule(
            flows={"electricity": [2.0] * num},
            soc=[0.5] * num,
        ),
        "CHP1": DeviceSchedule(
            flows={"electricity": [1.5] * num, "gas": [-3.0] * num, "heat": [1.0] * num},
            binary_status=[1] * num,
        ),
        "PV1": DeviceSchedule(
            flows={"electricity": [0.8] * num},
        ),
    }
    grid_flows = {
        "import": [0.5] * num,
        "export": [3.0] * num,
    }
    return _make_response(
        num_intervals=num,
        device_schedules=devices,
        grid_flows=grid_flows,
        investment_metrics=metrics,
        expected_profit=200000.0,
        total_da_revenue=300000.0,
        total_cost=100000.0,
    )


@pytest.fixture
def response_short() -> InvestmentPlanningResponse:
    """Short (168h = 1 week) optimization response."""
    return _make_response(
        num_intervals=168,
        investment_metrics=None,
    )
