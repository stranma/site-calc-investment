"""Data models for investment client."""

from site_calc_investment.models.common import TimeSpan, Resolution, Location
from site_calc_investment.models.devices import (
    # Properties
    BatteryProperties,
    CHPProperties,
    HeatAccumulatorProperties,
    PhotovoltaicProperties,
    DemandProperties,
    MarketImportProperties,
    MarketExportProperties,
    # Schedule
    Schedule,
    # Devices
    Battery,
    CHP,
    HeatAccumulator,
    Photovoltaic,
    HeatDemand,
    ElectricityDemand,
    ElectricityImport,
    ElectricityExport,
    GasImport,
    HeatExport,
    Device,
)
from site_calc_investment.models.requests import (
    Site,
    InvestmentParameters,
    OptimizationConfig,
    TimeSpanInvestment,
    InvestmentPlanningRequest,
)
from site_calc_investment.models.responses import (
    Job,
    DeviceSchedule,
    SiteResult,
    InvestmentMetrics,
    Summary,
    InvestmentPlanningResponse,
)

__all__ = [
    # Common
    "TimeSpan",
    "Resolution",
    "Location",
    # Device Properties
    "BatteryProperties",
    "CHPProperties",
    "HeatAccumulatorProperties",
    "PhotovoltaicProperties",
    "DemandProperties",
    "MarketImportProperties",
    "MarketExportProperties",
    # Schedule
    "Schedule",
    # Devices
    "Battery",
    "CHP",
    "HeatAccumulator",
    "Photovoltaic",
    "HeatDemand",
    "ElectricityDemand",
    "ElectricityImport",
    "ElectricityExport",
    "GasImport",
    "HeatExport",
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
    "SiteResult",
    "InvestmentMetrics",
    "Summary",
    "InvestmentPlanningResponse",
]
