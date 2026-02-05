"""Dashboard assembly and file generation.

Combines all chart specs into a single interactive HTML file
with Plotly.js loaded via CDN.
"""

import json
import os
import webbrowser
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from site_calc_investment.visualization._template import DASHBOARD_TEMPLATE, PLOTLY_CDN_URL
from site_calc_investment.visualization.charts.dispatch import (
    prepare_drill_down_data,
    should_embed_hourly_data,
)
from site_calc_investment.visualization.charts.energy import (
    build_energy_balance_chart,
    build_energy_summary_kpis,
)
from site_calc_investment.visualization.charts.financial import (
    build_annual_revenue_costs_chart,
    build_cumulative_cash_flow_chart,
    build_kpi_cards,
)
from site_calc_investment.visualization.types import ChartSpec, DashboardData


def generate_dashboard(
    job_id: str,
    response: Any,
    open_browser: bool = True,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate an interactive HTML dashboard from optimization results.

    :param job_id: Job identifier.
    :param response: InvestmentPlanningResponse object.
    :param open_browser: Whether to open the dashboard in a browser.
    :param output_dir: Override output directory (default: INVESTMENT_DATA_DIR/dashboards or cwd).
    :returns: Dict with file_path, charts_generated, summary, and message.
    """
    data = DashboardData.from_response(response)

    # Build all chart components
    kpi_cards = build_kpi_cards(data.financial)
    annual_chart = build_annual_revenue_costs_chart(data.financial)
    cash_flow_chart = build_cumulative_cash_flow_chart(data.financial)
    energy_chart = build_energy_balance_chart(data.energy, data.aggregation_level)
    energy_kpis = build_energy_summary_kpis(data.energy)

    # Device detail data
    embed_hourly = should_embed_hourly_data(data.energy.devices)
    drill_down = prepare_drill_down_data(data.energy.devices) if embed_hourly else None

    # Assemble HTML
    html = _assemble_html(
        job_id=job_id,
        kpi_cards=kpi_cards,
        annual_chart=annual_chart,
        cash_flow_chart=cash_flow_chart,
        energy_chart=energy_chart,
        energy_kpis=energy_kpis,
        drill_down_data=drill_down,
        total_hours=data.timespan.total_hours,
    )

    # Write file
    output_path = _get_output_path(job_id, output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    # Open in browser if requested
    if open_browser:
        _open_in_browser(str(output_path))

    # Build return dict
    charts_generated: List[str] = ["kpi_cards", "energy_balance", "energy_kpis"]
    if annual_chart:
        charts_generated.append("annual_revenue_costs")
    if cash_flow_chart:
        charts_generated.append("cumulative_cash_flow")
    if drill_down:
        charts_generated.append("device_drill_down")

    summary: Dict[str, Any] = {}
    if data.financial.npv is not None:
        summary["npv"] = data.financial.npv
    if data.financial.irr is not None:
        summary["irr"] = data.financial.irr
    if data.financial.payback_period_years is not None:
        summary["payback_period_years"] = data.financial.payback_period_years
    if data.financial.expected_profit is not None:
        summary["expected_profit"] = data.financial.expected_profit

    return {
        "file_path": str(output_path),
        "charts_generated": charts_generated,
        "summary": summary,
        "message": f"Dashboard saved to {output_path}",
    }


def _assemble_html(
    job_id: str,
    kpi_cards: List[Dict[str, Any]],
    annual_chart: Optional[ChartSpec],
    cash_flow_chart: Optional[ChartSpec],
    energy_chart: ChartSpec,
    energy_kpis: Dict[str, Any],
    drill_down_data: Optional[Dict[str, Any]],
    total_hours: int,
) -> str:
    """Assemble the full HTML dashboard from components.

    :param job_id: Job identifier.
    :param kpi_cards: KPI card dicts.
    :param annual_chart: Annual revenue/costs chart spec (or None).
    :param cash_flow_chart: Cumulative cash flow chart spec (or None).
    :param energy_chart: Energy balance chart spec.
    :param energy_kpis: Energy summary KPIs dict.
    :param drill_down_data: Device drill-down data for JS embedding (or None).
    :param total_hours: Total hours in the optimization.
    :returns: Complete HTML string.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    default_window_end = min(168, total_hours)

    # Build KPI cards HTML
    kpi_html = _build_kpi_cards_html(kpi_cards)
    energy_kpi_html = _build_energy_kpi_html(energy_kpis)

    # Serialize chart specs to JSON
    annual_json = _chart_to_json(annual_chart) if annual_chart else "null"
    cash_flow_json = _chart_to_json(cash_flow_chart) if cash_flow_chart else "null"
    energy_json = _chart_to_json(energy_chart)
    drill_down_json = json.dumps(drill_down_data) if drill_down_data else "null"

    return DASHBOARD_TEMPLATE.format(
        job_id=escape(job_id),
        timestamp=timestamp,
        plotly_cdn_url=PLOTLY_CDN_URL,
        kpi_cards_html=kpi_html,
        energy_kpi_html=energy_kpi_html,
        annual_revenue_json=annual_json,
        cumulative_cash_flow_json=cash_flow_json,
        energy_balance_json=energy_json,
        drill_down_json=drill_down_json,
        default_window_end=default_window_end,
        total_hours=total_hours,
    )


def _build_kpi_cards_html(cards: List[Dict[str, Any]]) -> str:
    """Build KPI cards HTML from card dicts."""
    if not cards:
        return '<div class="kpi-card"><div class="label">No Data</div><div class="value">--</div></div>'

    parts: List[str] = []
    for card in cards:
        parts.append(
            f'<div class="kpi-card">'
            f'<div class="label">{escape(card["label"])}</div>'
            f'<div class="value">{escape(card["formatted_value"])}</div>'
            f"</div>"
        )
    return "\n            ".join(parts)


def _build_energy_kpi_html(kpis: Dict[str, Any]) -> str:
    """Build energy KPI cards HTML."""
    items = [
        ("Total Generation", f'{kpis["total_generation_mwh"]:,.0f} MWh'),
        ("Total Consumption", f'{kpis["total_consumption_mwh"]:,.0f} MWh'),
        ("Net Grid Position", f'{kpis["net_grid_position_mwh"]:,.0f} MWh'),
    ]
    parts: List[str] = []
    for label, value in items:
        parts.append(
            f'<div class="kpi-card">'
            f'<div class="label">{escape(label)}</div>'
            f'<div class="value">{escape(value)}</div>'
            f"</div>"
        )
    return "\n            ".join(parts)


def _chart_to_json(spec: ChartSpec) -> str:
    """Convert a ChartSpec to JSON string for embedding."""
    return json.dumps({"traces": spec.traces, "layout": spec.layout})


def _get_output_path(job_id: str, output_dir: Optional[str] = None) -> Path:
    """Determine the output file path for the dashboard.

    :param job_id: Job identifier (used in filename).
    :param output_dir: Override directory, or None to use default.
    :returns: Path for the output HTML file.
    """
    if output_dir:
        base_dir = Path(output_dir)
    else:
        data_dir = os.environ.get("INVESTMENT_DATA_DIR")
        if data_dir:
            base_dir = Path(data_dir) / "dashboards"
        else:
            base_dir = Path.cwd() / "dashboards"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"dashboard_{job_id}_{timestamp}.html"
    return base_dir / filename


def _open_in_browser(file_path: str) -> None:
    """Open the dashboard in the default web browser.

    :param file_path: Absolute path to the HTML file.
    """
    webbrowser.open(f"file://{file_path}")
