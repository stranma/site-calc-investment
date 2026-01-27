"""Request models for investment client."""

from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field, field_validator

from site_calc_investment.models.common import TimeSpan, Resolution
from site_calc_investment.models.devices import Device


class Site(BaseModel):
    """Site definition with devices.

    A site represents a physical location with multiple devices
    that are optimized together.
    """

    site_id: str = Field(..., description="Unique site identifier")
    description: Optional[str] = Field(None, description="Optional site description")
    devices: List[Device] = Field(..., min_length=1, description="List of devices at this site")

    @field_validator("devices")
    @classmethod
    def validate_unique_names(cls, v: List[Device]) -> List[Device]:
        """Ensure all device names are unique within a site."""
        names = [d.name for d in v]
        if len(names) != len(set(names)):
            raise ValueError("Device names must be unique within a site")
        return v


class InvestmentParameters(BaseModel):
    """Financial parameters for investment analysis.

    These parameters are used to calculate NPV, IRR, and other
    investment metrics.
    """

    discount_rate: float = Field(..., ge=0, le=0.5, description="Annual discount rate for NPV (0-0.5, e.g., 0.05 = 5%)")
    project_lifetime_years: int = Field(..., ge=1, le=50, description="Project lifetime in years")
    investment_budget: Optional[float] = Field(None, ge=0, description="Maximum investment budget in EUR")
    carbon_price: Optional[float] = Field(None, ge=0, description="Carbon price in EUR/tCO2")
    device_capital_costs: Optional[Dict[str, float]] = Field(
        None, description="CAPEX for each device (EUR), keyed by device name"
    )
    device_annual_opex: Optional[Dict[str, float]] = Field(
        None, description="Annual O&M costs (EUR/year), keyed by device name"
    )
    price_escalation_rate: Optional[float] = Field(
        None, ge=0, le=1, description="Annual price escalation rate (e.g., 0.02 = 2%)"
    )


class OptimizationConfig(BaseModel):
    """Optimization configuration."""

    objective: Literal["maximize_profit", "minimize_cost", "maximize_self_consumption"] = Field(
        "maximize_profit", description="Optimization objective"
    )
    time_limit_seconds: int = Field(3600, gt=0, le=3600, description="Solver timeout (max 1 hour)")
    relax_binary_variables: bool = Field(
        True, description="Relax binary CHP variables to continuous (recommended for long horizons)"
    )


class TimeSpanInvestment(TimeSpan):
    """TimeSpan with investment client validation.

    Investment clients:
    - Only support 1-hour resolution
    - Maximum 100,000 intervals
    """

    resolution: Literal[Resolution.HOUR_1] = Resolution.HOUR_1  # type: ignore

    @field_validator("intervals")
    @classmethod
    def validate_max_intervals(cls, v: int) -> int:
        """Investment client limited to 100,000 intervals."""
        if v > 100_000:
            raise ValueError("Investment client limited to 100,000 intervals (~11 years)")
        return v

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: Resolution) -> Resolution:
        """Investment client only supports 1-hour resolution."""
        if v != Resolution.HOUR_1:
            raise ValueError("Investment client only supports 1-hour resolution")
        return v


class InvestmentPlanningRequest(BaseModel):
    """Request for long-term investment planning optimization.

    This request creates a device planning job for capacity sizing
    and investment ROI analysis over multi-year horizons.

    Example:
        >>> request = InvestmentPlanningRequest(
        ...     sites=[site],
        ...     timespan=TimeSpanInvestment.for_years(2025, 10),
        ...     investment_parameters=InvestmentParameters(
        ...         discount_rate=0.05,
        ...         device_capital_costs={"Battery1": 500000}
        ...     ),
        ...     optimization_config=OptimizationConfig(
        ...         objective="maximize_npv",
        ...         time_limit_seconds=3600
        ...     )
        ... )
    """

    sites: List[Site] = Field(..., min_length=1, max_length=50, description="Sites to optimize (max 50)")
    timespan: TimeSpanInvestment = Field(..., description="Time period (1-hour resolution only)")
    investment_parameters: Optional[InvestmentParameters] = Field(
        None, description="Optional financial parameters for ROI calculation"
    )
    optimization_config: OptimizationConfig = Field(
        default_factory=OptimizationConfig, description="Optimization configuration"
    )

    def model_dump_for_api(self) -> dict:
        """Convert to API format.

        Returns:
            Dictionary ready for JSON serialization and API submission
        """
        data = self.model_dump()
        # Convert timespan to API format
        data["timespan"] = self.timespan.to_api_dict()
        return data
