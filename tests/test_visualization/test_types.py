"""Tests for visualization types."""

from site_calc_investment.models.responses import InvestmentPlanningResponse
from site_calc_investment.visualization.types import (
    AggregationLevel,
    ChartSpec,
    DashboardData,
    DeviceFlowData,
    EnergyData,
    FinancialData,
    TimespanInfo,
)


class TestAggregationLevel:
    """Tests for AggregationLevel enum."""

    def test_has_four_values(self) -> None:
        assert len(AggregationLevel) == 4

    def test_values(self) -> None:
        assert AggregationLevel.HOURLY.value == "hourly"
        assert AggregationLevel.DAILY.value == "daily"
        assert AggregationLevel.WEEKLY.value == "weekly"
        assert AggregationLevel.MONTHLY.value == "monthly"


class TestTimespanInfo:
    """Tests for TimespanInfo dataclass."""

    def test_total_hours(self) -> None:
        ts = TimespanInfo(num_intervals=8760)
        assert ts.total_hours == 8760

    def test_num_years_one_year(self) -> None:
        ts = TimespanInfo(num_intervals=8760)
        assert ts.num_years == 1.0

    def test_num_years_ten_years(self) -> None:
        ts = TimespanInfo(num_intervals=87600)
        assert ts.num_years == 10.0

    def test_num_years_partial(self) -> None:
        ts = TimespanInfo(num_intervals=4380)
        assert ts.num_years == 0.5


class TestChartSpec:
    """Tests for ChartSpec dataclass."""

    def test_construction(self) -> None:
        spec = ChartSpec(
            traces=[{"x": [1, 2], "y": [3, 4], "type": "bar"}],
            layout={"title": "Test"},
            chart_id="test_chart",
        )
        assert len(spec.traces) == 1
        assert spec.layout["title"] == "Test"
        assert spec.chart_id == "test_chart"


class TestFinancialData:
    """Tests for FinancialData dataclass."""

    def test_defaults_are_none(self) -> None:
        fd = FinancialData()
        assert fd.npv is None
        assert fd.irr is None
        assert fd.payback_period_years is None
        assert fd.expected_profit is None

    def test_with_values(self) -> None:
        fd = FinancialData(npv=850000.0, irr=0.15, expected_profit=100000.0)
        assert fd.npv == 850000.0
        assert fd.irr == 0.15


class TestDeviceFlowData:
    """Tests for DeviceFlowData dataclass."""

    def test_without_soc(self) -> None:
        d = DeviceFlowData(name="PV1", flows={"electricity": [1.0, 2.0]})
        assert d.soc is None
        assert d.name == "PV1"

    def test_with_soc(self) -> None:
        d = DeviceFlowData(name="Bat1", flows={"electricity": [1.0]}, soc=[0.5])
        assert d.soc == [0.5]


class TestDashboardData:
    """Tests for DashboardData construction from response."""

    def test_from_response_with_metrics(self, response_1year: InvestmentPlanningResponse) -> None:
        data = DashboardData.from_response(response_1year)
        assert data.job_id == "viz_test_001"
        assert data.timespan.num_intervals == 8760
        assert data.has_investment_metrics is True
        assert data.financial.npv == 850000.0
        assert data.financial.irr == 0.15
        assert data.financial.payback_period_years == 4.5
        assert data.aggregation_level == AggregationLevel.DAILY

    def test_from_response_without_metrics(self, response_no_investment: InvestmentPlanningResponse) -> None:
        data = DashboardData.from_response(response_no_investment)
        assert data.has_investment_metrics is False
        assert data.financial.npv is None
        assert data.financial.irr is None
        assert data.financial.expected_profit == 100000.0

    def test_from_response_multi_device(self, response_multi_device: InvestmentPlanningResponse) -> None:
        data = DashboardData.from_response(response_multi_device)
        assert len(data.energy.devices) == 3
        device_names = {d.name for d in data.energy.devices}
        assert device_names == {"Battery1", "CHP1", "PV1"}

    def test_from_response_extracts_grid_flows(self, response_1year: InvestmentPlanningResponse) -> None:
        data = DashboardData.from_response(response_1year)
        assert data.energy.grid_import is not None
        assert data.energy.grid_export is not None
        assert len(data.energy.grid_import) == 8760

    def test_from_response_extracts_soc(self, response_1year: InvestmentPlanningResponse) -> None:
        data = DashboardData.from_response(response_1year)
        battery = next(d for d in data.energy.devices if d.name == "Battery1")
        assert battery.soc is not None
        assert len(battery.soc) == 8760

    def test_from_response_10year_aggregation(self, response_10year: InvestmentPlanningResponse) -> None:
        data = DashboardData.from_response(response_10year)
        assert data.aggregation_level == AggregationLevel.MONTHLY

    def test_from_response_short_aggregation(self, response_short: InvestmentPlanningResponse) -> None:
        data = DashboardData.from_response(response_short)
        assert data.aggregation_level == AggregationLevel.HOURLY
