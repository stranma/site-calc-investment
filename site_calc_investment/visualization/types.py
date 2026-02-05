"""Data types for the visualization module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from site_calc_investment.models.responses import InvestmentPlanningResponse


class AggregationLevel(Enum):
    """Time aggregation level for charts.

    Selected automatically based on the optimization horizon length.
    """

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class ChartSpec:
    """Plotly.js chart specification as plain Python dicts.

    Contains traces (data series) and layout configuration that map
    directly to Plotly.js JSON format.
    """

    traces: List[Dict[str, Any]]
    layout: Dict[str, Any]
    chart_id: str = ""


@dataclass
class TimespanInfo:
    """Information about the optimization time horizon."""

    num_intervals: int
    hours_per_interval: int = 1
    start_year: Optional[int] = None

    @property
    def total_hours(self) -> int:
        return self.num_intervals * self.hours_per_interval

    @property
    def num_years(self) -> float:
        return self.total_hours / 8760.0


@dataclass
class FinancialData:
    """Extracted financial data for chart building."""

    expected_profit: Optional[float] = None
    total_da_revenue: Optional[float] = None
    total_cost: Optional[float] = None
    npv: Optional[float] = None
    irr: Optional[float] = None
    payback_period_years: Optional[float] = None
    total_revenue: Optional[float] = None
    total_costs: Optional[float] = None
    annual_revenue_by_year: Optional[List[float]] = None
    annual_costs_by_year: Optional[List[float]] = None


@dataclass
class DeviceFlowData:
    """Flow and SOC data for a single device."""

    name: str
    flows: Dict[str, List[float]]
    soc: Optional[List[float]] = None


@dataclass
class EnergyData:
    """Extracted energy data for chart building."""

    devices: List[DeviceFlowData] = field(default_factory=list)
    grid_import: Optional[List[float]] = None
    grid_export: Optional[List[float]] = None


@dataclass
class DashboardData:
    """All data needed to build the dashboard, extracted from the API response.

    This is the intermediate representation between the raw API response
    and the chart builders.
    """

    job_id: str
    timespan: TimespanInfo
    financial: FinancialData
    energy: EnergyData
    aggregation_level: AggregationLevel
    has_investment_metrics: bool = False

    @classmethod
    def from_response(cls, response: InvestmentPlanningResponse) -> "DashboardData":
        """Build DashboardData from an InvestmentPlanningResponse.

        :param response: Completed optimization response.
        :returns: DashboardData ready for chart builders.
        """
        # Determine number of intervals from first device's first flow
        num_intervals = 0
        for site_result in response.sites.values():
            for schedule in site_result.device_schedules.values():
                for flow_values in schedule.flows.values():
                    num_intervals = len(flow_values)
                    break
                if num_intervals > 0:
                    break
            if num_intervals > 0:
                break

        timespan = TimespanInfo(num_intervals=num_intervals)

        # Extract financial data
        financial = FinancialData(
            expected_profit=response.summary.expected_profit,
            total_da_revenue=response.summary.total_da_revenue,
            total_cost=response.summary.total_cost,
        )

        has_investment = False
        if response.investment_metrics:
            has_investment = True
            metrics = response.investment_metrics
            financial.npv = metrics.npv
            financial.irr = metrics.irr
            financial.payback_period_years = metrics.payback_period_years
            financial.total_revenue = metrics.total_revenue_10y
            financial.total_costs = metrics.total_costs_10y
            financial.annual_revenue_by_year = metrics.annual_revenue_by_year
            financial.annual_costs_by_year = metrics.annual_costs_by_year

        # Extract energy data
        energy = EnergyData()
        for site_result in response.sites.values():
            for dev_name, schedule in site_result.device_schedules.items():
                device_flow = DeviceFlowData(
                    name=dev_name,
                    flows=dict(schedule.flows),
                    soc=list(schedule.soc) if schedule.soc else None,
                )
                energy.devices.append(device_flow)

            if site_result.grid_flows:
                if "import" in site_result.grid_flows:
                    site_import = list(site_result.grid_flows["import"])
                    if energy.grid_import is None:
                        energy.grid_import = site_import
                    else:
                        energy.grid_import = _sum_series(energy.grid_import, site_import)
                if "export" in site_result.grid_flows:
                    site_export = list(site_result.grid_flows["export"])
                    if energy.grid_export is None:
                        energy.grid_export = site_export
                    else:
                        energy.grid_export = _sum_series(energy.grid_export, site_export)

        from site_calc_investment.visualization.aggregation import detect_aggregation_level

        aggregation = detect_aggregation_level(num_intervals)

        return cls(
            job_id=response.job_id,
            timespan=timespan,
            financial=financial,
            energy=energy,
            aggregation_level=aggregation,
            has_investment_metrics=has_investment,
        )


def _sum_series(a: List[float], b: List[float]) -> List[float]:
    """Element-wise sum of two float lists, zero-padding the shorter one.

    :param a: First series.
    :param b: Second series.
    :returns: Element-wise sum with length equal to the longer input.
    """
    max_len = max(len(a), len(b))
    return [(a[i] if i < len(a) else 0.0) + (b[i] if i < len(b) else 0.0) for i in range(max_len)]
