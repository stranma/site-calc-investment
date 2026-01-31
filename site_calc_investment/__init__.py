"""Site-Calc Investment Client

Python client for long-term capacity planning and investment ROI analysis.
"""

__version__ = "1.0.0"

from site_calc_investment.analysis import (
    aggregate_annual,
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
    ElectricityDemand,
    ElectricityExport,
    ElectricityImport,
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
    OptimizationConfig,
    Photovoltaic,
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
    "Photovoltaic",
    "HeatDemand",
    "ElectricityDemand",
    "ElectricityImport",
    "ElectricityExport",
    "GasImport",
    "HeatExport",
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
    # Analysis
    "calculate_npv",
    "calculate_irr",
    "calculate_payback_period",
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
