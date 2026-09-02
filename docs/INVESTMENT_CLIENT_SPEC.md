# Investment Client Specification

**Package:** `site-calc-investment`
**Version:** 1.3.0
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
| **Timeout** | 3600 seconds (60 minutes) max |
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
    api_key="inv_9876543210fedcba",  # Must start with 'inv_'
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
    resolution=Resolution.HOUR_1,
)

# Helper for full years
ts = TimeSpan.for_years(start_year=2025, years=10, resolution=Resolution.HOUR_1)

# Access computed properties. Note: intervals count fixed 8760-hour years,
# so leap days are NOT included -- a "10-year" horizon is 3650 days and its
# end lands slightly before the calendar decade boundary.
print(ts.duration)  # timedelta(days=3650)
print(ts.years)  # 10.0
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
        "capacity": 10.0,  # MWh
        "max_power": 5.0,  # MW
        "efficiency": 0.90,  # 0-1
        "initial_soc": 0.5,  # 0-1
    },
    # Optional fixed costs for client-side NPV/IRR (never sent to the API):
    investment={"capital_cost": 500000, "annual_opex": 5000},
    # No ancillary_services field!
)
```

Every device accepts the optional `investment` block
(`{"capital_cost": EUR, "annual_opex": EUR/year}`). It is used only by the
client-side financial analysis (`calculate_investment_metrics`) and is
stripped from the API payload. For capacity costs the optimizer should trade
off, use sizing reservations instead (see Section 4.4):

- `power_sizing` -- the optimizer sizes installed power (MW) up to
  `max_power`, priced by a tariff menu (use `periods="horizon"` for a
  one-shot investment cost in EUR/MW).
- `capacity_sizing` -- the optimizer sizes energy capacity (MWh) up to
  `capacity`, priced by a tariff menu (use `periods="horizon"` for a
  one-shot investment cost in EUR/MWh). An optimizer-sized capacity must
  start empty: `initial_soc` defaults to 0 for sizing runs and must not
  be set above 0 (fix `reserved` to keep a non-zero initial SOC).
- `degradation_yearly` -- yearly capacity degradation curve in percent,
  one entry per model year: `[5, 3, 2]` = 5% in year 1, 3% in year 2,
  2% in year 3. The curve must include at least one entry for every
  model year in the horizon; shorter curves are rejected rather than
  extended by repeating or filling from the last entry. Longer curves
  are allowed and extra entries are ignored -- a full-lifetime curve can
  serve shorter runs. Caps the usable stored energy at
  `prod(1 - d/100)` times the energy the battery actually has -- the
  fixed `reserved` energy when `capacity_sizing` is present, otherwise
  `capacity` -- via a stepwise per-interval bound; each year's loss
  applies from the START of the year it occurs (prepend `0` for an
  undegraded first year). `initial_soc` must not exceed the year-1
  factor (the stock default adapts automatically). Model years are
  fixed 8760-hour blocks matching the annual-aggregation convention
  (no leap days). Power ratings are unaffected. Not combinable with SOC
  anchor points or an optimizer-sized `capacity_sizing`.

#### 4.2.2 CHP

```python
from site_calc_investment.models import CHP

chp = CHP(
    name="CHP1",
    properties={
        "gas_input": 8.0,
        "el_output": 3.0,
        "heat_output": 4.0,
        "is_binary": False,  # Treated as continuous for investment planning
    },
    schedule={"max_hours_per_day": 20.0},
)
```

**Note:** Even if `is_binary=True`, the optimizer will relax to continuous operation for computational tractability over long horizons.

#### 4.2.3 Profile Devices (PV, fixed and steerable production/consumption)

```python
from site_calc_investment.models import (
    PhotovoltaicNonSteerable,  # produces exactly power_profile
    PhotovoltaicSteerable,  # produces in [0, max_power_profile], curtailable
    FixedProduction,  # same semantics as nonsteerable PV
    MaxPowerProduction,  # steerable production at cost_per_mwh (EUR/MWh)
    FixedConsumption,  # consumes exactly power_profile
    MaxPowerConsumption,  # steerable consumption worth value_per_mwh (EUR/MWh)
)

pv = PhotovoltaicSteerable(
    name="FVE",
    properties={
        "max_power_profile": [0.0, 0.0, 1.2, 3.5, 4.8, 3.1, 0.9, 0.0] * 1095,  # MW per interval
    },
)

flex_load = MaxPowerConsumption(
    name="Electrolyzer",
    properties={
        "max_power_profile": [3.0] * 8760,  # MW
        "value_per_mwh": 50.0,  # consumes only when price < 50 EUR/MWh
    },
)
```

All profiles are absolute power in MW per interval, matching the timespan length. The steerable variants let the optimizer curtail production (e.g. at negative prices) or shift consumption to cheap hours.

#### 4.2.4 Market Devices

```python
from site_calc_investment.models import ElectricityImport, ElectricityExport

# Prices for 10 years (87,600 hourly values), e.g. with 2% annual escalation
base_year_prices = [30.0] * 8760
prices_10y = [p * (1.02**year) for year in range(10) for p in base_year_prices]

grid_import = ElectricityImport(
    name="GridImport",
    properties={
        "price": prices_10y,  # 87,600 values
        "max_import": 8.0,
    },
)
```

**Net-metered connection with an overflow price.** When consumption is
billed at one price and the surplus fed back to the grid is paid at
another, use `ElectricityImportWithOverflow` instead of a separate
import + export pair. The connection is either importing or exporting in
any hour, never both, which is what the meter settles; a free-standing
pair would otherwise sell the site's generation and buy its load in the
same hour whenever the overflow price is above the import price.

```python
from site_calc_investment.models import ElectricityImportWithOverflow

grid = ElectricityImportWithOverflow(
    name="Grid",
    properties={
        "import_price": prices_10y,
        "overflow_price": [p * 0.7 for p in prices_10y],
        "max_import": 2.0,  # real connection capacity (MW)
        "max_overflow": 2.0,  # defaults to max_import
    },
)
```

It is sent to the API as an `electricity_import` named `Grid` plus an
`electricity_export` named `Grid_overflow` paired with it, so results
contain two device schedules. Set `no_simultaneous_flow=False` to relax
the one-direction rule. A hand-built `ElectricityExport` can pair with an
`ElectricityImport` or `CzDistributionImport` the same way through its
`exclusive_with` property (the import's name).

Market device properties accept only their documented fields (unknown fields
raise validation errors):

- `electricity_import`: `price`, `max_import`, optional `capacity_reservation`
- `electricity_export`: `price`, `max_export`, optional `capacity_reservation`,
  optional `exclusive_with` (name of the paired import)
- `gas_import`: `price`, `max_import`
- `heat_export`: `price`, `max_export`

### 4.3 Investment Parameters

Global financial parameters only:

```python
from site_calc_investment.models import InvestmentParameters

inv_params = InvestmentParameters(
    discount_rate=0.05,  # 5% discount rate for NPV
    project_lifetime_years=10,  # Required
)
```

Unknown fields are rejected with a validation error (`extra="forbid"`).
Per-device CAPEX/OPEX lives on each device's `investment` block (Section
4.2.1); optimizer-priced capacity costs are expressed as capacity
reservations on the devices themselves (Section 4.4).

### 4.4 Capacity Reservations

A `CapacityReservation` puts a per-billing-period capacity limit and charge on
a device flow. The watched flow can never exceed the reserved capacity `R`;
every billing period intersecting the horizon is billed in full.

Fields:

| Field | Description |
|-------|-------------|
| `periods` | `"calendar_month"`, `"calendar_year"`, or `"horizon"` (one period covering the whole optimization) |
| `tariffs` | Price menu (list of `CapacityTariff`); empty list declares an unpriced pure limit |
| `reserved` | Fixed contracted capacity (MW); `None` lets the optimizer size `R` |
| `min_reserved` / `max_reserved` | Bounds for an optimized `R` (MW); `max_reserved` defaults to the device's maximum flow |
| `timezone` | IANA billing timezone (e.g. `"Europe/Prague"`) for calendar-period boundaries |

Each `CapacityTariff` has a `name`, `reserved_price` (EUR per MW of `R` per
period), `peak_price` (EUR per MW of the period's measured peak), and an
optional `fixed_price` (EUR per period). Per billing period the charge is
`fixed_price + reserved_price * R + peak_price * peak`. With several tariffs
on one reservation, the cheapest tariff is assigned automatically each
period. Optimizing `R` (i.e. `reserved=None`) requires every tariff to have
`reserved_price > 0`.

Capacity reservations appear in three places:

1. `capacity_reservation` on `electricity_import` / `electricity_export`
   properties (e.g. monthly grid capacity tariffs)
2. `power_sizing` / `capacity_sizing` on battery properties (investment
   sizing; see Section 4.2.1)
3. The `cz_distribution_import` device type, a convenience wrapper for the
   Czech distribution tariff (see below)

Example -- optimizer-sized battery power with a one-shot investment cost:

```python
from site_calc_investment.models import Battery

battery = Battery(
    name="BESS",
    properties={
        "capacity": 20.0,  # MWh
        "max_power": 10.0,  # MW -- sizing ceiling
        "efficiency": 0.90,
        "power_sizing": {
            "periods": "horizon",
            "tariffs": [
                # One-shot investment cost: 95,000 EUR per installed MW
                {"name": "capex", "reserved_price": 95000, "peak_price": 0}
            ],
            # reserved omitted -> the optimizer sizes installed power
        },
    },
)
```

Example -- Czech distribution-tariff import (2027 tariff structure):

```python
from site_calc_investment.models import CzDistributionImport

grid = CzDistributionImport(
    name="Grid",
    properties={
        "price": prices,  # EUR/MWh energy price profile
        "max_import": 10.0,  # physical connection limit (MW)
        "t1_reserved_price": 86000,  # EUR/MW/month
        "t1_peak_price": 30000,  # EUR/MW/month
        "t2_reserved_price": 65000,  # EUR/MW/month
        "t2_peak_price": 95000,  # EUR/MW/month
        "reserved_capacity": None,  # None -> optimizer sizes it
        # "timezone": "Europe/Prague" (default)
    },
)
```

Billing is monthly; each month is billed by whichever of T1/T2 is cheaper
(automatic assignment). On the wire the device is serialized as a plain
`electricity_import` with the equivalent monthly `capacity_reservation`
carrying the T1/T2 price menu.

### 4.5 Site Model

```python
from site_calc_investment.models import Site

site = Site(
    site_id="investment_analysis_site",
    description="10-year capacity planning scenario",
    devices=[battery, chp, heat_accumulator, pv, grid_import, grid_export, gas_import],
)
```

---

## 5. API Methods

### 5.1 Long-Term Planning

```python
from site_calc_investment import InvestmentClient
from site_calc_investment.models import InvestmentPlanningRequest, OptimizationConfig, Resolution
from site_calc_investment.models.requests import TimeSpanInvestment

client = InvestmentClient(base_url="...", api_key="inv_...")

# 10-year planning horizon
timespan = TimeSpanInvestment(
    start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
    intervals=87600,  # 10 years
    resolution=Resolution.HOUR_1,
)

request = InvestmentPlanningRequest(
    sites=[site],
    timespan=timespan,
    investment_parameters=inv_params,
    optimization_config=OptimizationConfig(
        objective="maximize_profit",
        time_limit_seconds=3600,  # 60 minute maximum
        mip_gap=0.01,  # stop within 1% of the proven optimum (default)
        relax_binary_variables=True,
    ),
)

# Submit job
job = client.create_planning_job(request)
print(f"Job ID: {job.job_id}")

# Wait for completion (longer poll interval for long jobs)
result = client.wait_for_completion(
    job.job_id,
    poll_interval=30,  # Check every 30 seconds
    timeout=7200,  # 2 hour max wait
)

# Compute investment metrics client-side from the annual aggregates
from site_calc_investment.analysis import calculate_investment_metrics

metrics = calculate_investment_metrics(
    annual_revenues=result.investment_metrics.annual_revenue_by_year,
    annual_costs=result.investment_metrics.annual_costs_by_year,
    discount_rate=0.05,
    devices=site.devices,  # sums the devices' investment blocks
)
print(f"NPV: €{metrics['npv']:,.0f}")
print(f"IRR: {metrics['irr'] * 100:.2f}%")
print(f"Payback: {metrics['payback_period_years']:.1f} years")
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

### 6.1 All-in-One Metrics (recommended)

`calculate_investment_metrics` assembles NPV, IRR, and payback from the
annual aggregates in the optimization result plus the devices' `investment`
blocks:

```python
from site_calc_investment.analysis import calculate_investment_metrics

metrics = calculate_investment_metrics(
    annual_revenues=result.investment_metrics.annual_revenue_by_year,
    annual_costs=result.investment_metrics.annual_costs_by_year,
    discount_rate=0.05,
    devices=site.devices,
)
# Returns dict with: npv, irr, payback_period_years,
#                    initial_investment, annual_net_cash_flows
```

It sums `capital_cost` into the initial investment and subtracts `annual_opex`
from each year's net cash flow.

**Do not double count:** `annual_costs_by_year` already includes
capacity-reservation charges (e.g. battery `power_sizing` payments or grid
tariff payments). Do not also model a cost carried by a sizing reservation as
`capital_cost` on the device.

### 6.2 NPV Calculation

```python
from site_calc_investment.analysis import calculate_npv

# Annual cash flows from optimization result
annual_cash_flows = result.investment_metrics.annual_revenue_by_year

# Calculate NPV with custom discount rate
npv = calculate_npv(
    cash_flows=annual_cash_flows,
    discount_rate=0.05,
    initial_investment=-1500000,  # €1.5M CAPEX
)
print(f"NPV: €{npv:,.0f}")
```

### 6.3 IRR Calculation

```python
from site_calc_investment.analysis import calculate_irr

# Full cash flow series (initial + annual)
cash_flows = [-1500000] + annual_cash_flows  # Prepend CAPEX

irr = calculate_irr(cash_flows)
print(f"IRR: {irr * 100:.2f}%")
```

### 6.4 Payback Period

```python
from site_calc_investment.analysis import calculate_payback_period

payback = calculate_payback_period(cash_flows)
print(f"Payback: {payback:.1f} years")
```

### 6.5 Annual Aggregation

```python
from site_calc_investment.analysis import aggregate_annual

# Extract annual revenue from hourly schedule
annual_revenues = aggregate_annual(
    hourly_values=result.sites["site1"].grid_flows["export"], prices=grid_export_prices, years=10
)
# Returns: [year1_revenue, year2_revenue, ..., year10_revenue]
```

---

## 7. Response Models

### 7.1 Investment Metrics

```python
{
    "investment_metrics": {
        "total_revenue_10y": 5175000.0,  # Total revenue over horizon (sum of annual_revenue_by_year)
        "total_costs_10y": 2950000.0,  # Total costs incl. capacity charges (sum of annual_costs_by_year)
        "npv": None,  # Calculated client-side
        "irr": None,  # Calculated client-side
        "payback_period_years": None,  # Calculated client-side
        "annual_revenue_by_year": [  # Year-by-year breakdown
            450000,
            465000,
            480000,
            495000,
            510000,
            525000,
            540000,
            555000,
            570000,
            585000,
        ],
        "annual_costs_by_year": [250000, 260000, 270000, 280000, 290000, 300000, 310000, 320000, 330000, 340000],
    }
}
```

`annual_costs_by_year` **includes capacity-reservation charges** (sizing
payments and grid capacity tariffs). NPV, IRR, and payback are computed
client-side from these arrays with `calculate_investment_metrics`
(Section 6.1), which also folds in the devices' `investment` blocks.

### 7.2 Device Schedule (87,600 intervals)

```python
{
    "Battery1": {
        "flows": {
            "electricity": [2.0, -1.5, 0.5, ...]  # 87,600 hourly values (MW)
        },
        "soc": [0.5, 0.48, 0.47, ...],  # 87,600 values (0-1)
        # No ancillary_reservations field
    },
    "CHP1": {
        "flows": {
            "gas": [-8.0, -4.0, -6.0, ...],  # 87,600 values (MW)
            "electricity": [3.0, 1.5, 2.25, ...],  # Continuous operation
            "heat": [4.0, 2.0, 3.0, ...],
        }
        # No binary_status (treated as continuous)
    },
}
```

### 7.3 Capacity Reservation Results

Devices with capacity reservations (a `capacity_reservation` property,
battery `power_sizing`/`capacity_sizing`, or a `cz_distribution_import`
device) carry a `capacity_reservations` list on their schedule:

```python
{
    "Grid": {
        "flows": {"electricity": [...]},
        "capacity_reservations": [
            {
                "kind": "capacity_reservation",  # or power_sizing | capacity_sizing
                "material": "electricity",
                "reserved": 4.2,  # contracted or optimizer-sized (MW; MWh for capacity_sizing)
                "total_payment": 391000.0,  # sum of all period payments (EUR)
                "periods": [
                    {
                        "start": "2026-01-01T00:00:00+01:00",
                        "end": "2026-02-01T00:00:00+01:00",
                        "peak": 3.9,  # measured peak in the period (MW)
                        "tariff": "T1",  # selected tariff (None for unpriced limits)
                        "payment": 32500.0,  # charge billed for this period (EUR)
                    },
                    ...,
                ],
            }
        ],
    }
}
```

For sizing reservations (`power_sizing`, `capacity_sizing`), `reserved` is
the optimizer's investment decision: the installed power (MW) or energy
capacity (MWh) it chose to build.

---

## 8. Error Handling

```python
from site_calc_investment.exceptions import ApiError, ValidationError, ForbiddenFeatureError, LimitExceededError

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
    Resolution,
    Site,
    Battery,
    ElectricityImport,
    ElectricityExport,
    InvestmentPlanningRequest,
    InvestmentParameters,
    OptimizationConfig,
)
from site_calc_investment.models.requests import TimeSpanInvestment
from site_calc_investment.analysis import calculate_investment_metrics

# Initialize client
client = InvestmentClient(base_url="https://api.site-calc.example.com", api_key="inv_9876543210fedcba")

# 10-year horizon
timespan = TimeSpanInvestment(
    start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")), intervals=87600, resolution=Resolution.HOUR_1
)

# Generate prices (2% annual escalation)
base_prices = [30.0 + 10 * abs(h - 12) / 12 for h in range(24)] * 365  # Daily pattern
prices_10y = []
for year in range(10):
    year_prices = [p * (1.02**year) for p in base_prices]
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
            "initial_soc": 0.5,
        },
        investment={
            "capital_cost": capacity * 100000,  # €100k/MWh
            "annual_opex": capacity * 1000,  # €1k/MWh/year
        },
    )

    site = Site(
        site_id=f"battery_{capacity}mwh",
        devices=[
            battery,
            ElectricityImport(name="GridImport", properties={"price": prices_10y, "max_import": 20.0}),
            ElectricityExport(name="GridExport", properties={"price": prices_10y, "max_export": 20.0}),
        ],
    )

    inv_params = InvestmentParameters(discount_rate=0.05, project_lifetime_years=10)

    request = InvestmentPlanningRequest(
        sites=[site],
        timespan=timespan,
        investment_parameters=inv_params,
        optimization_config=OptimizationConfig(objective="maximize_profit", time_limit_seconds=3600),
    )

    job = client.create_planning_job(request)
    result = client.wait_for_completion(job.job_id, poll_interval=30, timeout=7200)

    metrics = calculate_investment_metrics(
        annual_revenues=result.investment_metrics.annual_revenue_by_year,
        annual_costs=result.investment_metrics.annual_costs_by_year,
        discount_rate=0.05,
        devices=site.devices,
    )
    scenarios.append((f"{capacity} MWh", metrics))

# Compare scenarios
print("\n=== Battery Sizing Comparison ===")
for name, metrics in scenarios:
    print(
        f"{name}: NPV €{metrics['npv']:,.0f}, "
        f"IRR {metrics['irr'] * 100:.2f}%, "
        f"payback {metrics['payback_period_years']:.1f}y"
    )

# Find optimal size
best = max(scenarios, key=lambda s: s[1]["npv"])
print(f"\nOptimal size: {best[0]}")
```

Alternatively, let the optimizer size the battery itself in a single run:
give the battery a `power_sizing` / `capacity_sizing` reservation with the
investment cost as the tariff (Section 4.4) and read the sizing decision from
`capacity_reservations` in the result (Section 7.3). Costs carried by sizing
reservations are already part of `annual_costs_by_year` -- do not repeat them
in the `investment` block.

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

The solver time limit is capped at 3600 seconds (60 minutes) per job. Solve
time grows with horizon length, device count, and the number of capacity
reservations. Keeping `relax_binary_variables=True` (the default) is what
makes 10-year horizons tractable within the limit.

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

Because NPV is computed client-side, discount-rate sensitivity needs no
re-optimization -- run the job once and recompute:

```python
from site_calc_investment.analysis import calculate_investment_metrics

# Test NPV sensitivity to discount rate (single optimization run)
discount_rates = [0.03, 0.04, 0.05, 0.06, 0.07]
npvs = [
    calculate_investment_metrics(
        annual_revenues=result.investment_metrics.annual_revenue_by_year,
        annual_costs=result.investment_metrics.annual_costs_by_year,
        discount_rate=rate,
        devices=site.devices,
    )["npv"]
    for rate in discount_rates
]

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
| Solver time limit | 3600 seconds (60 minutes) |
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
- ✅ Financial analysis helpers (`calculate_investment_metrics` and friends)
- ✅ Per-device `investment` blocks for client-side CAPEX/OPEX accounting
- ✅ Capacity reservations: per-period capacity limits and charges with
  automatic cheapest-tariff assignment
- ✅ Battery `power_sizing` / `capacity_sizing` (optimizer-sized investment)
- ✅ Battery `degradation_yearly` (yearly capacity degradation curve)
- ✅ Czech distribution-tariff import device (`cz_distribution_import`)
- ✅ Net-metered import with overflow device (`electricity_import_with_overflow`) and `exclusive_with` pairing on exports
- ✅ Scenario comparison utilities
- ✅ Annual aggregation functions

### 14.3 Modified Behavior

- CHP `is_binary` ignored (always continuous)
- Higher solver time limit cap (3600 seconds maximum; the default remains 300 seconds)
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
