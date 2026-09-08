"""Solver-status fields on Summary: Optimal vs Feasible, gap, older services."""

import copy

from site_calc_investment.analysis import compare_scenarios
from site_calc_investment.analysis.comparison import print_comparison
from site_calc_investment.models.responses import InvestmentPlanningResponse, Summary


def test_summary_status_fields_default_to_none_for_older_services():
    summary = Summary(solver_status="Optimal", solve_time_seconds=1.0)
    assert summary.is_optimal is None
    assert summary.termination_reason is None
    assert summary.optimality_gap is None


def test_summary_carries_feasible_stop():
    summary = Summary(
        solver_status="Feasible",
        solve_time_seconds=300.0,
        is_optimal=False,
        termination_reason="time_limit",
        optimality_gap=0.083,
    )
    assert summary.is_optimal is False
    assert summary.termination_reason == "time_limit"
    assert summary.optimality_gap == 0.083


def test_compare_scenarios_reports_gap(mock_job_completed_response):
    data = copy.deepcopy(mock_job_completed_response)
    data["summary"].update({"solver_status": "Feasible", "is_optimal": False, "optimality_gap": 0.05})
    feasible = InvestmentPlanningResponse(**data)
    proven = InvestmentPlanningResponse(**mock_job_completed_response)

    comparison = compare_scenarios([feasible, proven], names=["cut short", "proven"])

    assert comparison["solver_status"] == ["Feasible", "optimal"]
    assert comparison["optimality_gap"] == [0.05, None]


def test_print_comparison_shows_gap(mock_job_completed_response, capsys):
    data = copy.deepcopy(mock_job_completed_response)
    data["summary"].update({"is_optimal": True, "optimality_gap": 0.0083})
    comparison = compare_scenarios([InvestmentPlanningResponse(**data)], names=["proven"])

    print_comparison(comparison)

    assert "Optimality Gap:" in capsys.readouterr().out
