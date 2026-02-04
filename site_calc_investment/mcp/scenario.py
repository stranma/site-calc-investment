"""In-memory storage for draft optimization scenarios."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from site_calc_investment.models.common import Resolution
from site_calc_investment.models.devices import (
    CHP,
    Battery,
    BatteryProperties,
    CHPProperties,
    DemandProperties,
    ElectricityDemand,
    ElectricityExport,
    ElectricityImport,
    GasImport,
    HeatAccumulator,
    HeatAccumulatorProperties,
    HeatDemand,
    HeatExport,
    MarketExportProperties,
    MarketImportProperties,
    Photovoltaic,
    PhotovoltaicProperties,
    Schedule,
)
from site_calc_investment.models.requests import (
    InvestmentParameters,
    InvestmentPlanningRequest,
    OptimizationConfig,
    Site,
    TimeSpanInvestment,
)


@dataclass
class TimespanConfig:
    """Draft timespan configuration."""

    start_year: int
    years: int = 1


@dataclass
class InvestmentParamsConfig:
    """Draft investment parameters configuration."""

    discount_rate: float = 0.05
    project_lifetime_years: Optional[int] = None
    device_capital_costs: Optional[dict[str, float]] = None
    device_annual_opex: Optional[dict[str, float]] = None


@dataclass
class DeviceConfig:
    """Raw device configuration before conversion to Pydantic models."""

    device_type: str
    name: str
    properties: dict[str, Any]
    schedule: Optional[dict[str, Any]] = None


@dataclass
class Scenario:
    """A draft optimization scenario."""

    id: str
    name: str
    description: str = ""
    devices: list[DeviceConfig] = field(default_factory=list)
    timespan: Optional[TimespanConfig] = None
    investment_params: Optional[InvestmentParamsConfig] = None
    jobs: list[str] = field(default_factory=list)


@dataclass
class ScenarioInfo:
    """Summary info for listing scenarios."""

    id: str
    name: str
    device_count: int
    has_timespan: bool
    job_count: int


DEVICE_TYPE_MAP: dict[str, str] = {
    "battery": "battery",
    "chp": "chp",
    "heat_accumulator": "heat_accumulator",
    "photovoltaic": "photovoltaic",
    "heat_demand": "heat_demand",
    "electricity_demand": "electricity_demand",
    "electricity_import": "electricity_import",
    "electricity_export": "electricity_export",
    "gas_import": "gas_import",
    "heat_export": "heat_export",
}

VALID_DEVICE_TYPES: set[str] = set(DEVICE_TYPE_MAP.keys())


def _build_schedule(schedule_dict: Optional[dict[str, Any]]) -> Optional[Schedule]:
    """Build a Schedule object from a raw dict, or None."""
    if schedule_dict is None:
        return None
    return Schedule(**schedule_dict)


def _build_device(config: DeviceConfig, expected_length: Optional[int]) -> Any:
    """Build a Pydantic device model from a DeviceConfig.

    :param config: Raw device configuration.
    :param expected_length: Expected array length for price/profile expansion (from timespan).
    :returns: A Pydantic device model instance.
    :raises ValueError: If the device type is unknown or properties are invalid.
    """
    from site_calc_investment.mcp.data_loaders import resolve_price_or_profile

    dtype = config.device_type.lower()
    props = dict(config.properties)
    schedule = _build_schedule(config.schedule)

    if dtype == "battery":
        return Battery(name=config.name, properties=BatteryProperties(**props), schedule=schedule)

    elif dtype == "chp":
        return CHP(name=config.name, properties=CHPProperties(**props), schedule=schedule)

    elif dtype == "heat_accumulator":
        return HeatAccumulator(name=config.name, properties=HeatAccumulatorProperties(**props), schedule=schedule)

    elif dtype == "photovoltaic":
        if "location" in props and isinstance(props["location"], dict):
            from site_calc_investment.models.common import Location

            props["location"] = Location(**props["location"])
        if "generation_profile" in props and props["generation_profile"] is not None:
            props["generation_profile"] = resolve_price_or_profile(props["generation_profile"], expected_length)
        return Photovoltaic(name=config.name, properties=PhotovoltaicProperties(**props), schedule=schedule)

    elif dtype == "heat_demand":
        props["max_demand_profile"] = resolve_price_or_profile(props["max_demand_profile"], expected_length)
        if "min_demand_profile" in props and not isinstance(props["min_demand_profile"], (int, float)):
            props["min_demand_profile"] = resolve_price_or_profile(props["min_demand_profile"], expected_length)
        return HeatDemand(name=config.name, properties=DemandProperties(**props))

    elif dtype == "electricity_demand":
        props["max_demand_profile"] = resolve_price_or_profile(props["max_demand_profile"], expected_length)
        if "min_demand_profile" in props and not isinstance(props["min_demand_profile"], (int, float)):
            props["min_demand_profile"] = resolve_price_or_profile(props["min_demand_profile"], expected_length)
        return ElectricityDemand(name=config.name, properties=DemandProperties(**props))

    elif dtype == "electricity_import":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return ElectricityImport(name=config.name, properties=MarketImportProperties(**props))

    elif dtype == "electricity_export":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return ElectricityExport(name=config.name, properties=MarketExportProperties(**props))

    elif dtype == "gas_import":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return GasImport(name=config.name, properties=MarketImportProperties(**props))

    elif dtype == "heat_export":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return HeatExport(name=config.name, properties=MarketExportProperties(**props))

    else:
        raise ValueError(f"Unknown device type: {dtype}")


class ScenarioStore:
    """In-memory storage for draft optimization scenarios."""

    def __init__(self) -> None:
        self._scenarios: dict[str, Scenario] = {}

    def create(self, name: str, description: str = "") -> str:
        """Create a new draft scenario.

        :param name: Human-readable scenario name.
        :param description: Optional description.
        :returns: scenario_id (UUID).
        """
        scenario_id = f"sc_{uuid.uuid4().hex[:8]}"
        self._scenarios[scenario_id] = Scenario(id=scenario_id, name=name, description=description)
        return scenario_id

    def get(self, scenario_id: str) -> Scenario:
        """Get a scenario by ID.

        :raises KeyError: If scenario not found.
        """
        if scenario_id not in self._scenarios:
            raise KeyError(f"Scenario '{scenario_id}' not found. Use list_scenarios to see active scenarios.")
        return self._scenarios[scenario_id]

    def add_device(
        self,
        scenario_id: str,
        device_type: str,
        name: str,
        properties: dict[str, Any],
        schedule: Optional[dict[str, Any]] = None,
    ) -> str:
        """Add a device to a draft scenario.

        :param scenario_id: Target scenario.
        :param device_type: One of the valid device types.
        :param name: Unique device name within the scenario.
        :param properties: Device-specific properties dict.
        :param schedule: Optional schedule constraints dict.
        :returns: Summary string of the added device.
        :raises KeyError: If scenario not found.
        :raises ValueError: If device_type is invalid or name is duplicate.
        """
        scenario = self.get(scenario_id)
        dtype = device_type.lower()

        if dtype not in VALID_DEVICE_TYPES:
            raise ValueError(
                f"Unknown device type '{device_type}'. Valid types: {', '.join(sorted(VALID_DEVICE_TYPES))}"
            )

        existing_names = {d.name for d in scenario.devices}
        if name in existing_names:
            raise ValueError(
                f"Device name '{name}' already exists in scenario '{scenario.name}'. "
                "Device names must be unique within a scenario."
            )

        config = DeviceConfig(device_type=dtype, name=name, properties=properties, schedule=schedule)
        scenario.devices.append(config)

        return _device_summary(config)

    def remove_device(self, scenario_id: str, device_name: str) -> None:
        """Remove a device from a draft scenario.

        :raises KeyError: If scenario not found or device not found.
        """
        scenario = self.get(scenario_id)
        for i, d in enumerate(scenario.devices):
            if d.name == device_name:
                scenario.devices.pop(i)
                return
        raise KeyError(
            f"Device '{device_name}' not found in scenario '{scenario.name}'. "
            f"Devices: {', '.join(d.name for d in scenario.devices) or '(none)'}"
        )

    def set_timespan(self, scenario_id: str, start_year: int, years: int = 1) -> str:
        """Set the optimization time horizon.

        :returns: Summary string with interval count.
        """
        scenario = self.get(scenario_id)
        scenario.timespan = TimespanConfig(start_year=start_year, years=years)
        intervals = years * 8760
        return (
            f"Timespan set: {start_year}-01-01 to {start_year + years - 1}-12-31 ({intervals} intervals, 1h resolution)"
        )

    def set_investment_params(
        self,
        scenario_id: str,
        discount_rate: float = 0.05,
        project_lifetime_years: Optional[int] = None,
        device_capital_costs: Optional[dict[str, float]] = None,
        device_annual_opex: Optional[dict[str, float]] = None,
    ) -> str:
        """Set financial parameters for ROI calculation.

        :returns: Confirmation string.
        """
        scenario = self.get(scenario_id)
        scenario.investment_params = InvestmentParamsConfig(
            discount_rate=discount_rate,
            project_lifetime_years=project_lifetime_years,
            device_capital_costs=device_capital_costs,
            device_annual_opex=device_annual_opex,
        )
        parts = [f"discount_rate={discount_rate:.1%}"]
        if project_lifetime_years is not None:
            parts.append(f"lifetime={project_lifetime_years}y")
        if device_capital_costs:
            total = sum(device_capital_costs.values())
            parts.append(f"CAPEX total={total:,.0f} EUR")
        if device_annual_opex:
            total = sum(device_annual_opex.values())
            parts.append(f"annual OPEX total={total:,.0f} EUR")
        return f"Investment parameters set: {', '.join(parts)}"

    def review(self, scenario_id: str) -> dict[str, Any]:
        """Review the current draft scenario.

        :returns: Summary dict with devices, timespan, investment params, validation.
        """
        scenario = self.get(scenario_id)

        device_summaries = []
        for d in scenario.devices:
            device_summaries.append(
                {
                    "name": d.name,
                    "type": d.device_type,
                    "summary": _device_summary(d),
                }
            )

        timespan_str = "not set"
        if scenario.timespan:
            intervals = scenario.timespan.years * 8760
            timespan_str = f"{scenario.timespan.start_year}, {scenario.timespan.years} year(s), {intervals} intervals"

        investment_str = "not set (no CAPEX/OPEX analysis)"
        if scenario.investment_params:
            ip = scenario.investment_params
            parts = [f"{ip.discount_rate:.1%} discount rate"]
            if ip.project_lifetime_years:
                parts.append(f"{ip.project_lifetime_years}y lifetime")
            if ip.device_capital_costs:
                parts.append(f"CAPEX for {len(ip.device_capital_costs)} devices")
            investment_str = ", ".join(parts)

        errors = []
        if not scenario.devices:
            errors.append("No devices added")
        if not scenario.timespan:
            errors.append("No timespan set")

        validation = "Valid -- ready to submit" if not errors else f"Not ready: {'; '.join(errors)}"

        return {
            "name": scenario.name,
            "description": scenario.description,
            "devices": device_summaries,
            "timespan": timespan_str,
            "investment_params": investment_str,
            "validation": validation,
            "job_count": len(scenario.jobs),
        }

    def build_request(
        self,
        scenario_id: str,
        objective: str = "maximize_profit",
        solver_timeout: int = 300,
    ) -> InvestmentPlanningRequest:
        """Convert draft scenario to an InvestmentPlanningRequest.

        :raises ValueError: If scenario is not ready (missing devices or timespan).
        """
        scenario = self.get(scenario_id)

        if not scenario.devices:
            raise ValueError("Cannot submit: no devices added to the scenario.")
        if not scenario.timespan:
            raise ValueError("Cannot submit: no timespan set. Use set_timespan first.")

        ts_config = scenario.timespan
        timespan = TimeSpanInvestment.for_years(
            start_year=ts_config.start_year,
            years=ts_config.years,
            resolution=Resolution.HOUR_1,
        )
        expected_length = ts_config.years * 8760

        devices = []
        for dc in scenario.devices:
            device = _build_device(dc, expected_length)
            devices.append(device)

        site = Site(
            site_id=f"site_{scenario_id}",
            description=scenario.name,
            devices=devices,
        )

        opt_config = OptimizationConfig(
            objective=objective,
            time_limit_seconds=min(solver_timeout, 900),
        )

        inv_params = None
        if scenario.investment_params:
            ip = scenario.investment_params
            lifetime = ip.project_lifetime_years or ts_config.years
            inv_params = InvestmentParameters(
                discount_rate=ip.discount_rate,
                project_lifetime_years=lifetime,
                device_capital_costs=ip.device_capital_costs,
                device_annual_opex=ip.device_annual_opex,
            )

        return InvestmentPlanningRequest(
            sites=[site],
            timespan=timespan,
            investment_parameters=inv_params,
            optimization_config=opt_config,
        )

    def record_job(self, scenario_id: str, job_id: str) -> None:
        """Record a submitted job ID against a scenario."""
        scenario = self.get(scenario_id)
        scenario.jobs.append(job_id)

    def delete(self, scenario_id: str) -> None:
        """Delete a draft scenario.

        :raises KeyError: If scenario not found.
        """
        if scenario_id not in self._scenarios:
            raise KeyError(f"Scenario '{scenario_id}' not found.")
        del self._scenarios[scenario_id]

    def list(self) -> list[ScenarioInfo]:
        """List all active draft scenarios."""
        result = []
        for s in self._scenarios.values():
            result.append(
                ScenarioInfo(
                    id=s.id,
                    name=s.name,
                    device_count=len(s.devices),
                    has_timespan=s.timespan is not None,
                    job_count=len(s.jobs),
                )
            )
        return result


def _device_summary(config: DeviceConfig) -> str:
    """Generate a human-readable summary of a device config."""
    props = config.properties
    dtype = config.device_type.lower()

    if dtype == "battery":
        cap = props.get("capacity", "?")
        pwr = props.get("max_power", "?")
        eff = props.get("efficiency", "?")
        eff_str = f"{float(eff) * 100:.0f}%" if isinstance(eff, (int, float)) else str(eff)
        return f"{cap} MWh / {pwr} MW / {eff_str} eff"

    elif dtype == "chp":
        gas = props.get("gas_input", "?")
        el = props.get("el_output", "?")
        heat = props.get("heat_output", "?")
        return f"gas {gas} MW -> el {el} MW + heat {heat} MW"

    elif dtype == "heat_accumulator":
        cap = props.get("capacity", "?")
        pwr = props.get("max_power", "?")
        eff = props.get("efficiency", "?")
        eff_str = f"{float(eff) * 100:.0f}%" if isinstance(eff, (int, float)) else str(eff)
        return f"{cap} MWh / {pwr} MW / {eff_str} eff (thermal)"

    elif dtype == "photovoltaic":
        peak = props.get("peak_power_mw", "?")
        return f"{peak} MW peak"

    elif dtype in ("heat_demand", "electricity_demand"):
        profile = props.get("max_demand_profile", [])
        if isinstance(profile, list) and profile:
            avg = sum(profile) / len(profile)
            return f"avg {avg:.1f} MW, {len(profile)} intervals"
        return "demand profile configured"

    elif dtype in ("electricity_import", "gas_import"):
        max_imp = props.get("max_import", "?")
        price = props.get("price")
        price_str = _price_summary(price)
        return f"max {max_imp} MW, {price_str}"

    elif dtype in ("electricity_export", "heat_export"):
        max_exp = props.get("max_export", "?")
        price = props.get("price")
        price_str = _price_summary(price)
        return f"max {max_exp} MW, {price_str}"

    return f"{dtype} device"


def _price_summary(price: Any) -> str:
    """Summarize a price value for display."""
    if isinstance(price, (int, float)):
        return f"flat {price} EUR/MWh"
    elif isinstance(price, list):
        if price:
            avg = sum(price) / len(price)
            return f"avg {avg:.1f} EUR/MWh ({len(price)} pts)"
        return "empty price array"
    elif isinstance(price, dict):
        if "file" in price:
            return f"from file: {price['file']}"
    return "price configured"
