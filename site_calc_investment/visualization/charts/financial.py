"""Financial chart builders for the visualization dashboard.

Builds Plotly.js-compatible chart specs (plain dicts) for:
- KPI summary cards (NPV, IRR, payback, profit)
- Annual revenue vs costs bar chart
- Cumulative cash flow line chart
"""

from typing import Any, Dict, List, Optional

from site_calc_investment.visualization.types import ChartSpec, FinancialData


def build_kpi_cards(financial: FinancialData) -> List[Dict[str, Any]]:
    """Build KPI card data for the financial summary section.

    :param financial: Extracted financial data.
    :returns: List of KPI dicts with label, value, and formatted_value.
        Returns 4 KPIs when investment_metrics are present (NPV, IRR, payback, profit),
        or 1 KPI (profit only) when they are not.
    """
    cards: List[Dict[str, Any]] = []

    if financial.npv is not None:
        cards.append(
            {
                "label": "Net Present Value",
                "value": financial.npv,
                "formatted_value": _format_currency(financial.npv),
                "unit": "EUR",
            }
        )

    if financial.irr is not None:
        cards.append(
            {
                "label": "Internal Rate of Return",
                "value": financial.irr,
                "formatted_value": f"{financial.irr * 100:.1f}%",
                "unit": "%",
            }
        )

    if financial.payback_period_years is not None:
        cards.append(
            {
                "label": "Payback Period",
                "value": financial.payback_period_years,
                "formatted_value": f"{financial.payback_period_years:.1f} years",
                "unit": "years",
            }
        )

    if financial.expected_profit is not None:
        cards.append(
            {
                "label": "Total Profit",
                "value": financial.expected_profit,
                "formatted_value": _format_currency(financial.expected_profit),
                "unit": "EUR",
            }
        )

    return cards


def build_annual_revenue_costs_chart(financial: FinancialData) -> Optional[ChartSpec]:
    """Build grouped bar chart of annual revenue vs costs.

    :param financial: Extracted financial data (needs annual_revenue_by_year and annual_costs_by_year).
    :returns: ChartSpec with 2 bar traces, or None if annual data is not available.
    """
    if not financial.annual_revenue_by_year or not financial.annual_costs_by_year:
        return None
    if len(financial.annual_revenue_by_year) != len(financial.annual_costs_by_year):
        return None

    num_years = len(financial.annual_revenue_by_year)
    year_labels = [f"Year {i + 1}" for i in range(num_years)]

    revenue_trace: Dict[str, Any] = {
        "x": year_labels,
        "y": financial.annual_revenue_by_year,
        "type": "bar",
        "name": "Revenue",
        "marker": {"color": "#2ecc71"},
    }

    costs_trace: Dict[str, Any] = {
        "x": year_labels,
        "y": financial.annual_costs_by_year,
        "type": "bar",
        "name": "Costs",
        "marker": {"color": "#e74c3c"},
    }

    layout: Dict[str, Any] = {
        "title": {"text": "Annual Revenue vs Costs"},
        "barmode": "group",
        "xaxis": {"title": {"text": "Year"}},
        "yaxis": {"title": {"text": "EUR"}},
        "legend": {"orientation": "h", "y": -0.15},
    }

    return ChartSpec(traces=[revenue_trace, costs_trace], layout=layout, chart_id="annual_revenue_costs")


def build_cumulative_cash_flow_chart(
    financial: FinancialData,
    initial_investment: float = 0.0,
) -> Optional[ChartSpec]:
    """Build cumulative cash flow line chart with payback point marker.

    :param financial: Extracted financial data.
    :param initial_investment: Initial CAPEX (negative value expected, e.g. -500000).
    :returns: ChartSpec with a line trace, or None if annual data is not available.
    """
    if not financial.annual_revenue_by_year or not financial.annual_costs_by_year:
        return None
    if len(financial.annual_revenue_by_year) != len(financial.annual_costs_by_year):
        return None

    num_years = len(financial.annual_revenue_by_year)
    year_labels = ["Year 0"] + [f"Year {i + 1}" for i in range(num_years)]

    # Build cumulative cash flow starting from initial investment
    cumulative: List[float] = [initial_investment]
    running_total = initial_investment
    for rev, cost in zip(financial.annual_revenue_by_year, financial.annual_costs_by_year):
        running_total += rev - cost
        cumulative.append(running_total)

    cash_flow_trace: Dict[str, Any] = {
        "x": year_labels,
        "y": cumulative,
        "type": "scatter",
        "mode": "lines+markers",
        "name": "Cumulative Cash Flow",
        "line": {"color": "#3498db", "width": 2},
        "marker": {"size": 6},
    }

    # Zero line
    zero_line_trace: Dict[str, Any] = {
        "x": year_labels,
        "y": [0] * len(year_labels),
        "type": "scatter",
        "mode": "lines",
        "name": "Break Even",
        "line": {"color": "#95a5a6", "dash": "dash", "width": 1},
        "showlegend": False,
    }

    layout: Dict[str, Any] = {
        "title": {"text": "Cumulative Cash Flow"},
        "xaxis": {"title": {"text": "Year"}},
        "yaxis": {"title": {"text": "EUR"}},
        "legend": {"orientation": "h", "y": -0.15},
        "annotations": [],
    }

    # Add payback point annotation if available
    if financial.payback_period_years is not None:
        payback_year = financial.payback_period_years
        # Add a vertical line annotation at payback point
        layout["annotations"].append(
            {
                "x": payback_year,
                "y": 0,
                "xref": "x",
                "yref": "y",
                "text": f"Payback: {payback_year:.1f}y",
                "showarrow": True,
                "arrowhead": 2,
                "ax": 0,
                "ay": -40,
                "font": {"color": "#e67e22", "size": 12},
            }
        )

        # Add vertical line shape
        layout["shapes"] = [
            {
                "type": "line",
                "x0": payback_year,
                "x1": payback_year,
                "y0": 0,
                "y1": 1,
                "xref": "x",
                "yref": "paper",
                "line": {"color": "#e67e22", "dash": "dot", "width": 2},
            }
        ]

    return ChartSpec(
        traces=[cash_flow_trace, zero_line_trace],
        layout=layout,
        chart_id="cumulative_cash_flow",
    )


def _format_currency(value: float) -> str:
    """Format a number as EUR currency string.

    :param value: Value in EUR.
    :returns: Formatted string like "EUR 850,000" or "EUR -23,162".
    """
    if abs(value) >= 1000:
        return f"EUR {value:,.0f}"
    return f"EUR {value:,.2f}"
