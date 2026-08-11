"""Request models for investment client."""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from site_calc_investment.models.common import Resolution, TimeSpan
from site_calc_investment.models.devices import Device, device_to_wire


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
    """Global financial parameters for investment analysis.

    Per-device investment costs live on each device's ``investment``
    block; optimizer-priced capacity costs are expressed as sizing
    reservations on the devices themselves.
    """

    model_config = ConfigDict(extra="forbid")

    discount_rate: float = Field(..., ge=0, le=0.5, description="Annual discount rate for NPV (0-0.5, e.g., 0.05 = 5%)")
    project_lifetime_years: int = Field(..., ge=1, le=50, description="Project lifetime in years")


class OptimizationConfig(BaseModel):
    """Optimization configuration."""

    objective: Literal["maximize_profit", "minimize_cost", "maximize_self_consumption"] = Field(
        "maximize_profit", description="Optimization objective"
    )
    time_limit_seconds: int = Field(300, gt=0, le=3600, description="Solver timeout (max 60 minutes)")
    mip_gap: float = Field(
        0.01,
        ge=0.0,
        le=0.1,
        description=(
            "Relative MIP optimality gap the solver may stop at "
            "(0.01 = accept solutions proven within 1% of the optimum; "
            "0 = prove full optimality). Smaller gaps solve longer."
        ),
    )
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
        ...         project_lifetime_years=10,
        ...     ),
        ...     optimization_config=OptimizationConfig(
        ...         objective="maximize_profit",
        ...         time_limit_seconds=600,
        ...     )
        ... )
    """

    sites: List[Site] = Field(..., min_length=1, max_length=50, description="Sites to optimize (max 50)")
    timespan: TimeSpanInvestment = Field(..., description="Time period (1-hour resolution only)")
    investment_parameters: Optional[InvestmentParameters] = Field(
        None, description="Optional financial parameters for ROI calculation"
    )
    optimization_config: OptimizationConfig = Field(
        default=OptimizationConfig(),  # type: ignore[call-arg]
        description="Optimization configuration",
    )

    def model_dump_for_api(self) -> dict:
        """Convert to API format.

        Strips client-only fields (device ``investment`` blocks) and
        rewrites sugar devices to their generic wire form.

        Returns:
            Dictionary ready for JSON serialization and API submission
        """
        data = self.model_dump()
        # Convert timespan to API format
        data["timespan"] = self.timespan.to_api_dict()
        for site in data["sites"]:
            site["devices"] = [device_to_wire(d) for d in site["devices"]]
        return data
