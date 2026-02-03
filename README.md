# Site-Calc Investment Client

Python client for Site-Calc investment planning API - long-term capacity planning and ROI analysis.

## Installation

```bash
pip install site-calc-investment
```

## Quick Start

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from site_calc_investment import InvestmentClient
from site_calc_investment.models import (
    Resolution, Site, Battery, ElectricityImport, ElectricityExport,
    InvestmentPlanningRequest, InvestmentParameters, OptimizationConfig
)
from site_calc_investment.models.requests import TimeSpanInvestment

# Initialize client
client = InvestmentClient(
    base_url="https://api.site-calc.example.com",
    api_key="inv_your_api_key_here"
)

# Create 1-week planning horizon (1-hour resolution)
timespan = TimeSpanInvestment(
    start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
    intervals=168,  # 1 week = 7 days × 24 hours
    resolution=Resolution.HOUR_1
)

# Generate hourly prices (example: day/night pattern)
prices = [30.0 if h % 24 < 6 else 80.0 if 8 <= h % 24 < 20 else 50.0 for h in range(168)]

# Define devices (NO ancillary_services field)
battery = Battery(
    name="Battery1",
    properties={
        "capacity": 10.0,
        "max_power": 5.0,
        "efficiency": 0.90,
        "initial_soc": 0.5
    }
)

grid_import = ElectricityImport(
    name="GridImport",
    properties={"price": prices, "max_import": 10.0}
)

grid_export = ElectricityExport(
    name="GridExport",
    properties={"price": prices, "max_export": 10.0}
)

site = Site(site_id="investment_site", devices=[battery, grid_import, grid_export])

# Investment parameters
inv_params = InvestmentParameters(
    discount_rate=0.05,
    project_lifetime_years=10,                  # Required field
    device_capital_costs={"Battery1": 500000},  # €500k CAPEX
    device_annual_opex={"Battery1": 5000}       # €5k/year O&M
)

# Create and submit optimization request
request = InvestmentPlanningRequest(
    sites=[site],
    timespan=timespan,
    investment_parameters=inv_params,
    optimization_config=OptimizationConfig(
        objective="maximize_profit",  # Options: maximize_profit, minimize_cost, maximize_self_consumption
        time_limit_seconds=300        # Max 900 seconds (15 min)
    )
)

job = client.create_planning_job(request)
result = client.wait_for_completion(job.job_id, poll_interval=5, timeout=600)

print(f"Status: {result.status}")
print(f"Solver: {result.summary.solver_status}")
print(f"Profit: €{result.summary.expected_profit:,.2f}")
```

## Features

- ✅ Long-term capacity planning (1-10 years)
- ✅ Investment ROI analysis (NPV, IRR, payback)
- ✅ Scenario comparison utilities
- ✅ Financial analysis helpers
- ✅ 1-hour resolution optimization
- ✅ Multi-site optimization
- ✅ Type-safe Pydantic models
- ✅ Automatic retry and error handling
- ✅ Job management (cancel single or all jobs)

## Capabilities

| Feature | Value |
|---------|-------|
| Max Horizon | 100,000 intervals (~11 years at 1-hour) |
| Resolution | 1-hour only |
| ANS Support | No |
| Binary Variables | Relaxed to continuous |
| Timeout | 900 seconds (15 minutes) max |

## Supported Devices

- Battery (NO ANS)
- CHP - Combined Heat and Power (continuous operation)
- Heat Accumulator
- Photovoltaic
- Heat Demand
- Electricity Demand
- Electricity Import/Export (market interface)
- Gas Import (market interface)
- Heat Export (market interface)

## Job Management

The client provides methods for managing optimization jobs:

```python
# Create a job
job = client.create_planning_job(request)
print(f"Job ID: {job.job_id}")

# Check job status
status = client.get_job_status(job.job_id)
print(f"Status: {status.status}, Progress: {status.progress}%")

# Wait for completion
result = client.wait_for_completion(job.job_id, poll_interval=30, timeout=7200)

# Cancel a single job
cancelled = client.cancel_job(job.job_id)

# Cancel all pending/running jobs (bulk cancel)
result = client.cancel_all_jobs()
print(f"Cancelled {result['cancelled_count']} jobs")
```

## Financial Analysis

```python
from site_calc_investment.analysis import (
    calculate_npv,
    calculate_irr,
    calculate_payback_period,
    compare_scenarios
)

# NPV calculation
npv = calculate_npv(
    cash_flows=annual_revenues,
    discount_rate=0.05,
    initial_investment=-1500000
)

# IRR calculation
irr = calculate_irr([-1500000] + annual_revenues)

# Scenario comparison
comparison = compare_scenarios(
    [result_5mw, result_10mw, result_15mw],
    names=["5 MW", "10 MW", "15 MW"]
)
print(comparison)  # DataFrame with NPV, IRR, costs, revenues
```

## Documentation

Full documentation available at: https://github.com/stranma/site-calc-investment#readme

## Examples

See `examples/` directory for complete examples:
- `capacity_planning.py` - 10-year capacity planning workflow
- `roi_analysis.py` - Investment ROI calculation
- `scenario_comparison.py` - Compare device configurations

## Requirements

- Python ≥ 3.10
- API key with `inv_` prefix (investment client)

## Key Differences from Operational Client

- ❌ No `/optimal-bidding` endpoint
- ❌ No `ancillary_services` on devices
- ❌ No 15-minute resolution (1-hour only)
- ✅ Up to 100,000 intervals (vs. 296)
- ✅ Investment metrics (NPV, IRR, payback)
- ✅ Financial analysis helpers

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
ruff format .

# Type check
mypy site_calc_investment
```

## License

MIT License

## Support

- Issues: https://github.com/stranma/site-calc-investment/issues
- Documentation: https://github.com/stranma/site-calc-investment#readme

---

Part of the [Site-Calc](https://github.com/stranma/site-calc) platform.
