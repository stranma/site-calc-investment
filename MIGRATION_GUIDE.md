# Migration Guide

## Migrating from 1.2.x to 1.3.0

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
