"""Visualization module for investment planning results.

Generates interactive HTML dashboards from optimization results using Plotly.js.
No additional Python dependencies required -- chart specs are built as plain dicts
and rendered via Plotly.js CDN in the generated HTML.
"""

from site_calc_investment.visualization.dashboard import generate_dashboard

__all__ = ["generate_dashboard"]
