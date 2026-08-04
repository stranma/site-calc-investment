"""Data models for investment client."""

from site_calc_investment.models.capacity import (
    CapacityReservation,
    CapacityTariff,
    DeviceInvestment,
)
from site_calc_investment.models.common import Location, Resolution, TimeSpan
from site_calc_investment.models.devices import (
    CHP,
    # Devices
    Battery,
    # Properties
    BatteryProperties,
    CHPProperties,
    CzDistributionImport,
    CzDistributionImportProperties,
    DemandProperties,
    Device,
    DeviceBase,
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
    # Schedule
    Schedule,
)
from site_calc_investment.models.requests import (
    InvestmentParameters,
    InvestmentPlanningRequest,
    OptimizationConfig,
    Site,
    TimeSpanInvestment,
)
from site_calc_investment.models.responses import (
    CapacityReservationResult,
    DeviceSchedule,
    InvestmentMetrics,
    InvestmentPlanningResponse,
    Job,
    ReservationPeriod,
    SiteResult,
    Summary,
)

__all__ = [
    # Common
    "TimeSpan",
    "Resolution",
    "Location",
    # Capacity reservations and investment accounting
    "CapacityTariff",
    "CapacityReservation",
    "DeviceInvestment",
    # Device Properties
    "BatteryProperties",
    "CHPProperties",
    "HeatAccumulatorProperties",
    "FixedProfileProperties",
    "MaxPowerConsumptionProperties",
    "MaxPowerProductionProperties",
    "PhotovoltaicSteerableProperties",
    "DemandProperties",
    "MarketImportProperties",
    "MarketExportProperties",
    "GasImportProperties",
    "HeatExportProperties",
    "CzDistributionImportProperties",
    # Schedule
    "Schedule",
    # Devices
    "DeviceBase",
    "Battery",
    "CHP",
    "HeatAccumulator",
    "PhotovoltaicNonSteerable",
    "PhotovoltaicSteerable",
    "FixedProduction",
    "MaxPowerProduction",
    "FixedConsumption",
    "MaxPowerConsumption",
    "HeatDemand",
    "ElectricityDemand",
    "ElectricityImport",
    "ElectricityExport",
    "GasImport",
    "HeatExport",
    "CzDistributionImport",
    "Device",
    # Request models
    "Site",
    "InvestmentParameters",
    "OptimizationConfig",
    "TimeSpanInvestment",
    "InvestmentPlanningRequest",
    # Response models
    "Job",
    "DeviceSchedule",
    "ReservationPeriod",
    "CapacityReservationResult",
    "SiteResult",
    "InvestmentMetrics",
    "Summary",
    "InvestmentPlanningResponse",
]
