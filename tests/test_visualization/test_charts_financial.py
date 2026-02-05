"""Tests for financial chart builders."""

from site_calc_investment.visualization.charts.financial import (
    build_annual_revenue_costs_chart,
    build_cumulative_cash_flow_chart,
    build_kpi_cards,
)
from site_calc_investment.visualization.types import FinancialData


class TestBuildKpiCards:
    """Tests for build_kpi_cards()."""

    def test_with_full_investment_metrics(self) -> None:
        fd = FinancialData(
            npv=850000.0,
            irr=0.15,
            payback_period_years=4.5,
            expected_profit=100000.0,
        )
        cards = build_kpi_cards(fd)
        assert len(cards) == 4

    def test_kpi_labels(self) -> None:
        fd = FinancialData(
            npv=850000.0,
            irr=0.15,
            payback_period_years=4.5,
            expected_profit=100000.0,
        )
        cards = build_kpi_cards(fd)
        labels = [c["label"] for c in cards]
        assert "Net Present Value" in labels
        assert "Internal Rate of Return" in labels
        assert "Payback Period" in labels
        assert "Total Profit" in labels

    def test_npv_formatting(self) -> None:
        fd = FinancialData(npv=850000.0, expected_profit=100000.0)
        cards = build_kpi_cards(fd)
        npv_card = next(c for c in cards if c["label"] == "Net Present Value")
        assert npv_card["value"] == 850000.0
        assert "850,000" in npv_card["formatted_value"]

    def test_irr_formatting(self) -> None:
        fd = FinancialData(irr=0.15, expected_profit=100000.0)
        cards = build_kpi_cards(fd)
        irr_card = next(c for c in cards if c["label"] == "Internal Rate of Return")
        assert irr_card["formatted_value"] == "15.0%"

    def test_payback_formatting(self) -> None:
        fd = FinancialData(payback_period_years=4.5, expected_profit=100000.0)
        cards = build_kpi_cards(fd)
        payback_card = next(c for c in cards if c["label"] == "Payback Period")
        assert payback_card["formatted_value"] == "4.5 years"

    def test_without_investment_metrics_profit_only(self) -> None:
        fd = FinancialData(expected_profit=100000.0)
        cards = build_kpi_cards(fd)
        assert len(cards) == 1
        assert cards[0]["label"] == "Total Profit"
        assert cards[0]["value"] == 100000.0

    def test_empty_financial_data(self) -> None:
        fd = FinancialData()
        cards = build_kpi_cards(fd)
        assert len(cards) == 0


class TestBuildAnnualRevenueCostsChart:
    """Tests for build_annual_revenue_costs_chart()."""

    def test_returns_chart_spec(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[142500.0] * 10,
            annual_costs_by_year=[42500.0] * 10,
        )
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is not None
        assert spec.chart_id == "annual_revenue_costs"

    def test_has_two_traces(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[142500.0] * 10,
            annual_costs_by_year=[42500.0] * 10,
        )
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is not None
        assert len(spec.traces) == 2

    def test_trace_names(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[142500.0] * 5,
            annual_costs_by_year=[42500.0] * 5,
        )
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is not None
        names = [t["name"] for t in spec.traces]
        assert "Revenue" in names
        assert "Costs" in names

    def test_trace_data_values(self) -> None:
        revenues = [100000.0, 110000.0, 120000.0]
        costs = [30000.0, 35000.0, 40000.0]
        fd = FinancialData(
            annual_revenue_by_year=revenues,
            annual_costs_by_year=costs,
        )
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is not None
        revenue_trace = next(t for t in spec.traces if t["name"] == "Revenue")
        costs_trace = next(t for t in spec.traces if t["name"] == "Costs")
        assert revenue_trace["y"] == revenues
        assert costs_trace["y"] == costs

    def test_bar_type(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0],
            annual_costs_by_year=[30000.0],
        )
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is not None
        for trace in spec.traces:
            assert trace["type"] == "bar"

    def test_grouped_barmode(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0],
            annual_costs_by_year=[30000.0],
        )
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is not None
        assert spec.layout["barmode"] == "group"

    def test_returns_none_without_data(self) -> None:
        fd = FinancialData()
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is None

    def test_returns_none_with_partial_data(self) -> None:
        fd = FinancialData(annual_revenue_by_year=[100000.0])
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is None

    def test_returns_none_with_mismatched_lengths(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 5,
            annual_costs_by_year=[30000.0] * 3,
        )
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is None

    def test_year_labels(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 3,
            annual_costs_by_year=[30000.0] * 3,
        )
        spec = build_annual_revenue_costs_chart(fd)
        assert spec is not None
        assert spec.traces[0]["x"] == ["Year 1", "Year 2", "Year 3"]


class TestBuildCumulativeCashFlowChart:
    """Tests for build_cumulative_cash_flow_chart()."""

    def test_returns_chart_spec(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[142500.0] * 10,
            annual_costs_by_year=[42500.0] * 10,
        )
        spec = build_cumulative_cash_flow_chart(fd)
        assert spec is not None
        assert spec.chart_id == "cumulative_cash_flow"

    def test_cumulative_starts_at_initial_investment(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 5,
            annual_costs_by_year=[40000.0] * 5,
        )
        spec = build_cumulative_cash_flow_chart(fd, initial_investment=-500000.0)
        assert spec is not None
        cash_flow_trace = spec.traces[0]
        assert cash_flow_trace["y"][0] == -500000.0

    def test_cumulative_increases_over_time(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 5,
            annual_costs_by_year=[40000.0] * 5,
        )
        spec = build_cumulative_cash_flow_chart(fd, initial_investment=-500000.0)
        assert spec is not None
        cash_flow_trace = spec.traces[0]
        y = cash_flow_trace["y"]
        # Each year adds 60k (100k - 40k)
        assert y[0] == -500000.0
        assert y[1] == -440000.0
        assert y[2] == -380000.0

    def test_payback_annotation_present(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 10,
            annual_costs_by_year=[40000.0] * 10,
            payback_period_years=4.5,
        )
        spec = build_cumulative_cash_flow_chart(fd)
        assert spec is not None
        annotations = spec.layout.get("annotations", [])
        assert len(annotations) > 0
        assert "4.5" in annotations[0]["text"]

    def test_payback_vertical_line(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 10,
            annual_costs_by_year=[40000.0] * 10,
            payback_period_years=4.5,
        )
        spec = build_cumulative_cash_flow_chart(fd)
        assert spec is not None
        shapes = spec.layout.get("shapes", [])
        assert len(shapes) == 1
        assert shapes[0]["x0"] == 4.5

    def test_no_payback_annotation_when_none(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 5,
            annual_costs_by_year=[40000.0] * 5,
        )
        spec = build_cumulative_cash_flow_chart(fd)
        assert spec is not None
        annotations = spec.layout.get("annotations", [])
        assert len(annotations) == 0
        assert "shapes" not in spec.layout

    def test_returns_none_without_data(self) -> None:
        fd = FinancialData()
        spec = build_cumulative_cash_flow_chart(fd)
        assert spec is None

    def test_returns_none_with_mismatched_lengths(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 5,
            annual_costs_by_year=[40000.0] * 3,
        )
        spec = build_cumulative_cash_flow_chart(fd)
        assert spec is None

    def test_line_type(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 3,
            annual_costs_by_year=[40000.0] * 3,
        )
        spec = build_cumulative_cash_flow_chart(fd)
        assert spec is not None
        assert spec.traces[0]["type"] == "scatter"
        assert "lines" in spec.traces[0]["mode"]

    def test_zero_initial_investment(self) -> None:
        fd = FinancialData(
            annual_revenue_by_year=[100000.0] * 3,
            annual_costs_by_year=[40000.0] * 3,
        )
        spec = build_cumulative_cash_flow_chart(fd)
        assert spec is not None
        assert spec.traces[0]["y"][0] == 0.0
