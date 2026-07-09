"""Device models for investment client (NO ancillary services)."""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

# Device Properties Models


class BatteryProperties(BaseModel):
    """Battery storage properties."""

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
        """Validate profile values are non-negative."""
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
        """Validate profile values are non-negative."""
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
        """Validate profile values are non-negative."""
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
        """Validate profile values are non-negative."""
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
    """Market import device properties (electricity or gas)."""

    price: List[float] = Field(..., description="Price profile (EUR/MWh)")
    max_import: float = Field(..., gt=0, description="Maximum import capacity (MW)")
    max_import_unit_cost: Optional[float] = Field(
        None, ge=0, description="Optional reserved capacity cost (EUR/MW/year)"
    )


class MarketExportProperties(BaseModel):
    """Market export device properties (electricity or heat)."""

    price: List[float] = Field(..., description="Price profile (EUR/MWh)")
    max_export: float = Field(..., gt=0, description="Maximum export capacity (MW)")
    max_export_unit_cost: Optional[float] = Field(None, ge=0, description="Optional export capacity cost (EUR/MW/year)")


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


class Battery(BaseModel):
    """Battery storage device (NO ancillary services for investment client)."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["battery"] = "battery"
    properties: BatteryProperties
    schedule: Optional[Schedule] = None


class CHP(BaseModel):
    """Combined Heat and Power device.

    Note: is_binary is automatically relaxed to continuous for investment planning.
    """

    name: str = Field(..., description="Unique device identifier")
    type: Literal["chp"] = "chp"
    properties: CHPProperties
    schedule: Optional[Schedule] = None


class HeatAccumulator(BaseModel):
    """Heat accumulator (thermal storage) device."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["heat_accumulator"] = "heat_accumulator"
    properties: HeatAccumulatorProperties
    schedule: Optional[Schedule] = None


class PhotovoltaicNonSteerable(BaseModel):
    """Non-steerable photovoltaic system: produces exactly its power profile."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["photovoltaic_nonsteerable"] = "photovoltaic_nonsteerable"
    properties: FixedProfileProperties


class PhotovoltaicSteerable(BaseModel):
    """Steerable photovoltaic system: produces anywhere in [0, max_power_profile].

    The optimizer curtails output when it is unprofitable (e.g. negative prices).
    """

    name: str = Field(..., description="Unique device identifier")
    type: Literal["photovoltaic_steerable"] = "photovoltaic_steerable"
    properties: PhotovoltaicSteerableProperties


class FixedProduction(BaseModel):
    """Fixed production device: produces exactly its power profile."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["fixed_production"] = "fixed_production"
    properties: FixedProfileProperties


class MaxPowerProduction(BaseModel):
    """Steerable production device: produces in [0, max_power_profile] at a linear cost.

    The optimizer produces only when the electricity price exceeds cost_per_mwh.
    """

    name: str = Field(..., description="Unique device identifier")
    type: Literal["max_power_production"] = "max_power_production"
    properties: MaxPowerProductionProperties


class FixedConsumption(BaseModel):
    """Fixed consumption device: consumes exactly its power profile."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["fixed_consumption"] = "fixed_consumption"
    properties: FixedProfileProperties


class MaxPowerConsumption(BaseModel):
    """Steerable consumption device: consumes in [0, max_power_profile] at a linear value.

    The optimizer consumes only when the electricity price is below value_per_mwh.
    """

    name: str = Field(..., description="Unique device identifier")
    type: Literal["max_power_consumption"] = "max_power_consumption"
    properties: MaxPowerConsumptionProperties


class HeatDemand(BaseModel):
    """Heat demand device."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["heat_demand"] = "heat_demand"
    properties: DemandProperties


class ElectricityDemand(BaseModel):
    """Electricity demand device."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["electricity_demand"] = "electricity_demand"
    properties: DemandProperties


class ElectricityImport(BaseModel):
    """Electricity import (grid connection for buying)."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["electricity_import"] = "electricity_import"
    properties: MarketImportProperties


class ElectricityExport(BaseModel):
    """Electricity export (grid connection for selling)."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["electricity_export"] = "electricity_export"
    properties: MarketExportProperties


class GasImport(BaseModel):
    """Gas import (gas supply connection)."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["gas_import"] = "gas_import"
    properties: MarketImportProperties


class HeatExport(BaseModel):
    """Heat export (district heating connection)."""

    name: str = Field(..., description="Unique device identifier")
    type: Literal["heat_export"] = "heat_export"
    properties: MarketExportProperties


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
]
