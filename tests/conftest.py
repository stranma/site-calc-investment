"""Pytest configuration and fixtures for investment client tests."""

from datetime import datetime
from typing import List
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from site_calc_investment.models import (
    CHP,
    Battery,
    BatteryProperties,
    CHPProperties,
    ElectricityExport,
    ElectricityImport,
    InvestmentParameters,
    MarketExportProperties,
    MarketImportProperties,
    OptimizationConfig,
    Site,
)


@pytest.fixture
def prague_tz():
    """Prague timezone."""
    return ZoneInfo("Europe/Prague")


@pytest.fixture
def test_datetime(prague_tz):
    """Test datetime in Prague timezone."""
    return datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)


@pytest.fixture
def hourly_prices_1year() -> List[float]:
    """Generate 8760 hourly prices for 1 year."""
    prices = []
    for day in range(365):
        for hour in range(24):
            if 9 <= hour <= 20:
                price = 40.0
            else:
                price = 25.0
            prices.append(price)
    return prices


@pytest.fixture
def hourly_prices_10year() -> List[float]:
    """Generate 87,600 hourly prices for 10 years with 2% escalation."""
    base_daily = []
    for hour in range(24):
        if 9 <= hour <= 20:
            price = 40.0
        else:
            price = 25.0
        base_daily.append(price)

    prices = []
    for year in range(10):
        factor = 1.02**year
        for day in range(365):
            for hour in range(24):
                prices.append(base_daily[hour] * factor)

    return prices


@pytest.fixture
def battery_10mw() -> Battery:
    """10 MW / 20 MWh battery (2-hour duration)."""
    return Battery(
        name="Battery1", properties=BatteryProperties(capacity=20.0, max_power=10.0, efficiency=0.90, initial_soc=0.5)
    )


@pytest.fixture
def chp_device() -> CHP:
    """Combined Heat and Power device."""
    return CHP(name="CHP1", properties=CHPProperties(gas_input=8.0, el_output=3.0, heat_output=4.0, is_binary=False))


@pytest.fixture
def grid_import(hourly_prices_10year) -> ElectricityImport:
    """Grid import device with 10-year prices."""
    return ElectricityImport(
        name="GridImport", properties=MarketImportProperties(price=hourly_prices_10year, max_import=20.0)
    )


@pytest.fixture
def grid_export(hourly_prices_10year) -> ElectricityExport:
    """Grid export device with 10-year prices."""
    return ElectricityExport(
        name="GridExport", properties=MarketExportProperties(price=hourly_prices_10year, max_export=20.0)
    )


@pytest.fixture
def simple_site(battery_10mw, grid_import, grid_export) -> Site:
    """Simple site with battery and grid connections."""
    return Site(
        site_id="test_site",
        description="Test site for investment planning",
        devices=[battery_10mw, grid_import, grid_export],
    )


@pytest.fixture
def investment_params() -> InvestmentParameters:
    """Investment parameters for testing."""
    return InvestmentParameters(
        discount_rate=0.05,
        project_lifetime_years=10,
        device_capital_costs={"Battery1": 2_000_000},
        device_annual_opex={"Battery1": 20_000},
    )


@pytest.fixture
def optimization_config() -> OptimizationConfig:
    """Optimization configuration for testing."""
    return OptimizationConfig(objective="maximize_profit", time_limit_seconds=3600, relax_binary_variables=True)


@pytest.fixture
def mock_job_response():
    """Mock job creation response."""
    return {
        "job_id": "test_job_123",
        "status": "pending",
        "created_at": "2025-01-01T10:00:00+01:00",
        "message": "Job created successfully",
    }


@pytest.fixture
def mock_job_running_response():
    """Mock job running status response."""
    return {
        "job_id": "test_job_123",
        "status": "running",
        "created_at": "2025-01-01T10:00:00+01:00",
        "started_at": "2025-01-01T10:00:05+01:00",
        "progress": 45,
        "message": "Optimization in progress",
    }


@pytest.fixture
def mock_job_result_api_response():
    """Mock API response from /api/v1/jobs/{job_id}/result endpoint.

    This represents the raw API response which wraps the result data in a 'result' field.
    Used for testing the API client.
    """
    return {
        "job_id": "test_job_123",
        "status": "completed",
        "result": {
            "sites": {
                "test_site": {
                    "device_schedules": {"Battery1": {"flows": {"electricity": [2.0] * 100}, "soc": [0.5] * 100}},
                    "grid_flows": {"import": [0.0] * 100, "export": [2.0] * 100},
                }
            },
            "summary": {
                "total_da_revenue": 500000.0,
                "total_cost": 200000.0,
                "expected_profit": 300000.0,
                "solver_status": "optimal",
                "solve_time_seconds": 127.3,
                "sites_count": 1,
            },
            "investment_metrics": {
                "total_revenue_10y": 5000000.0,
                "total_costs_10y": 2000000.0,
                "npv": 1250000.0,
                "irr": 0.12,
                "payback_period_years": 6.2,
                "annual_revenue_by_year": [450000.0] * 10,
                "annual_costs_by_year": [180000.0] * 10,
            },
        },
    }


@pytest.fixture
def mock_job_completed_response():
    """Mock job completed response for direct InvestmentPlanningResponse creation.

    This is the flattened format suitable for directly creating model instances.
    Used for testing scenario comparison and other model-level tests.
    """
    return {
        "job_id": "test_job_123",
        "status": "completed",
        "sites": {
            "test_site": {
                "device_schedules": {"Battery1": {"flows": {"electricity": [2.0] * 100}, "soc": [0.5] * 100}},
                "grid_flows": {"import": [0.0] * 100, "export": [2.0] * 100},
            }
        },
        "summary": {
            "total_da_revenue": 500000.0,
            "total_cost": 200000.0,
            "expected_profit": 300000.0,
            "solver_status": "optimal",
            "solve_time_seconds": 127.3,
            "sites_count": 1,
        },
        "investment_metrics": {
            "total_revenue_10y": 5000000.0,
            "total_costs_10y": 2000000.0,
            "npv": 1250000.0,
            "irr": 0.12,
            "payback_period_years": 6.2,
            "annual_revenue_by_year": [450000.0] * 10,
            "annual_costs_by_year": [180000.0] * 10,
        },
    }


@pytest.fixture
def mock_job_failed_response():
    """Mock job failed response."""
    return {
        "job_id": "test_job_123",
        "status": "failed",
        "created_at": "2025-01-01T10:00:00+01:00",
        "started_at": "2025-01-01T10:00:05+01:00",
        "failed_at": "2025-01-01T10:10:00+01:00",
        "error": {
            "code": "infeasible",
            "message": "Optimization problem is infeasible",
            "details": {"conflicting_constraints": ["Battery SOC constraints"]},
        },
    }


@pytest.fixture
def mock_health_response():
    """Mock health endpoint response."""
    mock = Mock()
    mock.status_code = 200
    mock.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "api_version": "1.0",
        "environment": "test",
    }
    return mock


@pytest.fixture(autouse=True)
def skip_version_check(monkeypatch):
    """Skip server version validation in tests.

    This avoids needing to mock the /health endpoint in every test.
    The version validation logic should be tested separately.
    """
    from site_calc_investment.api.client import InvestmentClient

    original_init = InvestmentClient.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._version_checked = True

    monkeypatch.setattr(InvestmentClient, "__init__", patched_init)
