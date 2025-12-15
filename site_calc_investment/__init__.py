"""Site-Calc Investment Client

Python client for long-term capacity planning and investment ROI analysis.
"""

from site_calc_investment.api.client import InvestmentClient
from site_calc_investment.models import (
    # Core models
    TimeSpan,
    Resolution,
    Location,
    # Device models (NO ancillary_services)
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
    # Site and configuration
    Site,
    Schedule,
    InvestmentParameters,
    OptimizationConfig,
    # Request models
    InvestmentPlanningRequest,
    # Response models
    Job,
    InvestmentPlanningResponse,
    InvestmentMetrics,
)
from site_calc_investment.analysis import (
    calculate_npv,
    calculate_irr,
    calculate_payback_period,
    aggregate_annual,
    compare_scenarios,
)
from site_calc_investment.exceptions import (
    SiteCalcError,
    ApiError,
    ValidationError,
    AuthenticationError,
    ForbiddenFeatureError,
    LimitExceededError,
    TimeoutError,
    OptimizationError,
    JobNotFoundError,
)

__version__ = "1.0.0"
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
