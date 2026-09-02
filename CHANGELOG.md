# Changelog

All notable changes to the Site-Calc Investment Client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.1] - 2026-09-02

### Added

- `examples/04_import_with_overflow.py`: runnable walk-through of the
  net-metered connection -- the `electricity_import_with_overflow` device, the
  same pairing built by hand from a `cz_distribution_import` and an
  `electricity_export` with `exclusive_with`, the payload actually sent, and
  the arithmetic showing why an unpaired import + export overstates revenue.
- "How the pairing works" section in `docs/INVESTMENT_CLIENT_SPEC.md`.
- `ElectricityImportWithOverflow` and `ElectricityImportWithOverflowProperties`
  are exported from the package top level like the other device models.

### Changed

- `exclusive_with` on an `electricity_export` may target only an
  `electricity_import` or a `cz_distribution_import`. Pairing with an
  `electricity_import_with_overflow` device (which already carries its own
  export leg) is now rejected, relaxed or not; 1.5.0 accepted the relaxed
  case, which produced a second export on the same meter with no clear
  meaning.

## [1.5.0] - 2026-09-02

> The `electricity_import_with_overflow` device and the `exclusive_with`
> property require the optimization service at API version 1.5 or newer.
> Against an older service the pairing is silently ignored and the grid
> connection behaves like an independent import + export again -- call
> `get_version()` after upgrading to confirm compatibility.

### Added

- **New device type `electricity_import_with_overflow`**: a net-metered grid
  connection where consumption is billed at `import_price` and the surplus
  fed back to the grid is paid at `overflow_price`. The connection is either
  importing or exporting in any given hour, never both, so the result matches
  what the meter settles. Without this rule an overflow price above the
  import price lets the optimizer sell the site's generation and buy the
  site's load in the same hour, overstating revenue by
  `min(generation, load) * (overflow_price - import_price)` for every such
  hour and misjudging CHP and battery dispatch. Properties: `import_price`,
  `overflow_price` (both accept the scalar / array / file shorthand in the
  MCP tools), `max_import`, `max_overflow` (defaults to `max_import`),
  `no_simultaneous_flow` (default `True`; `False` relaxes the one-direction
  rule), and an optional `capacity_reservation` on the import side.
  Serialized to the API as an `electricity_import` named after the device
  plus an `electricity_export` named `<name>_overflow`, so results contain
  two device schedules for one sugar device.
- **`exclusive_with` on `electricity_export`**: pair a hand-built export with
  an `electricity_import` or `cz_distribution_import` in the same site by
  name to get the same one-direction behavior, e.g. a Czech
  distribution-tariff import with an overflow export. Validated client-side:
  the target must exist in the site, be an import, and be paired at most
  once; a device may not reuse a sugar device's derived `<name>_overflow`
  name.
- Paired devices must carry the real connection capacity in `max_import` /
  `max_overflow` / `max_export`: the service refuses a paired device without
  an explicit rating, and solve time depends on the ratings being realistic.

### Changed

- `device_to_wire` now returns a list of wire devices (one entry for every
  existing type, two for `electricity_import_with_overflow`).

## [1.4.0] - 2026-08-11

### Added

- `BatteryProperties.degradation_yearly`: yearly capacity degradation
  curve in percent, one entry per model year: `[5, 3, 2]` = 5% in
  year 1, 3% in year 2, 2% in year 3. The curve must include at least
  one entry for every model year in the horizon; shorter curves are
  rejected rather than extended by repeating or filling from the last
  entry. Longer curves are allowed and extras are ignored. The server expands it
  to a stepwise cap on usable stored energy: `prod(1 - d/100)` times
  the energy the battery actually has -- the fixed `reserved` energy
  when `capacity_sizing` is present, otherwise `capacity`. Each year's
  loss applies from the start of the year it occurs -- prepend `0` for
  an undegraded first year. `initial_soc` must not exceed the year-1
  factor (an omitted initial_soc adapts automatically). Not combinable
  with SOC anchor points or an optimizer-sized `capacity_sizing` (a
  fixed `reserved` capacity is fine). Requires site-calc-server >=
  1.4.0 with the degradation feature.
- `OptimizationConfig.mip_gap` (default 0.01): relative MIP optimality
  gap the solver may stop at (0 = prove full optimality, max 0.1). Also
  exposed as `mip_gap` on the MCP `submit_scenario` tool. Coordinated
  1.4.0 with site-calc-server (which now actually applies the gap) per
  the Minor Lock: 1.3.x servers accept the field but silently ignore
  it, and the client's MAJOR.MINOR health check surfaces exactly that
  mismatch.

## [1.3.1] - 2026-08-10

### Changed

- Maximum solver timeout raised from 900 seconds (15 minutes) to 3600
  seconds (60 minutes) for optimization requests; the default remains
  300 seconds. The MCP `submit_scenario` clamp and all documentation
  updated to match. Note: the server must allow the higher limit
  (`INVESTMENT_MAX_TIME_LIMIT`), otherwise requests above its cap are
  rejected with HTTP 400.

## [1.3.0] - 2026-08-04

> The capacity-reservation features (reservations, battery sizing,
> `cz_distribution_import`) and the reservation charges inside
> `annual_costs_by_year` require the optimization service at API version
> 1.3 or newer. Against an older service these device properties would be
> silently ignored -- call `get_version()` after upgrading to confirm
> compatibility.

### Added

- **Capacity reservations**: new `CapacityReservation` / `CapacityTariff`
  models putting a per-billing-period capacity limit and charge on a device
  flow. Billing periods: `calendar_month`, `calendar_year`, or `horizon`;
  each period is charged `fixed_price + reserved_price * R + peak_price * peak`,
  and with several tariffs on one reservation the cheapest tariff is assigned
  automatically per period. The reserved capacity `R` is either contracted
  (`reserved` set) or sized by the optimizer within
  `[min_reserved, max_reserved]`. IANA `timezone` controls calendar-period
  boundaries.
- **`capacity_reservation` on `electricity_import` / `electricity_export`**:
  model monthly grid capacity tariffs or other per-period capacity charges on
  the market connection.
- **Battery investment sizing**: `power_sizing` lets the optimizer size
  installed power (MW) up to `max_power`, priced by a tariff menu (use
  `periods='horizon'` for a one-shot investment cost in EUR/MW);
  `capacity_sizing` sizes energy capacity (MWh) up to `capacity`, priced by
  a tariff menu (EUR/MWh). An optimizer-sized capacity must start empty:
  `initial_soc` defaults to 0 for sizing runs and must not be set above 0
  (fix `reserved` to keep a non-zero initial SOC).
- **New device type `cz_distribution_import`**: electricity import billed
  under the Czech distribution capacity tariff (2027 tariff structure).
  Monthly billing with a T1/T2 price menu (`t1_reserved_price` /
  `t1_peak_price` / `t2_reserved_price` / `t2_peak_price`, EUR/MW/month);
  `reserved_capacity` is contracted or left `None` for the optimizer to size;
  `timezone` defaults to `Europe/Prague`. Serialized to the API as a plain
  `electricity_import` with the equivalent monthly capacity reservation.
- **Per-device investment costs**: every device accepts
  `investment={"capital_cost": EUR, "annual_opex": EUR/year}` for client-side
  NPV/IRR analysis. These values are stripped from the API payload and never
  influence the optimization.
- **Capacity reservation results**: `DeviceSchedule.capacity_reservations`
  lists each reservation's `kind` (`power_sizing` | `capacity_sizing` |
  `capacity_reservation`), watched `material`, contracted or optimizer-sized
  `reserved` value, `total_payment`, and a per-billing-period breakdown
  (`start`, `end`, `peak`, selected `tariff`, `payment`).
- **`calculate_investment_metrics` analysis helper**: assembles NPV, IRR,
  payback, initial investment, and annual net cash flows from the annual
  revenue/cost arrays, the discount rate, and the devices' `investment`
  blocks.
- MCP: `add_device` gained an `investment` parameter and supports
  `cz_distribution_import`; `get_job_result` includes a compact
  `capacity_reservations` summary block (sized capacity, total payment,
  tariffs used per device) with the raw per-period breakdown at
  `detail_level='full'`; `get_device_schema` documents the new fields and
  device type. Tool count stays 17.

### Changed

- **BREAKING**: `InvestmentParameters` now has only `discount_rate` and
  `project_lifetime_years`; unknown fields raise validation errors
  (`extra='forbid'`).
- **BREAKING**: battery and market property classes reject unknown fields;
  `gas_import` and `heat_export` now have dedicated property classes (price
  and max flow only).
- `annual_costs_by_year` in the results now includes capacity-reservation
  charges (sizing payments and grid capacity tariffs).
- MCP: `set_investment_params` parameters are now `scenario_id`,
  `discount_rate`, `project_lifetime_years` only.

### Removed

- **BREAKING**: `InvestmentParameters` fields `device_capital_costs` and
  `device_annual_opex` (moved to per-device `investment` blocks) and
  `investment_budget`, `carbon_price`, `price_escalation_rate` (these were
  never applied by the optimization service).
- **BREAKING**: `max_import_unit_cost` / `max_export_unit_cost` on market
  import/export properties (never applied by the optimization service; use a
  `capacity_reservation` with a whole-horizon tariff for a priced peak-flow
  ceiling).

### Migration

See `MIGRATION_GUIDE.md` ("Migrating from 1.2.x to 1.3.0") for the full
field-by-field mapping. In short: move per-device CAPEX/OPEX from
`InvestmentParameters` to each device's `investment` block, replace unit-cost
fields with capacity reservations, and compute NPV/IRR with
`calculate_investment_metrics` (without re-adding costs that a sizing
reservation already charges).

---

## [1.2.9] - 2026-07-09

### Added

- **Profile-based device types** (6 new): `fixed_production` and `fixed_consumption`
  (produce/consume exactly a `power_profile` in MW), `max_power_production`
  (steerable in `[0, max_power_profile]` at a linear `cost_per_mwh`) and
  `max_power_consumption` (steerable, each MWh consumed worth `value_per_mwh`),
  plus `photovoltaic_nonsteerable` / `photovoltaic_steerable` -- PV-named variants
  of the two production devices. Steerable PV is curtailed automatically when
  producing is unprofitable (e.g. negative prices).
- MCP: `add_device` and `get_device_schema` support all six new types; profile
  properties accept the usual shorthands (scalar, `{"file": ...}`, raw list).

### Removed

- **`Photovoltaic` device** (`photovoltaic` type) with `location`/`tilt`/`azimuth`/
  `peak_power_mw`: replaced by the two explicit PV variants above. Users now supply
  the power profile directly (e.g. from a weather service or measured data) instead
  of site geometry.

### Changed

- Requires a server release that accepts the new device types; older servers
  reject them during validation.

---

## [1.2.8] - 2026-02-06

### Removed
- **`visualize_results` MCP tool**: Removed HTML dashboard visualization tool
  and `generate_dashboard` public API. The visualization module had minimal adoption
  and added complexity. Dashboard generation may return as a standalone package.
- **`site_calc_investment.visualization` module**: Entire visualization subpackage removed.

### Fixed
- **CSV metadata row count**: `_get_csv_metadata` now correctly counts rows in
  headerless CSV files (off-by-one fix).

### Changed
- MCP tool count: 18 -> 17

---

## [1.2.7] - 2026-02-05

### Added
- **`fetch_url` MCP tool**: New tool (#18) that downloads a URL (e.g., CSV price data
  from the web), saves it locally, and returns CSV metadata (row count, column names,
  numeric columns). Enables workflows where the LLM fetches market data directly
  instead of requiring manual file preparation or inline array generation.
- **`intervals` parameter on `set_timespan`**: Optional parameter (1-100,000) that
  overrides `years * 8760` calculation. Allows using partial-year data (e.g., a CSV
  with 864 rows for ~36 days of hourly data).

### Changed
- MCP tool count: 17 -> 18

---


## [1.2.6] - 2026-02-05

### Added
- **`visualize_results` MCP tool**: New tool (#17) that generates an interactive HTML dashboard
  from completed optimization results. Opens in browser with three tabs:
  - **Financial Analysis**: KPI cards (NPV, IRR, payback, profit), annual revenue vs costs
    bar chart, cumulative cash flow curve with payback marker
  - **Energy Balance**: Stacked bar chart of generation/consumption with smart time aggregation
    (hourly/daily/weekly/monthly), energy summary KPIs
  - **Device Detail**: Interactive dispatch and SOC charts with hour-range drill-down controls
- **`generate_dashboard` public API**: New function exported from `site_calc_investment` for
  programmatic dashboard generation without MCP
- **Visualization module** (`site_calc_investment.visualization`): Self-contained module with
  zero new dependencies (uses Plotly.js via CDN, stdlib only)

### Changed
- MCP tool count: 16 -> 17

### Security
- Dashboard JSON embedding uses HTML-safe escaping to prevent XSS via `</script>` injection
- Output filenames sanitize `job_id` to prevent path traversal attacks

---

## [1.2.5] - 2026-02-05

### Fixed
- **Windows timezone support**: Moved `tzdata` from dev-only to runtime dependency. Fixes
  `submit_scenario` failing with "No time zone found with key Europe/Prague" when installed
  via `uvx --from site-calc-investment[mcp]` on Windows (no system timezone database).

---


## [1.2.4] - 2026-02-04

### Added
- **`get_version` MCP tool**: New tool (#16) that returns the installed client version and, if
  the server is reachable, the server API version with compatibility check.

### Changed
- MCP tool count: 15 -> 16

---


## [1.2.3] - 2026-02-04

### Added
- **`save_data_file` MCP tool**: New tool (#15) that writes generated data (price arrays, demand
  profiles) to CSV files on the local filesystem. Solves the problem where the LLM cannot write
  files directly but the MCP server can.
  - Supports named columns with automatic `.csv` extension
  - Relative paths resolve against `INVESTMENT_DATA_DIR` environment variable
  - Returned file path can be used directly in `add_device` via `{"file": "...", "column": "..."}`
- **`INVESTMENT_DATA_DIR` environment variable**: Optional config for `save_data_file` base directory
- **MCP Server specification**: Full docs at `docs/MCP_SERVER_SPEC.md`

### Changed
- MCP server instructions updated to inform the LLM about `save_data_file` capability
- MCP tool count: 14 -> 15

---


## [1.2.2] - 2026-02-04

### Added
- **MCP Server**: FastMCP-based MCP server exposing 14 tools for LLM-driven investment planning
  - Stateful builder pattern: create scenario -> add devices -> set timespan -> review -> submit -> get results
  - All 10 device types supported with data shorthand (scalar expansion, CSV/JSON file loading)
  - 3 result detail levels: summary, monthly, full
  - Install via `pip install site-calc-investment[mcp]`
  - CLI entry point: `site-calc-investment-mcp`
- **`get_device_schema` tool**: Returns property schemas for each device type with types, units, and examples

### Changed
- Package now has `[mcp]` optional dependency group (`fastmcp>=2.0`)

---

## [1.2.1] - 2026-02-03

### Fixed
- **README Quick Start**: Fixed example code to use correct model classes and valid parameter values
  - Use `TimeSpanInvestment` instead of `TimeSpan`
  - Use valid `objective` values (`maximize_profit`, `minimize_cost`, `maximize_self_consumption`)
  - Add required `project_lifetime_years` to `InvestmentParameters`
  - Fix `time_limit_seconds` max value (900, not 3600)
- **Capabilities table**: Corrected timeout from "3600 seconds" to "900 seconds (15 minutes) max"
- **QUICK_START.md**: Added `pypi` environment name for Trusted Publishing setup

---

## [1.2.0] - 2026-02-03

### Changed
- **Repository URLs**: Updated package metadata to point to official GitHub repository
- **CI/CD**: Added automatic PyPI publishing workflow on release tags

### Fixed
- Minor documentation improvements and URL corrections

---

## [1.1.0] - 2026-02-01

### Added
- **SOC Anchoring**: New optional fields `soc_anchor_interval_hours` and `soc_anchor_target`
  in `BatteryProperties` for improved long-term battery optimization
- **Version Validation**: Client automatically checks server version compatibility and warns
  if MAJOR.MINOR versions don't match
- **Timeout Control**: Jobs can now specify custom timeout limits

### Changed
- **Default Solver**: Changed from CBC to HiGHS for 30-40% faster optimization times
- Results are identical; no code changes required

### Notes
- All v1.0.x client code continues to work without modification
- SOC anchoring is opt-in via new optional fields
- Version warnings are informational only and don't affect functionality

---

## [1.0.0] - 2024-12-15

### Added
- Initial release of Site-Calc Investment Client
- Complete Pydantic V2 models for investment planning requests and responses
- 10 device types: Battery, CHP, HeatAccumulator, Photovoltaic, ElectricityDemand, HeatDemand, ElectricityImport, ElectricityExport, GasImport, HeatExport
- API client with automatic retry logic and exponential backoff
- Financial analysis functions: NPV, IRR (Newton-Raphson), payback period
- Scenario comparison utilities for evaluating multiple investment options
- Support for 10-year hourly optimization (up to 100,000 intervals)
- Comprehensive test suite with 120 tests and 93% coverage
- Three complete examples demonstrating capacity planning, scenario comparison, and financial analysis

### Features
- **Investment-Specific**: Designed exclusively for long-term capacity planning and ROI analysis
- **No Ancillary Services**: Investment client does not support ANS optimization (reserved for operational client)
- **1-Hour Resolution Only**: Optimized for multi-year planning horizons
- **Automatic Binary Relaxation**: CHP binary constraints automatically relaxed for tractability
- **Financial Metrics**: Built-in NPV, IRR, and payback period calculations
- **Type-Safe**: Full type hints with Pydantic V2 validation
- **Well-Tested**: 120 tests covering all major functionality with mocked HTTP responses

### Notes
- Requires API key with `inv_` prefix
- Maximum 100,000 intervals (~11 years at 1-hour resolution)
- Default timeout: 3600 seconds (1 hour)
- Python 3.10+ required
