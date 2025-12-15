"""Financial analysis helpers for investment planning."""

from site_calc_investment.analysis.financial import (
    calculate_npv,
    calculate_irr,
    calculate_payback_period,
    aggregate_annual,
)
from site_calc_investment.analysis.comparison import compare_scenarios

__all__ = [
    "calculate_npv",
    "calculate_irr",
    "calculate_payback_period",
    "aggregate_annual",
    "compare_scenarios",
]
