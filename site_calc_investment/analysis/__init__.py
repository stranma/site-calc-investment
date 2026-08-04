"""Financial analysis helpers for investment planning."""

from site_calc_investment.analysis.comparison import compare_scenarios
from site_calc_investment.analysis.financial import (
    aggregate_annual,
    calculate_investment_metrics,
    calculate_irr,
    calculate_npv,
    calculate_payback_period,
)

__all__ = [
    "calculate_npv",
    "calculate_irr",
    "calculate_payback_period",
    "calculate_investment_metrics",
    "aggregate_annual",
    "compare_scenarios",
]
