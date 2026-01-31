"""Scenario comparison utilities."""

from typing import List, Optional

from site_calc_investment.models.responses import InvestmentPlanningResponse


def compare_scenarios(
    scenarios: List[InvestmentPlanningResponse],
    names: Optional[List[str]] = None,
) -> dict:
    """Compare multiple optimization scenarios.

    Extracts key metrics from each scenario for easy comparison.

    Args:
        scenarios: List of optimization results
        names: Optional names for each scenario (default: "Scenario 1", "Scenario 2", ...)

    Returns:
        Dictionary with comparison data suitable for printing or DataFrame conversion

    Example:
        >>> results = [result_5mw, result_10mw, result_15mw]
        >>> comparison = compare_scenarios(results, names=["5 MW", "10 MW", "15 MW"])
        >>> for name, metrics in zip(comparison["names"], comparison["npv"]):
        ...     print(f"{name}: NPV = €{metrics:,.0f}")
        5 MW: NPV = €1,250,000
        10 MW: NPV = €1,850,000
        15 MW: NPV = €1,600,000
    """
    if not scenarios:
        raise ValueError("At least one scenario is required")

    if names is None:
        names = [f"Scenario {i + 1}" for i in range(len(scenarios))]

    if len(names) != len(scenarios):
        raise ValueError(f"Number of names ({len(names)}) must match number of scenarios ({len(scenarios)})")

    comparison = {
        "names": names,
        "total_revenue": [],
        "total_costs": [],
        "profit": [],
        "npv": [],
        "irr": [],
        "payback_years": [],
        "solve_time_seconds": [],
        "solver_status": [],
    }

    for scenario in scenarios:
        summary = scenario.summary
        inv_metrics = summary.investment_metrics

        comparison["total_revenue"].append(
            inv_metrics.total_revenue_period if inv_metrics else summary.expected_profit + summary.total_cost
        )
        comparison["total_costs"].append(summary.total_cost)
        comparison["profit"].append(summary.expected_profit)
        comparison["npv"].append(inv_metrics.npv if inv_metrics else None)
        comparison["irr"].append(inv_metrics.irr if inv_metrics else None)
        comparison["payback_years"].append(inv_metrics.payback_period_years if inv_metrics else None)
        comparison["solve_time_seconds"].append(summary.solve_time_seconds)
        comparison["solver_status"].append(summary.solver_status)

    return comparison


def print_comparison(comparison: dict) -> None:
    """Print scenario comparison in a readable format.

    Args:
        comparison: Comparison dictionary from compare_scenarios()

    Example:
        >>> comparison = compare_scenarios([result1, result2, result3], names=["Small", "Medium", "Large"])
        >>> print_comparison(comparison)
        === Scenario Comparison ===
        ...
    """
    print("=" * 80)
    print("SCENARIO COMPARISON")
    print("=" * 80)

    for i, name in enumerate(comparison["names"]):
        print(f"\n{name}:")
        print(f"  Total Revenue:   €{comparison['total_revenue'][i]:>15,.0f}")
        print(f"  Total Costs:     €{comparison['total_costs'][i]:>15,.0f}")
        print(f"  Profit:          €{comparison['profit'][i]:>15,.0f}")

        if comparison["npv"][i] is not None:
            print(f"  NPV:             €{comparison['npv'][i]:>15,.0f}")

        if comparison["irr"][i] is not None:
            print(f"  IRR:              {comparison['irr'][i] * 100:>15.2f}%")

        if comparison["payback_years"][i] is not None:
            print(f"  Payback:          {comparison['payback_years'][i]:>15.1f} years")

        print(f"  Solve Time:       {comparison['solve_time_seconds'][i]:>15.1f}s")
        print(f"  Solver Status:    {comparison['solver_status'][i]:>15}")

    print("\n" + "=" * 80)

    # Find best scenario by NPV
    npv_values = [v for v in comparison["npv"] if v is not None]
    if npv_values:
        best_idx = comparison["npv"].index(max(npv_values))
        print(f"\nBest Scenario (by NPV): {comparison['names'][best_idx]}")
        print(f"NPV: €{comparison['npv'][best_idx]:,.0f}")

    print("=" * 80)
