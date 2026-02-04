# MCP Server Specification

**Package:** `site-calc-investment[mcp]`
**Server name:** `site-calc-investment`
**Protocol:** MCP (Model Context Protocol) via FastMCP
**Tools:** 15

---

## 1. Overview

The MCP server exposes the Site-Calc investment planning API as tools that LLMs (e.g., Claude Desktop) can call interactively. Users describe what they want to optimize in natural language, and the LLM assembles scenarios, submits jobs, and retrieves results through these tools.

### 1.1 Architecture

```
Claude Desktop (LLM)
    |
    | MCP protocol (stdio)
    v
site-calc-investment-mcp (local process)
    |
    | HTTPS / REST
    v
Site-Calc API (remote server)
```

The MCP server runs **locally** on the user's machine. It has full filesystem access (for CSV data files) and network access (for the optimization API).

### 1.2 Key Capabilities

| Feature | Value |
|---------|-------|
| Tools | 15 |
| Device types | 10 |
| Max horizon | 100,000 intervals (~11 years) |
| Resolution | 1-hour |
| Local filesystem | Read + Write (CSV data files) |
| API connection | HTTPS to Site-Calc server |

---

## 2. Configuration

### 2.1 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `INVESTMENT_API_URL` | Yes | Site-Calc API base URL |
| `INVESTMENT_API_KEY` | Yes | API key (starts with `inv_`) |
| `INVESTMENT_DATA_DIR` | No | Default directory for `save_data_file` relative paths |

`INVESTMENT_API_URL` and `INVESTMENT_API_KEY` are required for job submission tools (`submit_scenario`, `get_job_status`, `get_job_result`, `cancel_job`). Scenario assembly tools work without them.

`INVESTMENT_DATA_DIR` sets the base directory for resolving relative paths in `save_data_file`. If not set, relative paths resolve against the current working directory.

### 2.2 Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "site-calc-investment": {
      "command": "uvx",
      "args": ["--from", "site-calc-investment[mcp]", "site-calc-investment-mcp"],
      "env": {
        "INVESTMENT_API_URL": "https://api.site-calc.example.com",
        "INVESTMENT_API_KEY": "inv_your_api_key_here",
        "INVESTMENT_DATA_DIR": "C:\\my_source\\BESS_Optimization_Tool"
      }
    }
  }
}
```

#### Development (local checkout)

When working against a local checkout of the client package, use `uv run --directory` instead:

```json
{
  "mcpServers": {
    "site-calc-investment": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "C:\\my_source\\site-calc\\client-investment",
        "site-calc-investment-mcp"
      ],
      "env": {
        "INVESTMENT_API_URL": "https://api.site-calc.example.com",
        "INVESTMENT_API_KEY": "inv_your_api_key_here",
        "INVESTMENT_DATA_DIR": "C:\\my_source\\BESS_Optimization_Tool"
      }
    }
  }
}
```

### 2.3 Installation

```bash
pip install site-calc-investment[mcp]
```

Or with uv (recommended for development):

```bash
cd client-investment
uv sync --group dev
```

---

## 3. Tool Reference

### 3.1 Scenario Assembly Tools

#### `create_scenario`

Create a new draft optimization scenario.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Human-readable name |
| `description` | string | No | Longer description |

**Returns:** `{"scenario_id": "sc_...", "name": "..."}`

---

#### `add_device`

Add a device to a draft scenario.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scenario_id` | string | Yes | Target scenario |
| `device_type` | string | Yes | One of 10 device types (see Section 4) |
| `name` | string | Yes | Unique device name within scenario |
| `properties` | object | Yes | Device-specific properties |
| `schedule` | object | No | Runtime constraints |

Properties support data shorthand:
- A number (e.g., `50.0`) -- expanded to constant array matching the timespan
- A list (e.g., `[30, 40, 80, 50]`) -- used directly
- A file reference (e.g., `{"file": "prices.csv", "column": "price_eur"}`) -- loaded from local CSV

**Returns:** Summary string.

---

#### `set_timespan`

Set the optimization time horizon.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scenario_id` | string | Yes | | Target scenario |
| `start_year` | int | Yes | | Start year (e.g., 2025) |
| `years` | int | No | 1 | Number of years |

One year = 8,760 intervals. Maximum ~11 years (100,000 intervals).

**Returns:** Confirmation string with interval count.

---

#### `set_investment_params`

Set financial parameters for ROI calculation (NPV, IRR, payback).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scenario_id` | string | Yes | | Target scenario |
| `discount_rate` | float | No | 0.05 | Annual discount rate (0-0.5) |
| `project_lifetime_years` | int | No | timespan years | Project lifetime |
| `device_capital_costs` | object | No | | CAPEX by device name (EUR) |
| `device_annual_opex` | object | No | | Annual O&M by device name (EUR) |

**Returns:** Confirmation string.

---

#### `review_scenario`

Show a summary of the draft scenario before submitting.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scenario_id` | string | Yes | Scenario to review |

**Returns:** Dict with `name`, `devices`, `timespan`, `investment_params`, `validation`.

---

#### `remove_device`

Remove a device from a draft scenario.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scenario_id` | string | Yes | Target scenario |
| `device_name` | string | Yes | Device to remove |

**Returns:** Confirmation string.

---

#### `delete_scenario`

Delete a draft scenario entirely.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scenario_id` | string | Yes | Scenario to delete |

**Returns:** Confirmation string.

---

#### `list_scenarios`

List all active draft scenarios.

**Returns:** List of `{"id", "name", "device_count", "has_timespan", "job_count"}`.

---

### 3.2 Job Submission and Management Tools

#### `submit_scenario`

Submit a draft scenario for server-side optimization.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scenario_id` | string | Yes | | Scenario to submit |
| `objective` | string | No | `maximize_profit` | Optimization objective |
| `solver_timeout` | int | No | 300 | Time limit in seconds (max 900) |

Objectives: `maximize_profit`, `minimize_cost`, `maximize_self_consumption`.

**Returns:** `{"job_id": "...", "status": "pending"}`

---

#### `get_job_status`

Check job status and progress.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | Job identifier |

**Returns:** Dict with `job_id`, `status`, and optionally `progress`, `message`, `estimated_completion_seconds`, `solver_time_seconds`, `error`.

---

#### `get_job_result`

Retrieve completed optimization results.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `job_id` | string | Yes | | Job identifier |
| `detail_level` | string | No | `summary` | `summary`, `monthly`, or `full` |

Detail levels:
- **summary** -- Aggregated totals (profit, cost, solve time, investment metrics). Compact.
- **monthly** -- Summary + per-device monthly breakdowns.
- **full** -- All data including hourly schedules. Can be very large.

**Returns:** Result dict at requested detail level.

---

#### `cancel_job`

Cancel a pending or running job.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | Job to cancel |

**Returns:** `{"job_id": "...", "status": "cancelled"}`

---

#### `list_jobs`

List all scenarios and their associated jobs.

**Returns:** List of `{"scenario_id", "scenario_name", "job_ids", "job_count"}`.

---

### 3.3 Data File Tools

#### `save_data_file`

Save generated data to a CSV file on the local filesystem.

This tool exists because the LLM cannot write files directly, but this MCP server runs locally and can. Use it to persist generated data arrays (prices, demand profiles, etc.) so they can be referenced in `add_device` via `{"file": "<path>", "column": "<name>"}`.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | string | Yes | | Filename or path (e.g., `"prices_2025.csv"`) |
| `columns` | object | Yes | | Named columns: `{"col_name": [float, ...]}` |
| `overwrite` | bool | No | false | Allow overwriting existing files |

Path resolution:
- Absolute paths are used as-is
- Relative paths resolve against `INVESTMENT_DATA_DIR` (or cwd if not set)
- `.csv` extension is appended if missing
- Non-`.csv` extensions are rejected

**Returns:**
```json
{
  "file_path": "C:\\Users\\Admin\\data\\prices.csv",
  "columns": ["hour", "price_eur_mwh"],
  "rows": 8760,
  "message": "Saved 8760 rows to C:\\Users\\Admin\\data\\prices.csv"
}
```

**Typical workflow:**
```
1. LLM generates price array (8760 values)
2. LLM calls save_data_file(file_path="prices_2025.csv", columns={"price_eur": [...]})
3. LLM calls add_device(properties={"price": {"file": "C:/.../prices_2025.csv", "column": "price_eur"}, ...})
```

---

### 3.4 Helper Tools

#### `get_device_schema`

Get the properties schema for a device type.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_type` | string | Yes | Device type name |

**Returns:** Schema dict with `properties`, `supports_schedule`, `example`.

---

## 4. Supported Device Types

| Device Type | Description | Key Properties |
|-------------|-------------|----------------|
| `battery` | Battery energy storage | capacity, max_power, efficiency |
| `chp` | Combined heat and power | gas_input, el_output, heat_output |
| `heat_accumulator` | Thermal storage | capacity, max_power, efficiency |
| `photovoltaic` | Solar PV | peak_power_mw, location, tilt, azimuth |
| `electricity_import` | Buy from grid | price, max_import |
| `electricity_export` | Sell to grid | price, max_export |
| `gas_import` | Gas supply | price, max_import |
| `heat_export` | Sell heat | price, max_export |
| `electricity_demand` | Electricity load | max_demand_profile |
| `heat_demand` | Heat load | max_demand_profile |

Use `get_device_schema(device_type)` for full property documentation.

---

## 5. End-to-End Example

A typical session for battery arbitrage analysis:

```
User: "Evaluate a 10 MWh battery with 2025 German electricity prices"

LLM actions:
1. Generate 8760 hourly prices for 2025
2. save_data_file(file_path="de_prices_2025.csv",
     columns={"hour": [0..8759], "price_eur_mwh": [32.1, 28.5, ...]})
3. create_scenario(name="10 MWh Battery - DE 2025")
4. set_timespan(scenario_id=sid, start_year=2025)
5. add_device(scenario_id=sid, device_type="battery", name="BESS",
     properties={"capacity": 10.0, "max_power": 5.0, "efficiency": 0.90})
6. add_device(scenario_id=sid, device_type="electricity_import", name="GridBuy",
     properties={"price": {"file": ".../de_prices_2025.csv", "column": "price_eur_mwh"},
                 "max_import": 5.0})
7. add_device(scenario_id=sid, device_type="electricity_export", name="GridSell",
     properties={"price": {"file": ".../de_prices_2025.csv", "column": "price_eur_mwh"},
                 "max_export": 5.0})
8. set_investment_params(scenario_id=sid, discount_rate=0.05,
     device_capital_costs={"BESS": 500000})
9. review_scenario(scenario_id=sid)
10. submit_scenario(scenario_id=sid)
11. get_job_status(job_id=jid)  -- poll until complete
12. get_job_result(job_id=jid, detail_level="summary")
```

LLM then presents the results: profit, NPV, IRR, payback period.

---

## 6. Error Handling

Tools raise standard Python exceptions that FastMCP translates to MCP error responses:

| Exception | Cause |
|-----------|-------|
| `ValueError` | Invalid parameters (wrong device type, missing properties, bad column data) |
| `FileNotFoundError` | Referenced CSV/JSON file does not exist |
| `FileExistsError` | `save_data_file` with `overwrite=False` on existing file |
| `KeyError` | Nonexistent scenario_id or device_name |

The LLM receives error messages and can retry with corrected parameters.

---

## 7. Testing

```bash
# Run MCP server tests
cd client-investment && uv run pytest tests/test_mcp/ -v

# Run full test suite
cd client-investment && uv run pytest tests/ -v
```

Test coverage includes:
- 11 tests for `save_csv` data layer
- 2 tests for `save_data_file` tool integration
- 7 MCP protocol integration tests (via FastMCP Client)
- 77+ tests for scenario assembly and job management tools
