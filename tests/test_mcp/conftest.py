"""Shared fixtures for MCP server tests."""

import json
from typing import Generator

import pytest

from site_calc_investment.mcp.scenario import ScenarioStore


@pytest.fixture
def store() -> ScenarioStore:
    """Fresh ScenarioStore for each test."""
    return ScenarioStore()


@pytest.fixture
def scenario_id(store: ScenarioStore) -> str:
    """Pre-created scenario with timespan set."""
    sid = store.create(name="Test Scenario", description="For testing")
    store.set_timespan(sid, start_year=2025, years=1)
    return sid


@pytest.fixture
def tmp_csv(tmp_path: object) -> Generator[str, None, None]:
    """Create a temporary CSV file with 8760 price values."""
    import pathlib

    path = pathlib.Path(str(tmp_path)) / "prices.csv"
    with open(path, "w", newline="") as f:
        f.write("hour,price_eur\n")
        for i in range(8760):
            hour_of_day = i % 24
            price = 40.0 if 9 <= hour_of_day <= 20 else 25.0
            f.write(f"{i},{price}\n")
    yield str(path)


@pytest.fixture
def tmp_json(tmp_path: object) -> Generator[str, None, None]:
    """Create a temporary JSON file with 8760 price values."""
    import pathlib

    path = pathlib.Path(str(tmp_path)) / "prices.json"
    prices = []
    for i in range(8760):
        hour_of_day = i % 24
        prices.append(40.0 if 9 <= hour_of_day <= 20 else 25.0)
    with open(path, "w") as f:
        json.dump(prices, f)
    yield str(path)


@pytest.fixture
def tmp_csv_no_header(tmp_path: object) -> Generator[str, None, None]:
    """Create a temporary CSV file without headers."""
    import pathlib

    path = pathlib.Path(str(tmp_path)) / "prices_no_header.csv"
    with open(path, "w", newline="") as f:
        for i in range(100):
            f.write(f"{float(i)}\n")
    yield str(path)


@pytest.fixture
def mock_job_response() -> dict:
    """Mock job creation response."""
    return {
        "job_id": "test_job_mcp_123",
        "status": "pending",
        "created_at": "2025-01-01T10:00:00+01:00",
        "message": "Job created successfully",
    }


@pytest.fixture
def mock_result_response() -> dict:
    """Mock API response from /api/v1/jobs/{job_id}/result endpoint."""
    return {
        "job_id": "test_job_mcp_123",
        "status": "completed",
        "result": {
            "sites": {
                "site_sc_test": {
                    "device_schedules": {
                        "Battery1": {
                            "flows": {"electricity": [2.0] * 100},
                            "soc": [0.5] * 100,
                        }
                    },
                    "grid_flows": {"import": [0.0] * 100, "export": [2.0] * 100},
                }
            },
            "summary": {
                "total_da_revenue": 142500.0,
                "total_cost": 42500.0,
                "expected_profit": 100000.0,
                "solver_status": "optimal",
                "solve_time_seconds": 1.8,
                "sites_count": 1,
            },
            "investment_metrics": {
                "npv": 850000.0,
                "irr": 0.15,
                "payback_period_years": 4.5,
                "total_revenue_10y": 1425000.0,
                "total_costs_10y": 425000.0,
                "annual_revenue_by_year": [142500.0] * 10,
                "annual_costs_by_year": [42500.0] * 10,
            },
        },
    }
