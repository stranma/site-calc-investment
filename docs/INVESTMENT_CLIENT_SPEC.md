# Investment Client Specification

**Package:** `site-calc-investment`
**Version:** 1.0.0
**Purpose:** Long-term capacity planning and investment ROI analysis

---

## 1. Overview

The investment client provides Python bindings for the Site-Calc optimization API focused on **long-term planning**:

- Capacity sizing and technology selection
- Investment ROI and NPV analysis
- Multi-year operational simulation
- Strategic planning (1-10 years)

### 1.1 Key Capabilities

| Feature | Value |
|---------|-------|
| **Max Horizon** | 100,000 intervals (~11 years) |
| **Resolution** | 1-hour only |
| **ANS Optimization** | ❌ No |
| **Binary Variables** | ⚠️ Relaxed to continuous |
| **Timeout** | 3600 seconds (1 hour) |
| **Endpoints** | `/device-planning` only |

### 1.2 Use Cases

1. **Capacity Planning** - Determine optimal size for batteries, CHP, solar arrays
2. **Investment Analysis** - Calculate NPV, IRR, payback period for technology investments
3. **Scenario Comparison** - Compare different device configurations over 10-year horizon
4. **Strategic Planning** - Long-term revenue and cost projections

### 1.3 Differences from Operational Client

| Feature | Operational | Investment |
|---------|-------------|------------|
| Time horizon | Days | Years |
| Resolution | 15-min or 1-hour | 1-hour only |
| ANS optimization | Yes | No |
| Binary CHP | Yes (on/off) | No (continuous modulation) |
| Focus | Bidding & dispatch | Capacity & ROI |

---

## 2. Installation

```bash
pip install site-calc-investment
```

### 2.1 Dependencies

- Python ≥ 3.10
- pydantic ≥ 2.0
- httpx ≥ 0.24
- python-dateutil ≥ 2.8
- numpy ≥ 1.24 (for financial calculations)

---

## 3. Authentication

Investment client requires API key with `inv_` prefix:

```python
from site_calc_investment import InvestmentClient

client = InvestmentClient(
    base_url="https://api.site-calc.example.com",
    api_key="inv_9876543210fedcba"  # Must start with 'inv_'
)
```

---

## 4. Core Models

### 4.1 TimeSpan

Time period for long-term optimization:

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from site_calc_investment.models import TimeSpan, Resolution

# 10 years at 1-hour resolution
ts = TimeSpan(
    start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
    intervals=87600,  # 10 years × 8760 hours/year
    resolution=Resolution.HOUR_1
)

# Helper for full years
ts = TimeSpan.for_years(
    start_year=2025,
    years=10,
    resolution=Resolution.HOUR_1
)

# Access computed properties
print(ts.end)         # 2035-01-01 00:00:00+01:00
print(ts.duration)    # timedelta(days=3650)
print(ts.years)       # 10.0
```

**Validation:**
- `start` must use `Europe/Prague` timezone
- `intervals` ≤ 100,000
- **Only** `1h` resolution supported (15-min not allowed)

### 4.2 Device Models

Device models are **identical to operational** except:
- ❌ **NO** `ancillary_services` field
- ✅ CHP `is_binary` automatically treated as continuous

#### 4.2.1 Battery

```python
from site_calc_investment.models import Battery

battery = Battery(
    name="Battery1",
    properties={
        "capacity": 10.0,          # MWh
        "max_power": 5.0,          # MW
        "efficiency": 0.90,        # 0-1
        "initial_soc": 0.5         # 0-1
    }
    # No ancillary_services field!
)
```

#### 4.2.2 CHP

```python
from site_calc_investment.models import CHP

chp = CHP(
    name="CHP1",
    properties={
        "gas_input": 8.0,
        "el_output": 3.0,
        "heat_output": 4.0,
        "is_binary": False  # Treated as continuous for investment planning
    },
    schedule={
        "max_hours_per_day": 20.0
    }
)
```

**Note:** Even if `is_binary=True`, the optimizer will relax to continuous operation for computational tractability over long horizons.

#### 4.2.3 Market Devices

```python
from site_calc_investment.models import ElectricityImport, ElectricityExport

# Prices for 10 years (87,600 hourly values)
prices_10y = generate_prices_with_escalation(
    base_year_prices=[30.0] * 8760,
    years=10,
    escalation_rate=0.02  # 2% annual increase
)

grid_import = ElectricityImport(
    name="GridImport",
    properties={
        "price": prices_10y,  # 87,600 values
        "max_import": 8.0
    }
)
```

### 4.3 Investment Parameters

New model for financial analysis:

```python
from site_calc_investment.models import InvestmentParameters

inv_params = InvestmentParameters(
    discount_rate=0.05,  # 5% discount rate for NPV
    device_capital_costs={
        "Battery1": 500000,    # €500k CAPEX
        "CHP1": 1200000,       # €1.2M CAPEX
        "PV1": 2000000         # €2M CAPEX
    },
    device_annual_opex={
        "Battery1": 5000,      # €5k/year O&M
        "CHP1": 30000,         # €30k/year O&M
        "PV1": 20000           # €20k/year O&M
    },
    price_escalation_rate=0.02  # 2% annual inflation
)
```

### 4.4 Site Model

```python
from site_calc_investment.models import Site

site = Site(
    site_id="investment_analysis_site",
    description="10-year capacity planning scenario",
    devices=[
        battery,
        chp,
        heat_accumulator,
        pv,
        grid_import,
        grid_export,
        gas_import
    ]
)
```

---

## 5. API Methods

### 5.1 Long-Term Planning

```python
from site_calc_investment import InvestmentClient
from site_calc_investment.models import (
    InvestmentPlanningRequest,
    OptimizationConfig,
    TimeSpan,
    Resolution
)

client = InvestmentClient(base_url="...", api_key="inv_...")

# 10-year planning horizon
timespan = TimeSpan(
    start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
    intervals=87600,  # 10 years
    resolution=Resolution.HOUR_1
)

request = InvestmentPlanningRequest(
    sites=[site],
    timespan=timespan,
    investment_parameters=inv_params,
    optimization_config=OptimizationConfig(
        objective="maximize_npv",
        time_limit_seconds=3600,  # 1 hour timeout
        relax_binary_variables=True
    )
)

# Submit job
job = client.create_planning_job(request)
print(f"Job ID: {job.job_id}")

# Wait for completion (longer poll interval for long jobs)
result = client.wait_for_completion(
    job.job_id,
    poll_interval=30,  # Check every 30 seconds
    timeout=7200       # 2 hour max wait
)

# Access investment metrics
metrics = result.summary.investment_metrics
print(f"NPV: €{metrics.npv:,.0f}")
print(f"IRR: {metrics.irr*100:.2f}%")
print(f"Payback: {metrics.payback_period_years:.1f} years")
```

### 5.2 Scenario Comparison

```python
from site_calc_investment.analysis import compare_scenarios

# Scenario 1: 5 MW battery
battery_5mw = Battery(name="Battery1", properties={"capacity": 5.0, "max_power": 2.5, ...})
site_1 = Site(site_id="scenario_5mw", devices=[battery_5mw, ...])

# Scenario 2: 10 MW battery
battery_10mw = Battery(name="Battery1", properties={"capacity": 10.0, "max_power": 5.0, ...})
site_2 = Site(site_id="scenario_10mw", devices=[battery_10mw, ...])

# Run both optimizations
result_1 = client.create_planning_job(
    InvestmentPlanningRequest(sites=[site_1], timespan=timespan, ...)
)
result_2 = client.create_planning_job(
    InvestmentPlanningRequest(sites=[site_2], timespan=timespan, ...)
)

# Wait for both
result_1 = client.wait_for_completion(result_1.job_id)
result_2 = client.wait_for_completion(result_2.job_id)

# Compare
comparison = compare_scenarios([result_1, result_2], names=["5 MW", "10 MW"])
print(comparison)  # DataFrame with NPV, IRR, costs, revenues
```

---

## 6. Financial Analysis Helpers

### 6.1 NPV Calculation

```python
from site_calc_investment.analysis import calculate_npv

# Annual cash flows from optimization result
annual_cash_flows = result.summary.investment_metrics.annual_revenue_by_year

# Calculate NPV with custom discount rate
npv = calculate_npv(
    cash_flows=annual_cash_flows,
    discount_rate=0.05,
    initial_investment=-1500000  # €1.5M CAPEX
)
print(f"NPV: €{npv:,.0f}")
```

### 6.2 IRR Calculation

```python
from site_calc_investment.analysis import calculate_irr

# Full cash flow series (initial + annual)
cash_flows = [-1500000] + annual_cash_flows  # Prepend CAPEX

irr = calculate_irr(cash_flows)
print(f"IRR: {irr*100:.2f}%")
```

### 6.3 Payback Period

```python
from site_calc_investment.analysis import calculate_payback_period

payback = calculate_payback_period(cash_flows)
print(f"Payback: {payback:.1f} years")
```

### 6.4 Annual Aggregation

```python
from site_calc_investment.analysis import aggregate_annual

# Extract annual revenue from hourly schedule
annual_revenues = aggregate_annual(
    hourly_values=result.sites["site1"].grid_flows["export"],
    prices=grid_export_prices,
    years=10
)
# Returns: [year1_revenue, year2_revenue, ..., year10_revenue]
```

---

## 7. Response Models

### 7.1 Investment Metrics

```python
{
    "investment_metrics": {
        "total_revenue_10y": 5000000.0,      # Total revenue over horizon
        "total_costs_10y": 3000000.0,        # Total costs (fuel, O&M)
        "npv": 1250000.0,                    # Net present value
        "irr": 0.12,                         # Internal rate of return (12%)
        "payback_period_years": 6.2,         # Simple payback
        "annual_revenue_by_year": [          # Year-by-year breakdown
            450000, 465000, 480000, 495000, 510000,
            525000, 540000, 555000, 570000, 585000
        ],
        "annual_costs_by_year": [
            250000, 260000, 270000, 280000, 290000,
            300000, 310000, 320000, 330000, 340000
        ]
    }
}
```

### 7.2 Device Schedule (87,600 intervals)

```python
{
    "Battery1": {
        "flows": {
            "electricity": [2.0, -1.5, 0.5, ...]  # 87,600 hourly values (MW)
        },
        "soc": [0.5, 0.48, 0.47, ...],            # 87,600 values (0-1)
        # No ancillary_reservations field
    },
    "CHP1": {
        "flows": {
            "gas": [-8.0, -4.0, -6.0, ...],       # 87,600 values (MW)
            "electricity": [3.0, 1.5, 2.25, ...], # Continuous operation
            "heat": [4.0, 2.0, 3.0, ...]
        }
        # No binary_status (treated as continuous)
    }
}
```

---

## 8. Error Handling

```python
from site_calc_investment.exceptions import (
    ApiError,
    ValidationError,
    ForbiddenFeatureError,
    LimitExceededError
)

try:
    result = client.create_planning_job(request)
except ValidationError as e:
    if e.code == "invalid_resolution":
        print("Investment client only supports 1-hour resolution")
except ForbiddenFeatureError as e:
    if "ancillary_services" in str(e):
        print("Remove ancillary_services from devices")
except LimitExceededError as e:
    print(f"Exceeded {e.max_allowed} interval limit")
```

---

## 9. Complete Example: Battery Sizing

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from site_calc_investment import InvestmentClient
from site_calc_investment.models import (
    TimeSpan, Resolution, Site, Battery, ElectricityImport, ElectricityExport,
    InvestmentPlanningRequest, InvestmentParameters, OptimizationConfig
)
from site_calc_investment.analysis import compare_scenarios

# Initialize client
client = InvestmentClient(
    base_url="https://api.site-calc.example.com",
    api_key="inv_9876543210fedcba"
)

# 10-year horizon
timespan = TimeSpan(
    start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
    intervals=87600,
    resolution=Resolution.HOUR_1
)

# Generate prices (2% annual escalation)
base_prices = [30.0 + 10*abs(h-12)/12 for h in range(24)] * 365  # Daily pattern
prices_10y = []
for year in range(10):
    year_prices = [p * (1.02 ** year) for p in base_prices]
    prices_10y.extend(year_prices)

# Test three battery sizes
scenarios = []
for capacity in [5.0, 10.0, 15.0]:
    battery = Battery(
        name="Battery1",
        properties={
            "capacity": capacity,
            "max_power": capacity / 2,  # 2-hour discharge
            "efficiency": 0.90,
            "initial_soc": 0.5
        }
    )

    site = Site(
        site_id=f"battery_{capacity}mw",
        devices=[
            battery,
            ElectricityImport(name="GridImport", properties={"price": prices_10y, "max_import": 20.0}),
            ElectricityExport(name="GridExport", properties={"price": prices_10y, "max_export": 20.0})
        ]
    )

    inv_params = InvestmentParameters(
        discount_rate=0.05,
        device_capital_costs={"Battery1": capacity * 100000},  # €100k/MW
        device_annual_opex={"Battery1": capacity * 1000}       # €1k/MW/year
    )

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
    scenarios.append((f"{capacity} MW", result))

# Compare scenarios
comparison = compare_scenarios(
    [s[1] for s in scenarios],
    names=[s[0] for s in scenarios]
)

print("\n=== Battery Sizing Comparison ===")
print(comparison)

# Find optimal size
best = max(scenarios, key=lambda s: s[1].summary.investment_metrics.npv)
print(f"\nOptimal size: {best[0]}")
print(f"NPV: €{best[1].summary.investment_metrics.npv:,.0f}")
print(f"IRR: {best[1].summary.investment_metrics.irr*100:.2f}%")
```

---

## 10. Validation Rules

### 10.1 TimeSpan Validation

- Maximum 100,000 intervals
- **Only** 1-hour resolution (15-min rejected)
- Timezone must be `Europe/Prague`

### 10.2 Forbidden Features

Investment clients will receive validation errors if:
- Any device has `ancillary_services` field
- Request includes `locked_reservations`
- Resolution is `15min`

### 10.3 Array Length

All time-series arrays must have length matching `timespan.intervals`:

```python
# For 10 years at 1-hour:
timespan.intervals == 87600

# All these must be 87,600 elements:
- grid_import.properties["price"]
- demand.properties["max_demand_profile"]
- schedule.can_run (if provided)
```

---

## 11. Performance Considerations

### 11.1 Solve Times

Typical solve times for 10-year horizon:

| Complexity | Solve Time |
|------------|------------|
| Simple (battery only) | 5-15 min |
| Medium (battery + CHP) | 15-45 min |
| Complex (multi-site, many devices) | 30-60 min |

### 11.2 Binary Variable Relaxation

To make 10-year problems tractable:
- CHP `is_binary` automatically relaxed to continuous
- CHP can operate at any power level between 0-100%
- No on/off switching constraints applied

### 11.3 Memory Requirements

- Client memory: ~500 MB for request serialization
- Server memory: 5-20 GB during optimization
- Response size: 10-50 MB (gzipped)

---

## 12. Typical Workflows

### 12.1 Capacity Sizing

1. Define base site configuration
2. Create variants with different device sizes
3. Run optimizations for each variant
4. Compare NPV, IRR, payback period
5. Select optimal configuration

### 12.2 Technology Selection

1. Create scenarios with different technologies (e.g., CHP vs. heat pump)
2. Use same load profiles and prices for fair comparison
3. Compare investment metrics
4. Perform sensitivity analysis on key parameters

### 12.3 Sensitivity Analysis

```python
from site_calc_investment.analysis import sensitivity_analysis

# Test NPV sensitivity to discount rate
discount_rates = [0.03, 0.04, 0.05, 0.06, 0.07]
npvs = []

for rate in discount_rates:
    inv_params.discount_rate = rate
    job = client.create_planning_job(request)
    result = client.wait_for_completion(job.job_id)
    npvs.append(result.summary.investment_metrics.npv)

# Plot NPV vs. discount rate
plot_sensitivity(discount_rates, npvs, xlabel="Discount Rate", ylabel="NPV (€)")
```

---

## 13. Limits and Constraints

| Limit | Value |
|-------|-------|
| Max intervals | 100,000 |
| Max sites | 50 |
| Max devices per site | 30 |
| Request timeout | 3600 seconds |
| Request size | 50 MB |
| Resolution | 1-hour only |

---

## 14. Differences from Operational Client

### 14.1 Removed Features

- ❌ No `/optimal-bidding` endpoint
- ❌ No `ancillary_services` on devices
- ❌ No `locked_reservations`
- ❌ No 15-minute resolution
- ❌ No binary CHP operation

### 14.2 Added Features

- ✅ Investment metrics (NPV, IRR, payback)
- ✅ Financial analysis helpers
- ✅ Scenario comparison utilities
- ✅ Annual aggregation functions
- ✅ Price escalation modeling

### 14.3 Modified Behavior

- CHP `is_binary` ignored (always continuous)
- Longer timeouts (3600s vs 300s)
- Longer default poll intervals (30s vs 5s)

---

## 15. Migration Guide

Coming from operational client:

```python
# Operational
from site_calc_operational import OperationalClient
client = OperationalClient(api_key="op_...")
# 296 intervals, ANS optimization, 15-min resolution

# Investment
from site_calc_investment import InvestmentClient
client = InvestmentClient(api_key="inv_...")
# 100,000 intervals, NO ANS, 1-hour only
```

**Key changes:**
1. Change API key prefix from `op_` to `inv_`
2. Remove all `ancillary_services` from devices
3. Change resolution to `1h` (remove `15min`)
4. Increase `intervals` for long-term planning
5. Add `investment_parameters` for financial analysis

---

## 16. Support

- **Documentation**: https://docs.site-calc.example.com/investment-client
- **Issues**: https://github.com/site-calc/investment-client/issues
- **Examples**: https://github.com/site-calc/investment-client/tree/main/examples
