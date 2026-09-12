# Migration Guide

## Timezone and calendar migration

Upgrade the service before the client. The service must advertise
`"features": ["planning_timezone"]` at `/health`; the new client refuses
submission if that capability is missing or unavailable. A matching API version
alone is insufficient. Status and old-result reads remain available. The health
check is cached per client instance, so recreate the client after an upgrade or
repair. Published client 1.5.4 and the previously deployed server do not implement
this contract; see the [timezone guide](docs/TIMEZONE_GUIDE.md).

Release pair: **investment server 1.5.3**, **site-calc-investment 1.5.5**, API 1.5.
Verify the capability on the deployed service before installing client 1.5.5;
retaining client 1.5.4 preserves access to the older service while rollout finishes.

### Choose the calendar explicitly when migrating

Previously a Prague-aware constructor sent offset endpoints, but the service
used a UTC planning calendar. The same constructor now also sends
`timespan.timezone="Europe/Prague"`. The start instant and requested interval
count are retained, but the corrected elapsed-time arithmetic can change the end
instant across DST. Month labels, monthly SOC anchors and inherited billing
boundaries also change. These corrections can change the optimization result.
The four-hour winter example below crosses no DST transition.

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from site_calc_investment.models import TimeSpanInvestment

start = datetime(2026, 1, 31, 23, tzinfo=ZoneInfo("Europe/Prague"))

# The same Python constructor previously produced a UTC planning calendar.
# Now these four hours use Prague months: one January hour, three February hours.
local = TimeSpanInvestment(start=start, intervals=4)
assert local.timezone == "Europe/Prague"

# Preserve the old UTC calendar AND the same physical interval instants.
# Convert the instant; do not relabel it with replace(tzinfo=...).
legacy_calendar = TimeSpanInvestment(start=start.astimezone(timezone.utc), intervals=4, timezone="UTC")
assert legacy_calendar.start == local.start.astimezone(timezone.utc)
# UTC months contain two January hours and two February hours here.
```

A parsed offset-only timestamp (including `Z`) needs an explicit IANA name.
Omission is inferred only from an aware Python `ZoneInfo.key`. Nonzero endpoint
offsets must match the selected zone, so convert Prague endpoints to UTC before
explicitly selecting the legacy UTC calendar as above. All horizons are
half-open `[start, end)` and all arrays remain in elapsed interval order.

The old client computed endpoints with local wall-clock addition. For an
unchanged `intervals=24` constructor at Prague local midnight:

| Start | Old serialized end / elapsed duration | Corrected end / elapsed duration |
| --- | --- | --- |
| 2026-03-29 | March 30 00:00 / 23 hours | March 30 01:00 / 24 hours |
| 2026-10-25 | October 26 00:00 / 25 hours | October 25 23:00 / 24 hours |

Choosing `timezone="UTC"` with the same interval count does not preserve those
old endpoints. If the intended model is the historical endpoint-to-endpoint
horizon, reconstruct from its recorded instants and reconcile every profile
with the actual elapsed interval count:

```python
old_start = datetime(2026, 3, 29, tzinfo=ZoneInfo("Europe/Prague"))
old_end = datetime(2026, 3, 30, tzinfo=ZoneInfo("Europe/Prague"))
same_endpoints = TimeSpanInvestment.model_validate(
    {
        "period_start": old_start.astimezone(timezone.utc),
        "period_end": old_end.astimezone(timezone.utc),
        "resolution": "1h",
        "timezone": "UTC",
    }
)
assert same_endpoints.intervals == 23
assert same_endpoints.end == old_end.astimezone(timezone.utc)
```

Use `timezone="Europe/Prague"` instead if retaining these same endpoint instants
with the local calendar is intended. Supply 23 hourly profile values for this
example; do not keep a formerly declared 24-value profile or silently drop a
value. `for_day` now returns the actual 23/25-hour civil day, so callers migrating
from its old fixed-day count must also rebuild matching profiles.

Calendar capacity reservations inherit the planning zone unless explicitly
overridden. With the new explicit planning zone, an override must produce the
same requested calendar-preset interval boundaries over the horizon; otherwise
admission rejects it. Equivalent Berlin/Prague partitions can be accepted;
conflicting UTC/Prague partitions cannot. Do not change a contractual tariff's
zone merely to bypass this check. Choose the intended unified calendar or retain
the older request contract until the model is deliberately revised. Older wire
requests omitting/nulling timezone retain legacy UTC with a warning, but the new
SDK always sends a name and cannot opt out. Explicit decomposition still fails
for unsupported cross-period models; `auto` may fall back without changing zones.

### Choose duration separately from the calendar

```python
fixed = TimeSpanInvestment.for_fixed_years(2025, 10, timezone="Europe/Prague")
civil = TimeSpanInvestment.for_calendar_years(2025, 10, timezone="Europe/Prague")
assert fixed.intervals == 87600
assert civil.intervals == 87648
```

Both calendars contain intervening February 29 instants. Fixed duration does not
add hours for leap days; civil years include their full January-to-January span.
Switching to `for_calendar_years` requires rebuilding every profile for the new
interval count and endpoints. Never pad, drop or duplicate DST hours to force
24-hour days: `for_day` has 23/24/25 hours where applicable. Repeated local hours
need an explicit fold/offset choice; nonexistent local inputs are rejected.

Year/day helpers default to Prague; year helpers default to hourly resolution.
Investment spans only permit hourly resolution. Generic `TimeSpan` also supports
15 minutes. Deprecated `for_years` preserves historical `years * 8760` interval
counts, including its old quarter-hour behavior; use `for_fixed_years` for proper
365-day durations at either resolution. MCP continues fixed durations in Prague.

Existing annual financial arrays and yearly degradation still use 8,760-hour
model years; the civil example above can yield an eleventh 48-hour annual bucket.
Financial helpers consume supplied arrays, not civil dates. MCP `monthly` output
is limited to twelve approximate 730-hour chunks. For civil reporting, use full
schedules and explicit calendar aggregation; the new horizon helper does not
change these conventions or introduce synthetic equal-length calendar months.

### Stored jobs and results

The service revalidates durable requests. Legacy UTC semantics are retained, but
formerly accepted naive endpoints or nonaligned horizons now fail validation.
Operators should drain the queue and inspect outstanding retries before rollout;
correct invalid inputs and associated profiles before resubmitting. Completed
old results remain readable and may have no `timespan` metadata.

New result metadata carries aware UTC endpoints, resolution, named timezone,
explicit/legacy source and an optional server-owned rules signature. A rules
change between processing attempts produces an explanatory failure; clients must
not fabricate signatures. Polling now preserves stored error messages and codes.

---

## Migrating from 1.2.x to 1.3.0

> **Server dependency:** the new capacity-reservation features and the
> reservation charges included in `annual_costs_by_year` require the
> optimization service at API version 1.3+. An older service silently
> ignores the new device properties (the same failure mode as the removed
> `max_import_unit_cost` field). Call `get_version()` after upgrading to
> confirm the service side.

Version 1.3.0 moves per-device investment costs onto the devices themselves,
introduces capacity reservations (per-billing-period capacity limits and
charges with automatic cheapest-tariff assignment), and removes
`InvestmentParameters` fields that the optimization service never applied.

### Field mapping

| 1.2.x | 1.3.0 |
|-------|-------|
| `InvestmentParameters(device_capital_costs={"X": c})` | Device `X`'s `investment={"capital_cost": c}` |
| `InvestmentParameters(device_annual_opex={"X": o})` | Device `X`'s `investment={"annual_opex": o}` |
| `max_import_unit_cost` on import properties | `capacity_reservation={"periods": "horizon", "tariffs": [{"name": "unit", "reserved_price": <old unit cost>, "peak_price": 0}]}` on `electricity_import` |
| `max_export_unit_cost` on export properties | Same as above, on `electricity_export` |
| `InvestmentParameters(investment_budget=...)` | Removed -- was never applied |
| `InvestmentParameters(carbon_price=...)` | Removed -- was never applied |
| `InvestmentParameters(price_escalation_rate=...)` | Removed -- was never applied; bake escalation into the price arrays instead |

Notes on the mapping:

- `max_import_unit_cost` / `max_export_unit_cost` were **never applied by the
  optimization service**, so removing them does not change optimization
  results. If you want the intended behavior (a priced ceiling on the peak
  grid flow), the `capacity_reservation` above now actually delivers it: with
  `periods="horizon"` and a single tariff whose `reserved_price` is the old
  unit cost, the optimizer sizes the reserved capacity and pays for it once
  over the horizon.
- `gas_import` and `heat_export` now have dedicated property classes with
  `price` and `max_import`/`max_export` only (no capacity reservations).

### Before / after

```python
# 1.2.x
inv_params = InvestmentParameters(
    discount_rate=0.05,
    project_lifetime_years=10,
    device_capital_costs={"Battery1": 500000},
    device_annual_opex={"Battery1": 5000},
)
battery = Battery(name="Battery1", properties={...})

# 1.3.0
inv_params = InvestmentParameters(
    discount_rate=0.05,
    project_lifetime_years=10,
)
battery = Battery(
    name="Battery1",
    properties={...},
    investment={"capital_cost": 500000, "annual_opex": 5000},
)
```

MCP users: `set_investment_params` now accepts only `scenario_id`,
`discount_rate`, and `project_lifetime_years`; pass the per-device costs as
the `investment` parameter of `add_device` instead.

### Stricter validation

Unknown fields now raise validation errors (`extra="forbid"`) on:

- `InvestmentParameters`
- `BatteryProperties`
- Market property classes (`electricity_import`/`electricity_export`,
  `gas_import`, `heat_export`, `cz_distribution_import`)
- `CapacityReservation` / `CapacityTariff` / `DeviceInvestment`

Previously misspelled or unsupported fields were silently ignored; the same
input now fails loudly. Fix the field name or remove the field.

### NPV workflow

Compute financial metrics with the new `calculate_investment_metrics` helper:

```python
from site_calc_investment.analysis import calculate_investment_metrics

metrics = calculate_investment_metrics(
    annual_revenues=result.investment_metrics.annual_revenue_by_year,
    annual_costs=result.investment_metrics.annual_costs_by_year,
    discount_rate=0.05,
    devices=site.devices,  # sums the devices' investment blocks
)
# metrics["npv"], metrics["irr"], metrics["payback_period_years"], ...
```

`annual_costs_by_year` now **includes capacity-reservation charges** (e.g.
battery `power_sizing` payments or grid capacity-tariff payments). Do not
also model a cost carried by a sizing reservation as `capital_cost` on the
device, or it will be counted twice.

---

## Moving to a New Repository

This guide explains how to copy the `client-investment` package to a new standalone Git repository.

### Prerequisites

- Git installed on your system
- GitHub account (or GitLab/Bitbucket)
- Access to create new repositories

### Step 1: Create New Repository on GitHub

1. Go to https://github.com/new (or your Git hosting service)
2. Repository settings:
   - **Name**: `site-calc-investment` (or `investment-client`)
   - **Description**: "Python client for Site-Calc investment planning API - long-term capacity planning and ROI analysis"
   - **Visibility**: Public (for open source)
   - **Initialize**: Do NOT add README, .gitignore, or license (we already have them)

3. Click "Create repository"

### Step 2: Prepare the Client-Investment Folder

The folder is already prepared with all necessary files:

#### ✅ Included Files

- `LICENSE` - MIT license
- `README.md` - Complete documentation
- `CHANGELOG.md` - Version history
- `CONTRIBUTING.md` - Contribution guidelines
- `pyproject.toml` - Package configuration
- `.gitignore` - Git ignore rules
- `.github/workflows/ci.yml` - GitHub Actions CI

#### ✅ Package Structure

```
client-investment/
├── site_calc_investment/       # Main package (ready)
├── tests/                      # Test suite (ready)
├── examples/                   # Usage examples (ready)
├── LICENSE                     # MIT license (ready)
├── README.md                   # Documentation (ready)
├── CHANGELOG.md                # Version history (ready)
├── CONTRIBUTING.md             # Contribution guide (ready)
├── pyproject.toml              # Package config (ready)
├── .gitignore                  # Git ignore (ready)
└── .github/                    # CI workflows (ready)
```

### Step 3: Initialize Git Repository

From the `client-investment` directory:

```bash
# Navigate to client-investment folder
cd client-investment

# Initialize git (if not already initialized)
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Site-Calc Investment Client v1.0.0

- Complete Pydantic V2 models for investment planning
- API client with retry logic
- Financial analysis (NPV, IRR, payback)
- Scenario comparison utilities
- 120 tests with 93% coverage
- Full documentation and examples"
```

### Step 4: Push to New Repository

```bash
# Add remote (replace URL with your actual repository URL)
git remote add origin https://github.com/YOUR-USERNAME/site-calc-investment.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

### Step 5: Configure Repository Settings

On GitHub, configure:

#### Branch Protection

- Go to Settings → Branches → Add rule for `main`
- ✅ Require pull request reviews before merging
- ✅ Require status checks to pass before merging
  - Select: `test`, `build`
- ✅ Require branches to be up to date before merging

#### Topics/Tags

Add topics for discoverability:
- `python`
- `energy`
- `optimization`
- `investment-analysis`
- `capacity-planning`
- `roi-analysis`

#### About Section

- **Description**: "Python client for Site-Calc investment planning API - long-term capacity planning and ROI analysis"
- **Website**: (Your documentation site if available)
- **Topics**: (As above)

#### Enable Features

- ✅ Issues
- ✅ Wiki (optional)
- ✅ Discussions (optional - good for community support)

### Step 6: Set Up PyPI Publishing (Optional)

To publish to PyPI:

1. **Create PyPI account**: https://pypi.org/account/register/

2. **Generate API token**: Account settings → API tokens → Add API token

3. **Add GitHub Secret**:
   - Go to repository Settings → Secrets → Actions
   - Add secret: `PYPI_API_TOKEN` = your PyPI token

4. **Create release workflow** (`.github/workflows/publish.yml`):
   ```yaml
   name: Publish to PyPI

   on:
     release:
       types: [published]

   jobs:
     publish:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.11'
         - run: pip install build twine
         - run: python -m build
         - run: twine upload dist/*
           env:
             TWINE_USERNAME: __token__
             TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
   ```

5. **Publish a release**:
   - Go to Releases → Create new release
   - Tag: `v1.0.0`
   - Title: `v1.0.0 - Initial Release`
   - Description: Copy from CHANGELOG.md
   - Publish release → Package auto-publishes to PyPI

### Step 7: Update URLs (After Publishing)

Once repository is live, update these files to replace example URLs:

#### In `pyproject.toml`:

```toml
[project.urls]
Homepage = "https://github.com/YOUR-USERNAME/site-calc-investment"
Documentation = "https://github.com/YOUR-USERNAME/site-calc-investment#readme"
Repository = "https://github.com/YOUR-USERNAME/site-calc-investment"
Issues = "https://github.com/YOUR-USERNAME/site-calc-investment/issues"
```

#### In `README.md`:

- Update documentation links
- Update repository links
- Update API base URL (if different from example)

#### In `CONTRIBUTING.md`:

- Update clone URL

### Step 8: Add Badges to README (Optional)

Add status badges at the top of README.md:

```markdown
# Site-Calc Investment Client

[![CI](https://github.com/YOUR-USERNAME/site-calc-investment/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR-USERNAME/site-calc-investment/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/site-calc-investment.svg)](https://badge.fury.io/py/site-calc-investment)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
```

### Verification Checklist

After migration, verify:

- [ ] Repository is accessible and public
- [ ] All files are present and correct
- [ ] CI workflow runs successfully
- [ ] Tests pass on all platforms (Linux, Windows, macOS)
- [ ] README displays correctly on GitHub
- [ ] LICENSE file is present
- [ ] Issues are enabled
- [ ] Branch protection is configured
- [ ] (Optional) Package published to PyPI
- [ ] (Optional) Documentation site deployed

### Maintaining Two Repositories

If keeping code in both the original `site-calc` repo and the new standalone repo:

#### Option 1: Manual Sync

- Make changes in `client-investment` folder in original repo
- Periodically copy to standalone repo
- Use git to commit and push

#### Option 2: Git Subtree

- Use `git subtree` to sync between repositories
- More complex but keeps history

#### Option 3: Monorepo + Separate Publish

- Keep development in original repo
- CI copies to separate repo on release
- Automated with GitHub Actions

### Support

If you encounter issues during migration:
1. Check GitHub's documentation: https://docs.github.com
2. Consult CONTRIBUTING.md for development setup
3. Open an issue in the new repository

---

**Ready to migrate?** Follow the steps above in order, and you'll have a clean, professional open-source repository ready for the community!
