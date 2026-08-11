"""In-memory storage for draft optimization scenarios."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, cast

from site_calc_investment.models.capacity import DeviceInvestment
from site_calc_investment.models.common import Resolution
from site_calc_investment.models.devices import (
    CHP,
    Battery,
    BatteryProperties,
    CHPProperties,
    CzDistributionImport,
    CzDistributionImportProperties,
    DemandProperties,
    ElectricityDemand,
    ElectricityExport,
    ElectricityImport,
    FixedConsumption,
    FixedProduction,
    FixedProfileProperties,
    GasImport,
    GasImportProperties,
    HeatAccumulator,
    HeatAccumulatorProperties,
    HeatDemand,
    HeatExport,
    HeatExportProperties,
    MarketExportProperties,
    MarketImportProperties,
    MaxPowerConsumption,
    MaxPowerConsumptionProperties,
    MaxPowerProduction,
    MaxPowerProductionProperties,
    PhotovoltaicNonSteerable,
    PhotovoltaicSteerable,
    PhotovoltaicSteerableProperties,
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
    intervals: Optional[int] = None


@dataclass
class InvestmentParamsConfig:
    """Draft investment parameters configuration."""

    discount_rate: float = 0.05
    project_lifetime_years: Optional[int] = None


@dataclass
class DeviceConfig:
    """Raw device configuration before conversion to Pydantic models."""

    device_type: str
    name: str
    properties: dict[str, Any]
    schedule: Optional[dict[str, Any]] = None
    investment: Optional[dict[str, Any]] = None


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
    "photovoltaic_nonsteerable": "photovoltaic_nonsteerable",
    "photovoltaic_steerable": "photovoltaic_steerable",
    "fixed_production": "fixed_production",
    "max_power_production": "max_power_production",
    "fixed_consumption": "fixed_consumption",
    "max_power_consumption": "max_power_consumption",
    "heat_demand": "heat_demand",
    "electricity_demand": "electricity_demand",
    "electricity_import": "electricity_import",
    "electricity_export": "electricity_export",
    "gas_import": "gas_import",
    "heat_export": "heat_export",
    "cz_distribution_import": "cz_distribution_import",
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
    investment = DeviceInvestment(**config.investment) if config.investment else None

    if dtype == "battery":
        return Battery(
            name=config.name, properties=BatteryProperties(**props), schedule=schedule, investment=investment
        )

    elif dtype == "chp":
        return CHP(name=config.name, properties=CHPProperties(**props), schedule=schedule, investment=investment)

    elif dtype == "heat_accumulator":
        return HeatAccumulator(
            name=config.name, properties=HeatAccumulatorProperties(**props), schedule=schedule, investment=investment
        )

    elif dtype in ("photovoltaic_nonsteerable", "fixed_production", "fixed_consumption"):
        props["power_profile"] = resolve_price_or_profile(props["power_profile"], expected_length)
        model = {
            "photovoltaic_nonsteerable": PhotovoltaicNonSteerable,
            "fixed_production": FixedProduction,
            "fixed_consumption": FixedConsumption,
        }[dtype]
        return model(name=config.name, properties=FixedProfileProperties(**props), investment=investment)

    elif dtype == "photovoltaic_steerable":
        props["max_power_profile"] = resolve_price_or_profile(props["max_power_profile"], expected_length)
        return PhotovoltaicSteerable(
            name=config.name, properties=PhotovoltaicSteerableProperties(**props), investment=investment
        )

    elif dtype == "max_power_production":
        props["max_power_profile"] = resolve_price_or_profile(props["max_power_profile"], expected_length)
        return MaxPowerProduction(
            name=config.name, properties=MaxPowerProductionProperties(**props), investment=investment
        )

    elif dtype == "max_power_consumption":
        props["max_power_profile"] = resolve_price_or_profile(props["max_power_profile"], expected_length)
        return MaxPowerConsumption(
            name=config.name, properties=MaxPowerConsumptionProperties(**props), investment=investment
        )

    elif dtype == "heat_demand":
        props["max_demand_profile"] = resolve_price_or_profile(props["max_demand_profile"], expected_length)
        if "min_demand_profile" in props and props["min_demand_profile"] is not None:
            if not isinstance(props["min_demand_profile"], (int, float)):
                props["min_demand_profile"] = resolve_price_or_profile(props["min_demand_profile"], expected_length)
        return HeatDemand(name=config.name, properties=DemandProperties(**props), investment=investment)

    elif dtype == "electricity_demand":
        props["max_demand_profile"] = resolve_price_or_profile(props["max_demand_profile"], expected_length)
        if "min_demand_profile" in props and props["min_demand_profile"] is not None:
            if not isinstance(props["min_demand_profile"], (int, float)):
                props["min_demand_profile"] = resolve_price_or_profile(props["min_demand_profile"], expected_length)
        return ElectricityDemand(name=config.name, properties=DemandProperties(**props), investment=investment)

    elif dtype == "electricity_import":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return ElectricityImport(name=config.name, properties=MarketImportProperties(**props), investment=investment)

    elif dtype == "electricity_export":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return ElectricityExport(name=config.name, properties=MarketExportProperties(**props), investment=investment)

    elif dtype == "gas_import":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return GasImport(name=config.name, properties=GasImportProperties(**props), investment=investment)

    elif dtype == "heat_export":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return HeatExport(name=config.name, properties=HeatExportProperties(**props), investment=investment)

    elif dtype == "cz_distribution_import":
        props["price"] = resolve_price_or_profile(props["price"], expected_length)
        return CzDistributionImport(
            name=config.name, properties=CzDistributionImportProperties(**props), investment=investment
        )

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
        investment: Optional[dict[str, Any]] = None,
    ) -> str:
        """Add a device to a draft scenario.

        :param scenario_id: Target scenario.
        :param device_type: One of the valid device types.
        :param name: Unique device name within the scenario.
        :param properties: Device-specific properties dict.
        :param schedule: Optional schedule constraints dict.
        :param investment: Optional fixed costs for client-side NPV, e.g.
                           ``{"capital_cost": 500000, "annual_opex": 10000}``.
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

        if investment is not None:
            # Validate eagerly so a typo ({"capex": 1}) or wrong type fails
            # here at input time, not at submit time in _build_device.
            try:
                DeviceInvestment(**investment)
            except Exception as e:
                raise ValueError(f"Invalid investment block for device '{name}': {e}") from e

        config = DeviceConfig(
            device_type=dtype, name=name, properties=properties, schedule=schedule, investment=investment
        )
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

    def set_timespan(self, scenario_id: str, start_year: int, years: int = 1, intervals: Optional[int] = None) -> str:
        """Set the optimization time horizon.

        :param intervals: Explicit interval count (1-100,000). Overrides years * 8760 when provided.
        :returns: Summary string with interval count.
        """
        if intervals is not None:
            if intervals < 1 or intervals > 100_000:
                raise ValueError(f"intervals must be between 1 and 100,000, got {intervals}.")
            effective_intervals = intervals
        else:
            if years < 1:
                raise ValueError("Timespan must be at least 1 year.")
            effective_intervals = years * 8760
            if effective_intervals > 100_000:
                raise ValueError(
                    f"Timespan of {years} years ({effective_intervals} intervals) exceeds the 100,000 interval limit."
                )

        scenario = self.get(scenario_id)
        scenario.timespan = TimespanConfig(start_year=start_year, years=years, intervals=intervals)
        return f"Timespan set: {start_year}, {effective_intervals} intervals (1h resolution)"

    def set_investment_params(
        self,
        scenario_id: str,
        discount_rate: float = 0.05,
        project_lifetime_years: Optional[int] = None,
    ) -> str:
        """Set global financial parameters for ROI calculation.

        Per-device CAPEX/OPEX belongs on each device's ``investment``
        block (see add_device).

        :returns: Confirmation string.
        """
        scenario = self.get(scenario_id)
        scenario.investment_params = InvestmentParamsConfig(
            discount_rate=discount_rate,
            project_lifetime_years=project_lifetime_years,
        )
        parts = [f"discount_rate={discount_rate:.1%}"]
        if project_lifetime_years is not None:
            parts.append(f"lifetime={project_lifetime_years}y")
        return f"Investment parameters set: {', '.join(parts)}"

    def review(self, scenario_id: str) -> dict[str, Any]:
        """Review the current draft scenario.

        :returns: Summary dict with devices, timespan, investment params, validation.
        """
        scenario = self.get(scenario_id)

        device_summaries = []
        total_capex = 0.0
        total_opex = 0.0
        for d in scenario.devices:
            entry = {
                "name": d.name,
                "type": d.device_type,
                "summary": _device_summary(d),
            }
            if d.investment:
                capex = d.investment.get("capital_cost") or 0.0
                opex = d.investment.get("annual_opex") or 0.0
                total_capex += capex
                total_opex += opex
                entry["investment"] = f"CAPEX {capex:,.0f} EUR, OPEX {opex:,.0f} EUR/year"
            device_summaries.append(entry)

        timespan_str = "not set"
        if scenario.timespan:
            ts = scenario.timespan
            effective_intervals = ts.intervals if ts.intervals is not None else ts.years * 8760
            if ts.intervals is not None:
                timespan_str = f"{ts.start_year}, {effective_intervals} intervals (custom)"
            else:
                timespan_str = f"{ts.start_year}, {ts.years} year(s), {effective_intervals} intervals"

        investment_str = "not set (no NPV/IRR analysis)"
        if scenario.investment_params:
            ip = scenario.investment_params
            parts = [f"{ip.discount_rate:.1%} discount rate"]
            if ip.project_lifetime_years:
                parts.append(f"{ip.project_lifetime_years}y lifetime")
            investment_str = ", ".join(parts)
        if total_capex or total_opex:
            investment_str += f"; devices carry CAPEX {total_capex:,.0f} EUR, OPEX {total_opex:,.0f} EUR/year"

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
        objective: Literal["maximize_profit", "minimize_cost", "maximize_self_consumption"] = "maximize_profit",
        solver_timeout: int = 300,
        mip_gap: float = 0.01,
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
        if ts_config.intervals is not None:
            from datetime import datetime
            from zoneinfo import ZoneInfo

            start = datetime(ts_config.start_year, 1, 1, tzinfo=ZoneInfo("Europe/Prague"))
            timespan = TimeSpanInvestment(
                start=start,
                intervals=ts_config.intervals,
                resolution=Resolution.HOUR_1,
            )
            expected_length = ts_config.intervals
        else:
            timespan = cast(
                TimeSpanInvestment,
                TimeSpanInvestment.for_years(
                    start_year=ts_config.start_year,
                    years=ts_config.years,
                    resolution=Resolution.HOUR_1,
                ),
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
            time_limit_seconds=min(solver_timeout, 3600),
            mip_gap=mip_gap,
            relax_binary_variables=True,
        )

        inv_params = None
        if scenario.investment_params:
            ip = scenario.investment_params
            if ip.project_lifetime_years:
                lifetime = ip.project_lifetime_years
            elif ts_config.intervals is not None:
                import math

                lifetime = max(1, math.ceil(ts_config.intervals / 8760))
            else:
                lifetime = ts_config.years
            inv_params = InvestmentParameters(
                discount_rate=ip.discount_rate,
                project_lifetime_years=lifetime,
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

    def find_by_job(self, job_id: str) -> Optional[Scenario]:
        """Return the scenario that submitted the given job, if any."""
        for scenario in self._scenarios.values():
            if job_id in scenario.jobs:
                return scenario
        return None

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
        sizing = []
        if props.get("power_sizing"):
            sizing.append("power sizing")
        if props.get("capacity_sizing"):
            sizing.append("energy sizing")
        sizing_str = f" + {' + '.join(sizing)}" if sizing else ""
        return f"{cap} MWh / {pwr} MW / {eff_str} eff{sizing_str}"

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

    elif dtype in ("photovoltaic_nonsteerable", "fixed_production", "fixed_consumption"):
        profile = props.get("power_profile", [])
        if isinstance(profile, list) and profile:
            return f"fixed, peak {max(profile):.1f} MW, {len(profile)} intervals"
        return "fixed power profile configured"

    elif dtype in ("photovoltaic_steerable", "max_power_production", "max_power_consumption"):
        profile = props.get("max_power_profile", [])
        rate = props.get("cost_per_mwh", props.get("value_per_mwh"))
        rate_str = f", {rate} EUR/MWh" if isinstance(rate, (int, float)) else ""
        if isinstance(profile, list) and profile:
            return f"steerable, peak {max(profile):.1f} MW, {len(profile)} intervals{rate_str}"
        return f"steerable max-power profile configured{rate_str}"

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
        reservation_str = ", capacity reservation" if props.get("capacity_reservation") else ""
        return f"max {max_imp} MW, {price_str}{reservation_str}"

    elif dtype == "cz_distribution_import":
        max_imp = props.get("max_import", "?")
        price_str = _price_summary(props.get("price"))
        reserved = props.get("reserved_capacity")
        reserved_str = "R=optimize" if reserved is None else f"R={reserved} MW"
        return f"max {max_imp} MW, {price_str}, monthly CZ tariff T1/T2, {reserved_str}"

    elif dtype in ("electricity_export", "heat_export"):
        max_exp = props.get("max_export", "?")
        price = props.get("price")
        price_str = _price_summary(price)
        reservation_str = ", capacity reservation" if props.get("capacity_reservation") else ""
        return f"max {max_exp} MW, {price_str}{reservation_str}"

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
