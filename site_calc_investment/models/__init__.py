"""Data models for investment client."""

from site_calc_investment.models.common import Location, Resolution, TimeSpan
from site_calc_investment.models.devices import (
    CHP,
    # Devices
    Battery,
    # Properties
    BatteryProperties,
    CHPProperties,
    DemandProperties,
    Device,
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
    DeviceSchedule,
    InvestmentMetrics,
    InvestmentPlanningResponse,
    Job,
    SiteResult,
    Summary,
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
