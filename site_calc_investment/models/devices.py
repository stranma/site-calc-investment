"""Device models for investment client (NO ancillary services)."""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from site_calc_investment.models.capacity import CapacityReservation, CapacityTariff, DeviceInvestment

# Device Properties Models


class BatteryProperties(BaseModel):
    """Battery storage properties."""

    model_config = ConfigDict(extra="forbid")

    capacity: float = Field(..., gt=0, description="Energy capacity (MWh)")
    max_power: float = Field(..., gt=0, description="Power rating for charge/discharge (MW)")
    efficiency: float = Field(..., gt=0, le=1, description="Round-trip efficiency (0-1)")
    initial_soc: float = Field(0.5, ge=0, le=1, description="Initial state of charge (0-1)")
    soc_anchor_interval_hours: Optional[int] = Field(
        None,
        gt=0,
        description="If set, force SOC to target at regular intervals (hours). E.g., 4320 = every 6 months",
    )
    soc_anchor_target: float = Field(
        0.5,
        ge=0,
        le=1,
        description="Target SOC fraction at anchor points (0-1)",
    )
    power_sizing: Optional[CapacityReservation] = Field(
        None,
        description=(
            "Let the optimizer size installed power (MW). Use periods='horizon' with "
            "tariffs as investment cost tiers (EUR/MW); max_power is the sizing ceiling"
        ),
    )
    capacity_sizing: Optional[CapacityReservation] = Field(
        None,
        description=(
            "Let the optimizer size energy capacity (MWh); capacity is the sizing "
            "ceiling. The full reservation form is accepted (calendar periods, tariff "
            "menus, bounds, timezone); periods='horizon' with reserved_price tiers "
            "(EUR/MWh) is the one-shot CAPEX case. An optimizer-sized capacity must "
            "start empty: initial_soc defaults to 0 and must not be set above 0 "
            "unless 'reserved' fixes the capacity"
        ),
    )
    degradation_yearly: Optional[List[float]] = Field(
        None,
        description=(
            "Yearly capacity degradation curve in percent, e.g. [5, 3, 2] = 5% in "
            "year 1, 3% in year 2, 2% in every later year (the last entry repeats). "
            "The server caps the usable stored energy at capacity * prod(1 - d/100), "
            "each year's loss applied from the START of the year it occurs "
            "(conservative: year 1 already runs at 95% in the example; prepend 0 for "
            "an undegraded first year). Not combinable with SOC anchor points or an "
            "optimizer-sized capacity_sizing (a fixed 'reserved' capacity is fine)."
        ),
    )

    @model_validator(mode="after")
    def validate_degradation(self) -> "BatteryProperties":
        """Mirror the server's rules for the degradation curve."""
        curve = self.degradation_yearly
        if curve is not None:
            if len(curve) == 0:
                raise ValueError("degradation_yearly must not be empty")
            if any(not 0 <= d < 100 for d in curve):
                raise ValueError(f"degradation_yearly values must be in [0, 100), got {curve}")
            if self.soc_anchor_interval_hours is not None:
                raise ValueError(
                    "degradation_yearly cannot be combined with SOC anchor points (soc_anchor_interval_hours)"
                )
            if self.capacity_sizing is not None and self.capacity_sizing.reserved is None:
                raise ValueError(
                    "degradation_yearly cannot be combined with an optimizer-sized "
                    "capacity_sizing (the degraded ceiling is absolute MWh and may "
                    "exceed the built energy); fix the reserved capacity or drop the curve"
                )
        return self

    @model_validator(mode="after")
    def validate_capacity_sizing(self) -> "BatteryProperties":
        """Enforce the server's rules for capacity_sizing.

        An optimizer-sized energy capacity must start empty: every built
        MWh would otherwise arrive holding ``initial_soc`` MWh of free
        energy, distorting the sizing. When ``initial_soc`` is not set
        explicitly, sizing runs default it to 0 (the stock 0.5 default
        only makes sense for a fixed capacity). SOC anchor points are
        incompatible with capacity_sizing (anchors target a fraction of
        the ceiling, which may exceed the built capacity).
        """
        cs = self.capacity_sizing
        if cs is not None:
            if self.soc_anchor_interval_hours is not None:
                raise ValueError(
                    "capacity_sizing cannot be combined with SOC anchor points (soc_anchor_interval_hours)"
                )
            if cs.reserved is None:
                if "initial_soc" not in self.model_fields_set:
                    self.initial_soc = 0.0
                elif self.initial_soc > 0:
                    raise ValueError(
                        "initial_soc > 0 cannot be combined with an optimizer-sized "
                        "capacity_sizing (no fixed 'reserved' value); use initial_soc=0 "
                        "or fix the reserved capacity"
                    )
        return self


class CHPProperties(BaseModel):
    """Combined Heat and Power properties."""

    gas_input: float = Field(..., gt=0, description="Gas consumption at full load (MW)")
    el_output: float = Field(..., gt=0, description="Electricity generation at full load (MW)")
    heat_output: float = Field(..., gt=0, description="Heat generation at full load (MW)")
    is_binary: bool = Field(False, description="True=on/off only (relaxed for investment), False=modulating")
    min_power: Optional[float] = Field(None, ge=0, le=1, description="Min power fraction if modulation limited")


class HeatAccumulatorProperties(BaseModel):
    """Heat accumulator (thermal storage) properties."""

    capacity: float = Field(..., gt=0, description="Thermal energy capacity (MWh)")
    max_power: float = Field(..., gt=0, description="Charge/discharge power (MW)")
    efficiency: float = Field(..., gt=0, le=1, description="Storage efficiency (0-1)")
    initial_soc: float = Field(0.5, ge=0, le=1, description="Initial state of charge (0-1)")
    loss_rate: float = Field(0.001, ge=0, description="Standing losses (fraction/hour)")


class FixedProfileProperties(BaseModel):
    """Fixed power profile properties (production or consumption follows it exactly)."""

    power_profile: List[float] = Field(..., description="Exact power profile (MW per interval)")

    @field_validator("power_profile")
    @classmethod
    def validate_non_negative(cls, v: List[float]) -> List[float]:
        """Validate profile is non-empty with non-negative values."""
        if not v:
            raise ValueError("power_profile must not be empty")
        if not all(val >= 0 for val in v):
            raise ValueError("power_profile values must be non-negative")
        return v


class MaxPowerConsumptionProperties(BaseModel):
    """Steerable consumption properties: runs anywhere in [0, max_power_profile]."""

    max_power_profile: List[float] = Field(..., description="Maximum power profile (MW per interval)")
    value_per_mwh: float = Field(..., ge=0, description="Value earned per MWh consumed (EUR/MWh)")

    @field_validator("max_power_profile")
    @classmethod
    def validate_non_negative(cls, v: List[float]) -> List[float]:
        """Validate profile is non-empty with non-negative values."""
        if not v:
            raise ValueError("max_power_profile must not be empty")
        if not all(val >= 0 for val in v):
            raise ValueError("max_power_profile values must be non-negative")
        return v


class MaxPowerProductionProperties(BaseModel):
    """Steerable production properties: runs anywhere in [0, max_power_profile]."""

    max_power_profile: List[float] = Field(..., description="Maximum power profile (MW per interval)")
    cost_per_mwh: float = Field(0, ge=0, description="Variable production cost (EUR/MWh), 0 = free")

    @field_validator("max_power_profile")
    @classmethod
    def validate_non_negative(cls, v: List[float]) -> List[float]:
        """Validate profile is non-empty with non-negative values."""
        if not v:
            raise ValueError("max_power_profile must not be empty")
        if not all(val >= 0 for val in v):
            raise ValueError("max_power_profile values must be non-negative")
        return v


class PhotovoltaicSteerableProperties(BaseModel):
    """Steerable (curtailable) photovoltaic properties."""

    max_power_profile: List[float] = Field(
        ..., description="Maximum available PV power per interval (MW), e.g. from a weather forecast"
    )

    @field_validator("max_power_profile")
    @classmethod
    def validate_non_negative(cls, v: List[float]) -> List[float]:
        """Validate profile is non-empty with non-negative values."""
        if not v:
            raise ValueError("max_power_profile must not be empty")
        if not all(val >= 0 for val in v):
            raise ValueError("max_power_profile values must be non-negative")
        return v


class DemandProperties(BaseModel):
    """Demand properties (heat or electricity)."""

    max_demand_profile: List[float] = Field(..., description="Maximum demand profile (MW, not MWh!)")
    min_demand_profile: Union[List[float], float] = Field(
        0, description="Minimum demand profile (MW) or constant value"
    )

    @field_validator("max_demand_profile", "min_demand_profile")
    @classmethod
    def validate_positive(cls, v: Union[List[float], float]) -> Union[List[float], float]:
        """Validate demand values are non-negative."""
        if isinstance(v, list):
            if not all(val >= 0 for val in v):
                raise ValueError("Demand values must be non-negative")
        elif isinstance(v, (int, float)):
            if v < 0:
                raise ValueError("Demand value must be non-negative")
        return v


class MarketImportProperties(BaseModel):
    """Electricity import device properties."""

    model_config = ConfigDict(extra="forbid")

    price: List[float] = Field(..., description="Price profile (EUR/MWh)")
    max_import: float = Field(..., gt=0, description="Maximum import capacity (MW)")
    capacity_reservation: Optional[CapacityReservation] = Field(
        None, description="Optional per-period capacity limit and charge on the import flow"
    )


class MarketExportProperties(BaseModel):
    """Electricity export device properties."""

    model_config = ConfigDict(extra="forbid")

    price: List[float] = Field(..., description="Price profile (EUR/MWh)")
    max_export: float = Field(..., gt=0, description="Maximum export capacity (MW)")
    capacity_reservation: Optional[CapacityReservation] = Field(
        None, description="Optional per-period capacity limit and charge on the export flow"
    )


class GasImportProperties(BaseModel):
    """Gas import device properties."""

    model_config = ConfigDict(extra="forbid")

    price: List[float] = Field(..., description="Price profile (EUR/MWh)")
    max_import: float = Field(..., gt=0, description="Maximum import capacity (MW)")


class HeatExportProperties(BaseModel):
    """Heat export device properties."""

    model_config = ConfigDict(extra="forbid")

    price: List[float] = Field(..., description="Price profile (EUR/MWh)")
    max_export: float = Field(..., gt=0, description="Maximum export capacity (MW)")


class CzDistributionImportProperties(BaseModel):
    """Czech distribution-tariff electricity import (2027 tariff structure).

    Monthly billing with two tariffs T1/T2; each month is billed by
    whichever tariff is cheaper (automatic assignment). The reserved
    capacity is either contracted (``reserved_capacity`` set) or sized by
    the optimizer. All prices are user-supplied.
    """

    model_config = ConfigDict(extra="forbid")

    price: List[float] = Field(
        ..., description="Energy price profile (EUR/MWh): commodity plus regulated per-MWh components"
    )
    max_import: float = Field(..., gt=0, description="Physical connection limit (MW)")
    t1_reserved_price: float = Field(..., ge=0, description="T1: EUR per MW of reserved capacity per month")
    t1_peak_price: float = Field(..., ge=0, description="T1: EUR per MW of the monthly peak")
    t2_reserved_price: float = Field(..., ge=0, description="T2: EUR per MW of reserved capacity per month")
    t2_peak_price: float = Field(..., ge=0, description="T2: EUR per MW of the monthly peak")
    reserved_capacity: Optional[float] = Field(
        None, ge=0, description="Contracted reserved capacity (MW); None lets the optimizer size it"
    )
    min_reserved: float = Field(0.0, ge=0, description="Lower bound for an optimized reserved capacity (MW)")
    max_reserved: Optional[float] = Field(
        None, gt=0, description="Upper bound for an optimized reserved capacity (MW); defaults to max_import"
    )
    timezone: str = Field("Europe/Prague", description="IANA billing timezone")

    def to_capacity_reservation(self) -> CapacityReservation:
        """Build the equivalent generic capacity reservation (monthly, T1/T2 menu)."""
        return CapacityReservation(
            periods="calendar_month",
            tariffs=[
                CapacityTariff(
                    name="T1",
                    reserved_price=self.t1_reserved_price,
                    peak_price=self.t1_peak_price,
                    fixed_price=0.0,
                ),
                CapacityTariff(
                    name="T2",
                    reserved_price=self.t2_reserved_price,
                    peak_price=self.t2_peak_price,
                    fixed_price=0.0,
                ),
            ],
            reserved=self.reserved_capacity,
            min_reserved=self.min_reserved,
            max_reserved=self.max_reserved,
            timezone=self.timezone,
        )

    @model_validator(mode="after")
    def validate_tariff_consistency(self) -> "CzDistributionImportProperties":
        """Run the full reservation validation on the equivalent generic form."""
        self.to_capacity_reservation()
        return self


# Schedule Model


class Schedule(BaseModel):
    """Operational schedule constraints.

    Defines when and how a device can operate with runtime constraints
    and binary availability arrays.
    """

    # Runtime constraints
    min_continuous_run_hours: Optional[float] = Field(None, ge=0, description="Minimum runtime once started")
    max_continuous_run_hours: Optional[float] = Field(None, ge=0, description="Maximum continuous operation")
    max_hours_per_day: Optional[float] = Field(None, ge=0, le=24, description="Total hours per day")
    max_starts_per_day: Optional[int] = Field(None, ge=0, description="Maximum number of startups")
    min_downtime_hours: Optional[float] = Field(None, ge=0, description="Minimum off time between runs")

    # Binary availability arrays
    can_run: Optional[List[Union[int, float]]] = Field(
        None, description="0=cannot run, 1=can run (or fractional availability)"
    )
    must_run: Optional[List[int]] = Field(None, description="1=must run")

    # Power ranges when must_run=1
    min_power: Optional[List[float]] = Field(None, description="Minimum power when must_run=1 (MW)")
    max_power: Optional[List[float]] = Field(None, description="Maximum power when must_run=1 (MW)")

    @field_validator("can_run")
    @classmethod
    def validate_can_run(cls, v: Optional[List[Union[int, float]]]) -> Optional[List[Union[int, float]]]:
        """Validate can_run array."""
        if v is not None:
            if len(v) not in [24, 96]:
                raise ValueError("can_run array length must be 24 (1-hour) or 96 (15-min)")
            # Allow fractional values for PV, but validate range
            if not all(0 <= val <= 1 for val in v):
                raise ValueError("can_run values must be between 0 and 1")
        return v

    @field_validator("must_run")
    @classmethod
    def validate_must_run(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        """Validate must_run is binary."""
        if v is not None:
            if len(v) not in [24, 96]:
                raise ValueError("must_run array length must be 24 (1-hour) or 96 (15-min)")
            if not all(val in [0, 1] for val in v):
                raise ValueError("must_run must contain only 0 or 1")
        return v


# Device Models


class DeviceBase(BaseModel):
    """Common device fields: identity and client-side investment accounting."""

    name: str = Field(..., description="Unique device identifier")
    investment: Optional[DeviceInvestment] = Field(
        None,
        description="Fixed CAPEX/OPEX for client-side NPV analysis; stripped from the API payload",
    )


class Battery(DeviceBase):
    """Battery storage device (NO ancillary services for investment client)."""

    type: Literal["battery"] = "battery"
    properties: BatteryProperties
    schedule: Optional[Schedule] = None


class CHP(DeviceBase):
    """Combined Heat and Power device.

    Note: is_binary is automatically relaxed to continuous for investment planning.
    """

    type: Literal["chp"] = "chp"
    properties: CHPProperties
    schedule: Optional[Schedule] = None


class HeatAccumulator(DeviceBase):
    """Heat accumulator (thermal storage) device."""

    type: Literal["heat_accumulator"] = "heat_accumulator"
    properties: HeatAccumulatorProperties
    schedule: Optional[Schedule] = None


class PhotovoltaicNonSteerable(DeviceBase):
    """Non-steerable photovoltaic system: produces exactly its power profile."""

    type: Literal["photovoltaic_nonsteerable"] = "photovoltaic_nonsteerable"
    properties: FixedProfileProperties


class PhotovoltaicSteerable(DeviceBase):
    """Steerable photovoltaic system: produces anywhere in [0, max_power_profile].

    The optimizer curtails output when it is unprofitable (e.g. negative prices).
    """

    type: Literal["photovoltaic_steerable"] = "photovoltaic_steerable"
    properties: PhotovoltaicSteerableProperties


class FixedProduction(DeviceBase):
    """Fixed production device: produces exactly its power profile."""

    type: Literal["fixed_production"] = "fixed_production"
    properties: FixedProfileProperties


class MaxPowerProduction(DeviceBase):
    """Steerable production device: produces in [0, max_power_profile] at a linear cost.

    The optimizer produces only when the electricity price exceeds cost_per_mwh.
    """

    type: Literal["max_power_production"] = "max_power_production"
    properties: MaxPowerProductionProperties


class FixedConsumption(DeviceBase):
    """Fixed consumption device: consumes exactly its power profile."""

    type: Literal["fixed_consumption"] = "fixed_consumption"
    properties: FixedProfileProperties


class MaxPowerConsumption(DeviceBase):
    """Steerable consumption device: consumes in [0, max_power_profile] at a linear value.

    The optimizer consumes only when the electricity price is below value_per_mwh.
    """

    type: Literal["max_power_consumption"] = "max_power_consumption"
    properties: MaxPowerConsumptionProperties


class HeatDemand(DeviceBase):
    """Heat demand device."""

    type: Literal["heat_demand"] = "heat_demand"
    properties: DemandProperties


class ElectricityDemand(DeviceBase):
    """Electricity demand device."""

    type: Literal["electricity_demand"] = "electricity_demand"
    properties: DemandProperties


class ElectricityImport(DeviceBase):
    """Electricity import (grid connection for buying)."""

    type: Literal["electricity_import"] = "electricity_import"
    properties: MarketImportProperties


class ElectricityExport(DeviceBase):
    """Electricity export (grid connection for selling)."""

    type: Literal["electricity_export"] = "electricity_export"
    properties: MarketExportProperties


class GasImport(DeviceBase):
    """Gas import (gas supply connection)."""

    type: Literal["gas_import"] = "gas_import"
    properties: GasImportProperties


class HeatExport(DeviceBase):
    """Heat export (district heating connection)."""

    type: Literal["heat_export"] = "heat_export"
    properties: HeatExportProperties


class CzDistributionImport(DeviceBase):
    """Electricity import billed under the Czech distribution capacity tariff.

    Sent to the API as a plain electricity import with a monthly capacity
    reservation carrying the T1/T2 price menu.
    """

    type: Literal["cz_distribution_import"] = "cz_distribution_import"
    properties: CzDistributionImportProperties


# Union type for all devices
Device = Union[
    Battery,
    CHP,
    HeatAccumulator,
    PhotovoltaicNonSteerable,
    PhotovoltaicSteerable,
    FixedProduction,
    MaxPowerProduction,
    FixedConsumption,
    MaxPowerConsumption,
    HeatDemand,
    ElectricityDemand,
    ElectricityImport,
    ElectricityExport,
    GasImport,
    HeatExport,
    CzDistributionImport,
]


def device_to_wire(device: Dict[str, Any]) -> Dict[str, Any]:
    """Convert one dumped device dict to its API wire form.

    Strips the client-only ``investment`` block and rewrites the Czech
    distribution-tariff sugar device into a plain electricity import with
    the equivalent monthly capacity reservation.
    """
    device = dict(device)
    device.pop("investment", None)
    if device.get("type") == "cz_distribution_import":
        p = device["properties"]
        # Single source of truth for the T1/T2 -> reservation mapping:
        # rebuild the properties model and reuse its own conversion.
        reservation = CzDistributionImportProperties.model_validate(p).to_capacity_reservation()
        device = {
            "name": device["name"],
            "type": "electricity_import",
            "properties": {
                "price": p["price"],
                "max_import": p["max_import"],
                "capacity_reservation": reservation.model_dump(),
            },
        }
    return device
