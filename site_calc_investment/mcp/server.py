"""FastMCP server with all tool definitions for investment planning."""

from typing import Any, Literal, Optional, cast

from fastmcp import FastMCP

from site_calc_investment import __version__
from site_calc_investment.api.client import InvestmentClient
from site_calc_investment.mcp.config import Config, get_data_dir
from site_calc_investment.mcp.data_loaders import save_csv
from site_calc_investment.mcp.scenario import ScenarioStore

mcp = FastMCP(
    "site-calc-investment",
    instructions=(
        "Investment planning optimization tools for energy systems. "
        "Build scenarios with batteries, CHP, PV, and market connections, "
        "then submit for optimization to find optimal dispatch and ROI.\n\n"
        "IMPORTANT: Use save_data_file to write generated data (price arrays, "
        "demand profiles) to the local filesystem BEFORE referencing them in "
        "add_device. This MCP server runs locally and has filesystem access -- "
        "you do not need to ask the user to save files manually."
    ),
)

_store = ScenarioStore()
_client: Optional[InvestmentClient] = None


def _get_client() -> InvestmentClient:
    """Get or create the InvestmentClient singleton."""
    global _client
    if _client is None:
        config = Config.from_env()
        _client = InvestmentClient(base_url=config.api_url, api_key=config.api_key)
    return _client


# --- Scenario Assembly Tools ---


def create_scenario(name: str, description: str = "") -> dict[str, str]:
    """Create a new draft optimization scenario.

    Start here. After creating a scenario, add devices, set the timespan,
    and optionally set investment parameters before submitting.

    :param name: Human-readable scenario name (e.g., "Battery 10MWh evaluation").
    :param description: Optional longer description.
    :returns: Dict with scenario_id and name.
    """
    scenario_id = _store.create(name=name, description=description)
    return {"scenario_id": scenario_id, "name": name}


def add_device(
    scenario_id: str,
    device_type: str,
    name: str,
    properties: dict[str, Any],
    schedule: Optional[dict[str, Any]] = None,
) -> str:
    """Add a device to a draft scenario.

    Device types: battery, chp, photovoltaic, heat_accumulator,
    electricity_import, electricity_export, gas_import, heat_export,
    electricity_demand, heat_demand.

    Properties support data shorthand for large arrays:
    - A number (e.g., 50.0) is expanded to a flat array matching the timespan
    - A dict {"file": "C:/data/prices.csv"} loads from a local CSV file
    - A dict {"file": "path.csv", "column": "price_eur"} loads a specific column
    - A raw list [30, 40, 80, 50] for short horizons

    Use get_device_schema(device_type) to see required properties.

    :param scenario_id: Scenario to add device to.
    :param device_type: One of the supported device types (lowercase).
    :param name: Unique device name within the scenario.
    :param properties: Device-specific properties dict.
    :param schedule: Optional runtime constraints (can_run, must_run, etc.).
    :returns: Summary string of the added device.
    """
    return _store.add_device(
        scenario_id=scenario_id,
        device_type=device_type,
        name=name,
        properties=properties,
        schedule=schedule,
    )


def set_timespan(scenario_id: str, start_year: int, years: int = 1) -> str:
    """Set the optimization time horizon.

    Investment planning uses 1-hour resolution. One year = 8760 intervals.
    Maximum ~11 years (100,000 intervals).

    :param scenario_id: Target scenario.
    :param start_year: Start year (e.g., 2025).
    :param years: Number of years (default: 1).
    :returns: Confirmation with interval count.
    """
    return _store.set_timespan(scenario_id=scenario_id, start_year=start_year, years=years)


def set_investment_params(
    scenario_id: str,
    discount_rate: float = 0.05,
    project_lifetime_years: Optional[int] = None,
    device_capital_costs: Optional[dict[str, float]] = None,
    device_annual_opex: Optional[dict[str, float]] = None,
) -> str:
    """Set financial parameters for ROI calculation (NPV, IRR, payback).

    Optional -- if not set, only raw profit numbers are returned.

    :param scenario_id: Target scenario.
    :param discount_rate: Annual discount rate (0-0.5, e.g., 0.05 = 5%).
    :param project_lifetime_years: Project lifetime in years (defaults to timespan years).
    :param device_capital_costs: CAPEX by device name in EUR (e.g., {"Battery1": 500000}).
    :param device_annual_opex: Annual O&M cost by device name in EUR.
    :returns: Confirmation string.
    """
    return _store.set_investment_params(
        scenario_id=scenario_id,
        discount_rate=discount_rate,
        project_lifetime_years=project_lifetime_years,
        device_capital_costs=device_capital_costs,
        device_annual_opex=device_annual_opex,
    )


def review_scenario(scenario_id: str) -> dict[str, Any]:
    """Show a summary of the current draft scenario before submitting.

    Returns devices, timespan, investment parameters, and validation status.
    Check validation before submitting -- it must say "Valid" to proceed.

    :param scenario_id: Scenario to review.
    :returns: Full summary dict.
    """
    return _store.review(scenario_id=scenario_id)


def remove_device(scenario_id: str, device_name: str) -> str:
    """Remove a device from a draft scenario.

    :param scenario_id: Target scenario.
    :param device_name: Name of the device to remove.
    :returns: Confirmation string.
    """
    _store.remove_device(scenario_id=scenario_id, device_name=device_name)
    return f"Removed device '{device_name}' from scenario."


def delete_scenario(scenario_id: str) -> str:
    """Delete a draft scenario entirely.

    :param scenario_id: Scenario to delete.
    :returns: Confirmation string.
    """
    _store.delete(scenario_id=scenario_id)
    return f"Deleted scenario '{scenario_id}'."


def list_scenarios() -> list[dict[str, Any]]:
    """List all active draft scenarios.

    :returns: List of scenario summaries with id, name, device_count, status.
    """
    scenarios = _store.list()
    return [
        {
            "id": s.id,
            "name": s.name,
            "device_count": s.device_count,
            "has_timespan": s.has_timespan,
            "job_count": s.job_count,
        }
        for s in scenarios
    ]


# --- Job Submission & Management ---


def submit_scenario(
    scenario_id: str,
    objective: str = "maximize_profit",
    solver_timeout: int = 300,
) -> dict[str, str]:
    """Submit a draft scenario for optimization.

    The scenario is preserved after submission -- you can modify devices
    and resubmit for "what-if" analysis.

    Objectives: maximize_profit, minimize_cost, maximize_self_consumption.

    :param scenario_id: Scenario to submit.
    :param objective: Optimization objective (default: maximize_profit).
    :param solver_timeout: Solver time limit in seconds (max 900).
    :returns: Dict with job_id and initial status.
    """
    objective_literal = cast(
        Literal["maximize_profit", "minimize_cost", "maximize_self_consumption"],
        objective,
    )
    request = _store.build_request(
        scenario_id=scenario_id,
        objective=objective_literal,
        solver_timeout=solver_timeout,
    )
    client = _get_client()
    job = client.create_planning_job(request)
    _store.record_job(scenario_id, job.job_id)
    return {"job_id": job.job_id, "status": job.status}


def get_job_status(job_id: str) -> dict[str, Any]:
    """Check job status and progress.

    :param job_id: Job identifier from submit_scenario.
    :returns: Status dict with status, progress, message, timing info.
    """
    client = _get_client()
    job = client.get_job_status(job_id)
    result: dict[str, Any] = {
        "job_id": job.job_id,
        "status": job.status,
    }
    if job.progress is not None:
        result["progress"] = job.progress
    if job.message:
        result["message"] = job.message
    if job.estimated_completion_seconds is not None:
        result["estimated_completion_seconds"] = job.estimated_completion_seconds
    if job.solver_time is not None:
        result["solver_time_seconds"] = job.solver_time
    if job.error:
        result["error"] = job.error
    return result


def get_job_result(job_id: str, detail_level: str = "summary") -> dict[str, Any]:
    """Retrieve completed optimization results.

    Detail levels:
    - "summary": Aggregated totals (profit, solve time, per-device revenue/cost, investment metrics).
      Best for LLM context -- compact and informative.
    - "monthly": Summary + monthly breakdown per device.
    - "full": All data including hourly schedules. WARNING: can be very large (87K+ values).

    :param job_id: Job identifier.
    :param detail_level: One of "summary", "monthly", "full" (default: "summary").
    :returns: Result dict at requested detail level.
    """
    allowed_levels = {"summary", "monthly", "full"}
    if detail_level not in allowed_levels:
        raise ValueError(f"Invalid detail_level '{detail_level}'. Must be one of: {', '.join(sorted(allowed_levels))}")
    client = _get_client()
    response = client.get_job_result(job_id)

    result: dict[str, Any] = {
        "job_id": response.job_id,
        "status": response.status,
        "summary": {
            "expected_profit": response.summary.expected_profit,
            "total_da_revenue": response.summary.total_da_revenue,
            "total_cost": response.summary.total_cost,
            "solver_status": response.summary.solver_status,
            "solve_time_seconds": response.summary.solve_time_seconds,
        },
    }

    if response.investment_metrics:
        metrics = response.investment_metrics
        result["investment_metrics"] = {
            "npv": metrics.npv,
            "irr": metrics.irr,
            "payback_period_years": metrics.payback_period_years,
            "total_revenue": metrics.total_revenue_10y,
            "total_costs": metrics.total_costs_10y,
        }

    if detail_level in ("monthly", "full"):
        result["device_summaries"] = _build_device_summaries(response, detail_level)

    if detail_level == "full":
        sites_data: dict[str, Any] = {}
        for site_id, site_result in response.sites.items():
            site_devices: dict[str, Any] = {}
            for dev_name, schedule in site_result.device_schedules.items():
                dev_data: dict[str, Any] = {"flows": schedule.flows}
                if schedule.soc is not None:
                    dev_data["soc"] = schedule.soc
                if schedule.binary_status is not None:
                    dev_data["binary_status"] = schedule.binary_status
                site_devices[dev_name] = dev_data
            sites_data[site_id] = {"device_schedules": site_devices}
        result["sites"] = sites_data

    return result


def _build_device_summaries(response: Any, detail_level: str) -> dict[str, Any]:
    """Build per-device summaries from response data."""
    summaries: dict[str, Any] = {}

    for site_id, site_result in response.sites.items():
        for dev_name, schedule in site_result.device_schedules.items():
            dev_summary: dict[str, Any] = {}

            for material, flow_data in schedule.flows.items():
                total = sum(flow_data)
                dev_summary[f"total_{material}_mwh"] = round(total, 2)

            if schedule.soc:
                dev_summary["avg_soc"] = round(sum(schedule.soc) / len(schedule.soc), 3)

            if detail_level == "monthly" and schedule.flows:
                first_flow = list(schedule.flows.values())[0]
                hours_total = len(first_flow)
                monthly: list[dict[str, Any]] = []
                for month_idx in range(min(12, (hours_total + 729) // 730)):
                    start = month_idx * 730
                    end = min(start + 730, hours_total)
                    month_data: dict[str, Any] = {"month": month_idx + 1}
                    for material, flow_data in schedule.flows.items():
                        month_slice = flow_data[start:end]
                        month_data[f"total_{material}_mwh"] = round(sum(month_slice), 2)
                    monthly.append(month_data)
                dev_summary["monthly"] = monthly

            summaries[dev_name] = dev_summary

    return summaries


def cancel_job(job_id: str) -> dict[str, str]:
    """Cancel a pending or running job.

    :param job_id: Job to cancel.
    :returns: Dict with job_id and updated status.
    """
    client = _get_client()
    job = client.cancel_job(job_id)
    return {"job_id": job.job_id, "status": job.status}


def list_jobs() -> list[dict[str, Any]]:
    """List all scenarios and their associated jobs.

    :returns: List of scenarios with their job IDs and counts.
    """
    scenarios = _store.list()
    result: list[dict[str, Any]] = []
    for s in scenarios:
        scenario = _store.get(s.id)
        result.append(
            {
                "scenario_id": s.id,
                "scenario_name": s.name,
                "job_ids": scenario.jobs,
                "job_count": len(scenario.jobs),
            }
        )
    return result


# --- Data File Tools ---


def save_data_file(
    file_path: str,
    columns: dict[str, list[float]],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Save generated data to a CSV file on the local filesystem.

    This tool exists because you (the LLM) cannot write files directly --
    but this MCP server runs on the user's local machine and CAN.
    Use it to persist generated data arrays (prices, demand profiles, etc.)
    so they can be referenced in add_device via {"file": "<path>", "column": "<name>"}.

    Typical workflow:
    1. Generate price/demand data as arrays
    2. Call save_data_file to write them as CSV
    3. Use the returned file_path in add_device properties

    :param file_path: Filename or path (e.g., "prices_2025.csv").
        Relative paths resolve against INVESTMENT_DATA_DIR env var (or cwd).
        Extension '.csv' is appended if missing.
    :param columns: Named columns of numeric data.
        Example: {"hour": [0, 1, 2, ...], "price_eur_mwh": [30.5, 42.1, ...]}.
        All columns must have the same length.
    :param overwrite: Allow overwriting an existing file (default: False).
    :returns: Dict with file_path (absolute), column names, and row count.
    """
    data_dir = get_data_dir()
    saved_path = save_csv(
        file_path=file_path,
        columns=columns,
        data_dir=data_dir,
        overwrite=overwrite,
    )
    col_names = list(columns.keys())
    row_count = len(next(iter(columns.values())))
    return {
        "file_path": saved_path,
        "columns": col_names,
        "rows": row_count,
        "message": f"Saved {row_count} rows to {saved_path}",
    }


# --- Helper Tools ---


def get_device_schema(device_type: str) -> dict[str, Any]:
    """Get the properties schema for a device type.

    Shows required/optional properties, types, units, ranges, and defaults.
    Use this before add_device to know what properties are needed.

    :param device_type: e.g., "battery", "chp", "photovoltaic", "electricity_import".
    :returns: Schema dict with properties documentation.
    """
    schemas: dict[str, dict[str, Any]] = {
        "battery": {
            "device_type": "battery",
            "properties": {
                "capacity": {"type": "float", "required": True, "unit": "MWh", "description": "Energy capacity"},
                "max_power": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Power rating for charge/discharge",
                },
                "efficiency": {
                    "type": "float",
                    "required": True,
                    "range": "0-1",
                    "description": "Round-trip efficiency",
                },
                "initial_soc": {
                    "type": "float",
                    "required": False,
                    "default": 0.5,
                    "range": "0-1",
                    "description": "Initial state of charge",
                },
                "soc_anchor_interval_hours": {
                    "type": "int",
                    "required": False,
                    "description": "Force SOC to target at regular intervals (hours). E.g., 4320 = every 6 months",
                },
                "soc_anchor_target": {
                    "type": "float",
                    "required": False,
                    "default": 0.5,
                    "range": "0-1",
                    "description": "Target SOC at anchor points",
                },
            },
            "supports_schedule": True,
            "example": {
                "capacity": 10.0,
                "max_power": 5.0,
                "efficiency": 0.90,
                "initial_soc": 0.5,
            },
        },
        "chp": {
            "device_type": "chp",
            "properties": {
                "gas_input": {"type": "float", "required": True, "unit": "MW", "description": "Gas consumption"},
                "el_output": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Electricity generation",
                },
                "heat_output": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Heat generation",
                },
                "is_binary": {
                    "type": "bool",
                    "required": False,
                    "default": False,
                    "description": "On/off only (relaxed for investment)",
                },
                "min_power": {
                    "type": "float",
                    "required": False,
                    "range": "0-1",
                    "description": "Min power fraction",
                },
            },
            "supports_schedule": True,
            "example": {"gas_input": 4.0, "el_output": 2.0, "heat_output": 1.5},
        },
        "heat_accumulator": {
            "device_type": "heat_accumulator",
            "properties": {
                "capacity": {
                    "type": "float",
                    "required": True,
                    "unit": "MWh",
                    "description": "Thermal energy capacity",
                },
                "max_power": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Charge/discharge power",
                },
                "efficiency": {
                    "type": "float",
                    "required": True,
                    "range": "0-1",
                    "description": "Storage efficiency",
                },
                "initial_soc": {
                    "type": "float",
                    "required": False,
                    "default": 0.5,
                    "range": "0-1",
                    "description": "Initial state of charge",
                },
                "loss_rate": {
                    "type": "float",
                    "required": False,
                    "default": 0.001,
                    "description": "Standing losses (fraction/hour)",
                },
            },
            "supports_schedule": True,
            "example": {
                "capacity": 50.0,
                "max_power": 10.0,
                "efficiency": 0.95,
                "loss_rate": 0.001,
            },
        },
        "photovoltaic": {
            "device_type": "photovoltaic",
            "properties": {
                "peak_power_mw": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Peak power capacity",
                },
                "location": {
                    "type": "object",
                    "required": True,
                    "description": "Geographic location {latitude: float, longitude: float}",
                },
                "tilt": {
                    "type": "int",
                    "required": True,
                    "range": "0-90",
                    "unit": "degrees",
                    "description": "Panel tilt angle",
                },
                "azimuth": {
                    "type": "int",
                    "required": True,
                    "range": "0-359",
                    "unit": "degrees",
                    "description": "Azimuth (180=south)",
                },
                "generation_profile": {
                    "type": "list[float]",
                    "required": False,
                    "description": "Normalized generation profile (0-1). Loaded from PVGIS if not provided.",
                },
            },
            "supports_schedule": True,
            "example": {
                "peak_power_mw": 5.0,
                "location": {"latitude": 50.07, "longitude": 14.44},
                "tilt": 35,
                "azimuth": 180,
            },
        },
        "electricity_import": {
            "device_type": "electricity_import",
            "properties": {
                "price": {
                    "type": "float | list[float] | {file: str}",
                    "required": True,
                    "unit": "EUR/MWh",
                    "description": "Price profile. Supports: flat value, array, or {file: 'path.csv'}",
                },
                "max_import": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Maximum import capacity",
                },
                "max_import_unit_cost": {
                    "type": "float",
                    "required": False,
                    "unit": "EUR/MW/year",
                    "description": "Reserved capacity cost",
                },
            },
            "supports_schedule": False,
            "example": {"price": 50.0, "max_import": 10.0},
        },
        "electricity_export": {
            "device_type": "electricity_export",
            "properties": {
                "price": {
                    "type": "float | list[float] | {file: str}",
                    "required": True,
                    "unit": "EUR/MWh",
                    "description": "Price profile. Supports: flat value, array, or {file: 'path.csv'}",
                },
                "max_export": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Maximum export capacity",
                },
                "max_export_unit_cost": {
                    "type": "float",
                    "required": False,
                    "unit": "EUR/MW/year",
                    "description": "Export capacity cost",
                },
            },
            "supports_schedule": False,
            "example": {"price": 50.0, "max_export": 10.0},
        },
        "gas_import": {
            "device_type": "gas_import",
            "properties": {
                "price": {
                    "type": "float | list[float] | {file: str}",
                    "required": True,
                    "unit": "EUR/MWh",
                    "description": "Gas price profile",
                },
                "max_import": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Maximum gas import capacity",
                },
                "max_import_unit_cost": {
                    "type": "float",
                    "required": False,
                    "unit": "EUR/MW/year",
                    "description": "Reserved capacity cost",
                },
            },
            "supports_schedule": False,
            "example": {"price": 35.0, "max_import": 5.0},
        },
        "heat_export": {
            "device_type": "heat_export",
            "properties": {
                "price": {
                    "type": "float | list[float] | {file: str}",
                    "required": True,
                    "unit": "EUR/MWh",
                    "description": "Heat price profile",
                },
                "max_export": {
                    "type": "float",
                    "required": True,
                    "unit": "MW",
                    "description": "Maximum heat export capacity",
                },
                "max_export_unit_cost": {
                    "type": "float",
                    "required": False,
                    "unit": "EUR/MW/year",
                    "description": "Export capacity cost",
                },
            },
            "supports_schedule": False,
            "example": {"price": 40.0, "max_export": 2.0},
        },
        "electricity_demand": {
            "device_type": "electricity_demand",
            "properties": {
                "max_demand_profile": {
                    "type": "float | list[float] | {file: str}",
                    "required": True,
                    "unit": "MW",
                    "description": "Maximum demand profile (MW, not MWh!)",
                },
                "min_demand_profile": {
                    "type": "float | list[float] | {file: str}",
                    "required": False,
                    "default": 0,
                    "unit": "MW",
                    "description": "Minimum demand profile or constant. Supports file loading.",
                },
            },
            "supports_schedule": False,
            "example": {"max_demand_profile": 5.0},
        },
        "heat_demand": {
            "device_type": "heat_demand",
            "properties": {
                "max_demand_profile": {
                    "type": "float | list[float] | {file: str}",
                    "required": True,
                    "unit": "MW",
                    "description": "Maximum heat demand profile (MW)",
                },
                "min_demand_profile": {
                    "type": "float | list[float] | {file: str}",
                    "required": False,
                    "default": 0,
                    "unit": "MW",
                    "description": "Minimum heat demand profile or constant. Supports file loading.",
                },
            },
            "supports_schedule": False,
            "example": {"max_demand_profile": 3.0},
        },
    }

    dtype = device_type.lower()
    if dtype not in schemas:
        return {
            "error": f"Unknown device type '{device_type}'.",
            "valid_types": sorted(schemas.keys()),
        }

    return schemas[dtype]


def get_version() -> dict:
    """Return site-calc-investment client version and server API version.

    Shows the installed client package version. If the server is reachable,
    also shows the server API version and whether they are compatible.
    """
    result: dict[str, Any] = {"client_version": __version__}

    try:
        client = _get_client()
        response = client._client.get("/health")
        if response.status_code == 200:
            health = response.json()
            server_version = health.get("api_version")
            if server_version:
                result["server_api_version"] = server_version
                client_api = ".".join(__version__.split(".")[:2])
                server_api = ".".join(str(server_version).split(".")[:2])
                result["compatible"] = client_api == server_api
    except Exception:
        result["server_api_version"] = "unavailable"

    return result


# --- Visualization Tools ---


def visualize_results(job_id: str, open_browser: bool = True) -> dict[str, Any]:
    """Generate an interactive HTML dashboard for a completed optimization job.

    Creates a self-contained HTML file with three tabs:
    - Financial Analysis: KPIs (NPV, IRR, payback), annual revenue/costs chart, cash flow curve
    - Energy Balance: Stacked generation/consumption chart, energy summary KPIs
    - Device Detail: Interactive dispatch and SOC charts with date range drill-down

    The dashboard uses Plotly.js (loaded via CDN) for interactive charts.
    No additional Python dependencies are required.

    :param job_id: Job identifier (must be a completed job).
    :param open_browser: Open the dashboard in the default browser (default: True).
    :returns: Dict with file_path, charts_generated, summary, and message.
    """
    client = _get_client()
    response = client.get_job_result(job_id)

    from site_calc_investment.visualization.dashboard import generate_dashboard

    data_dir = get_data_dir()
    output_dir = None
    if data_dir:
        import os

        output_dir = os.path.join(data_dir, "dashboards")

    return generate_dashboard(
        job_id=job_id,
        response=response,
        open_browser=open_browser,
        output_dir=output_dir,
    )


# --- Register all functions as MCP tools ---

mcp.tool()(get_version)
mcp.tool()(create_scenario)
mcp.tool()(add_device)
mcp.tool()(set_timespan)
mcp.tool()(set_investment_params)
mcp.tool()(review_scenario)
mcp.tool()(remove_device)
mcp.tool()(delete_scenario)
mcp.tool()(list_scenarios)
mcp.tool()(submit_scenario)
mcp.tool()(get_job_status)
mcp.tool()(get_job_result)
mcp.tool()(cancel_job)
mcp.tool()(list_jobs)
mcp.tool()(get_device_schema)
mcp.tool()(save_data_file)
mcp.tool()(visualize_results)
