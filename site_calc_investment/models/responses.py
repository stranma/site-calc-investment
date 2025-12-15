"""Response models for investment client."""

from typing import Optional, List, Dict, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class Job(BaseModel):
    """Job status and metadata.

    Represents an asynchronous optimization job submitted to the API.
    """

    job_id: str = Field(..., description="Unique job identifier")
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = Field(
        ..., description="Job status"
    )
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    failed_at: Optional[datetime] = Field(None, description="Job failure timestamp")
    progress: Optional[int] = Field(None, ge=0, le=100, description="Progress percentage (optional)")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[Dict] = Field(None, description="Error details if failed")


class DeviceSchedule(BaseModel):
    """Optimized schedule for a single device.

    Contains flows (power/energy by material), state of charge (for storage),
    and any binary status indicators.
    """

    flows: Dict[str, List[float]] = Field(
        ..., description="Material flows keyed by material (e.g., 'electricity', 'gas', 'heat')"
    )
    soc: Optional[List[float]] = Field(None, description="State of charge (0-1) for storage devices")
    binary_status: Optional[List[int]] = Field(None, description="Binary on/off status (0/1) for CHP")


class GridFlows(BaseModel):
    """Grid import/export flows for a site."""

    import_flow: List[float] = Field(..., alias="import", description="MW imported from grid")
    export: List[float] = Field(..., description="MW exported to grid")

    class Config:
        populate_by_name = True


class SiteResult(BaseModel):
    """Optimization results for a single site."""

    device_schedules: Dict[str, DeviceSchedule] = Field(
        ..., description="Device schedules keyed by device name"
    )
    grid_flows: GridFlows = Field(..., description="Grid import/export flows")


class InvestmentMetrics(BaseModel):
    """Investment analysis metrics.

    Financial metrics calculated from the optimization results,
    including NPV, IRR, and payback period.
    """

    total_revenue_period: float = Field(..., description="Total revenue over planning horizon (EUR)")
    total_costs_period: float = Field(..., description="Total costs over planning horizon (EUR)")
    npv: Optional[float] = Field(None, description="Net present value (EUR)")
    irr: Optional[float] = Field(None, description="Internal rate of return (fraction, e.g., 0.12 = 12%)")
    payback_period_years: Optional[float] = Field(None, description="Simple payback period (years)")
    annual_revenue_by_year: Optional[List[float]] = Field(
        None, description="Annual revenue for each year"
    )
    annual_costs_by_year: Optional[List[float]] = Field(
        None, description="Annual costs for each year"
    )


class Summary(BaseModel):
    """Optimization summary with investment metrics."""

    total_da_revenue: Optional[float] = Field(None, description="Day-ahead market revenue (EUR)")
    total_cost: float = Field(..., description="Total operational costs (EUR)")
    expected_profit: float = Field(..., description="Expected profit (revenue - cost) (EUR)")
    solver_status: str = Field(..., description="Solver status (optimal, timeout, infeasible, etc.)")
    solve_time_seconds: float = Field(..., ge=0, description="Solver execution time")
    sites_count: int = Field(..., ge=1, description="Number of sites optimized")
    investment_metrics: Optional[InvestmentMetrics] = Field(
        None, description="Investment analysis metrics (if investment_parameters provided)"
    )


class InvestmentPlanningResponse(BaseModel):
    """Complete response for investment planning optimization.

    Contains optimized device schedules for all sites, grid flows,
    and financial analysis metrics.

    Example:
        >>> result = client.wait_for_completion(job_id)
        >>> print(f"NPV: €{result.summary.investment_metrics.npv:,.0f}")
        >>> print(f"IRR: {result.summary.investment_metrics.irr*100:.2f}%")
    """

    job_id: str = Field(..., description="Job identifier")
    status: Literal["completed"] = "completed"
    sites: Dict[str, SiteResult] = Field(..., description="Results keyed by site_id")
    summary: Summary = Field(..., description="Optimization summary and metrics")
