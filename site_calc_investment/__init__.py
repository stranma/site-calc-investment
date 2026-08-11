"""Site-Calc Investment Client

Python client for long-term capacity planning and investment ROI analysis.
"""

__version__ = "1.4.0"

from site_calc_investment.analysis import (
    aggregate_annual,
    calculate_investment_metrics,
    calculate_irr,
    calculate_npv,
    calculate_payback_period,
    compare_scenarios,
)
from site_calc_investment.api.client import InvestmentClient
from site_calc_investment.exceptions import (
    ApiError,
    AuthenticationError,
    ForbiddenFeatureError,
    JobNotFoundError,
    LimitExceededError,
    OptimizationError,
    SiteCalcError,
    TimeoutError,
    ValidationError,
)
from site_calc_investment.models import (
    CHP,
    # Device models (NO ancillary_services)
    Battery,
    CapacityReservation,
    CapacityReservationResult,
    # Capacity reservations and investment accounting
    CapacityTariff,
    CzDistributionImport,
    DeviceInvestment,
    ElectricityDemand,
    ElectricityExport,
    ElectricityImport,
    FixedConsumption,
    FixedProduction,
    GasImport,
    HeatAccumulator,
    HeatDemand,
    HeatExport,
    InvestmentMetrics,
    InvestmentParameters,
    # Request models
    InvestmentPlanningRequest,
    InvestmentPlanningResponse,
    # Response models
    Job,
    Location,
    MaxPowerConsumption,
    MaxPowerProduction,
    OptimizationConfig,
    PhotovoltaicNonSteerable,
    PhotovoltaicSteerable,
    ReservationPeriod,
    Resolution,
    Schedule,
    # Site and configuration
    Site,
    # Core models
    TimeSpan,
)

__all__ = [
    # Client
    "InvestmentClient",
    # Core
    "TimeSpan",
    "Resolution",
    "Location",
    # Devices
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
    # Capacity reservations and investment accounting
    "CapacityTariff",
    "CapacityReservation",
    "DeviceInvestment",
    # Configuration
    "Site",
    "Schedule",
    "InvestmentParameters",
    "OptimizationConfig",
    # Requests/Responses
    "InvestmentPlanningRequest",
    "Job",
    "InvestmentPlanningResponse",
    "InvestmentMetrics",
    "ReservationPeriod",
    "CapacityReservationResult",
    # Analysis
    "calculate_npv",
    "calculate_irr",
    "calculate_payback_period",
    "calculate_investment_metrics",
    "aggregate_annual",
    "compare_scenarios",
    # Exceptions
    "SiteCalcError",
    "ApiError",
    "ValidationError",
    "AuthenticationError",
    "ForbiddenFeatureError",
    "LimitExceededError",
    "TimeoutError",
    "OptimizationError",
    "JobNotFoundError",
]
