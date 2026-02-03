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
    TimeSpan, Resolution, Site, Battery, ElectricityImport,
    InvestmentPlanningRequest, InvestmentParameters, OptimizationConfig
)

# Initialize client
client = InvestmentClient(
    base_url="https://api.site-calc.example.com",
    api_key="inv_your_api_key_here"
)

# Create 10-year planning horizon (1-hour resolution)
timespan = TimeSpan(
    start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
    intervals=87600,  # 10 years × 8760 hours/year
    resolution=Resolution.HOUR_1
)

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
    properties={"price": prices_10y, "max_import": 8.0}
)

site = Site(site_id="investment_site", devices=[battery, grid_import])

# Investment parameters
inv_params = InvestmentParameters(
    discount_rate=0.05,
    device_capital_costs={"Battery1": 500000},  # €500k CAPEX
    device_annual_opex={"Battery1": 5000}       # €5k/year O&M
)

# Create and submit optimization request
request = InvestmentPlanningRequest(
    sites=[site],
    timespan=timespan,
    investment_parameters=inv_params,
    optimization_config=OptimizationConfig(
        objective="maximize_npv",
        time_limit_seconds=3600
    )
)

job = client.create_planning_job(request)
result = client.wait_for_completion(job.job_id, poll_interval=30, timeout=7200)

# Display investment metrics
metrics = result.summary.investment_metrics
print(f"NPV: €{metrics.npv:,.0f}")
print(f"IRR: {metrics.irr*100:.2f}%")
print(f"Payback: {metrics.payback_period_years:.1f} years")
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
| Timeout | 3600 seconds (1 hour) |

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

Full documentation available at: https://docs.site-calc.example.com/investment-client

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
