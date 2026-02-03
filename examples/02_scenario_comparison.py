"""Scenario Comparison Example

This example compares three different battery sizes to find the optimal
capacity for investment.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from site_calc_investment import (
    Battery,
    ElectricityExport,
    ElectricityImport,
    InvestmentClient,
    InvestmentParameters,
    InvestmentPlanningRequest,
    OptimizationConfig,
    Site,
    compare_scenarios,
)
from site_calc_investment.models.requests import TimeSpanInvestment


def create_prices(days: int = 7):
    """Create price profile with daily pattern."""
    prices = []
    for day in range(days):
        for hour in range(24):
            if 9 <= hour <= 20:
                prices.append(80.0)  # Day: high price
            else:
                prices.append(30.0)  # Night: low price
    return prices


def create_scenario(
    client: InvestmentClient,
    capacity_mwh: float,
    prices: list,
    timespan: TimeSpanInvestment,
) -> tuple:
    """Create and run a scenario with given battery capacity.

    Returns:
        (scenario_name, result)
    """
    scenario_name = f"{capacity_mwh:.0f} MWh Battery"
    print(f"\n{'=' * 60}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'=' * 60}")

    # Battery sized for 2-hour duration
    battery = Battery(
        name="Battery1",
        properties={
            "capacity": capacity_mwh,
            "max_power": capacity_mwh / 2,  # 2-hour discharge
            "efficiency": 0.90,
            "initial_soc": 0.5,
        },
    )

    grid_import = ElectricityImport(
        name="GridImport",
        properties={"price": prices, "max_import": 50.0},
    )

    grid_export = ElectricityExport(
        name="GridExport",
        properties={"price": prices, "max_export": 50.0},
    )

    site = Site(
        site_id=f"site_{capacity_mwh:.0f}mwh",
        devices=[battery, grid_import, grid_export],
    )

    # Capital cost: EUR 100/kWh
    capex = capacity_mwh * 1000 * 100  # EUR 100/kWh

    # O&M: EUR 1/kWh/year
    opex = capacity_mwh * 1000 * 1  # EUR 1/kWh/year

    inv_params = InvestmentParameters(
        discount_rate=0.05,
        project_lifetime_years=10,  # Required field
        device_capital_costs={"Battery1": capex},
        device_annual_opex={"Battery1": opex},
    )

    request = InvestmentPlanningRequest(
        sites=[site],
        timespan=timespan,
        investment_parameters=inv_params,
        optimization_config=OptimizationConfig(
            objective="maximize_profit",  # Valid options: maximize_profit, minimize_cost, maximize_self_consumption
            time_limit_seconds=300,
        ),
    )

    print(f"  Capacity:   {capacity_mwh:.0f} MWh")
    print(f"  Power:      {capacity_mwh / 2:.0f} MW")
    print(f"  CAPEX:      EUR {capex:,.0f}")
    print(f"  Annual O&M: EUR {opex:,.0f}")

    job = client.create_planning_job(request)
    print(f"\n  Job ID: {job.job_id}")
    print("  Waiting for completion...")

    result = client.wait_for_completion(job.job_id, poll_interval=5, timeout=600)

    print(f"  Completed in {result.summary.solve_time_seconds:.0f}s")

    if result.investment_metrics:
        metrics = result.investment_metrics
        npv_str = f"EUR {metrics.npv:,.0f}" if metrics.npv else "N/A"
        irr_str = f"{metrics.irr * 100:.2f}%" if metrics.irr else "N/A"
        payback_str = f"{metrics.payback_period_years:.1f} years" if metrics.payback_period_years else "N/A"
        print(f"\n  NPV:     {npv_str}")
        print(f"  IRR:     {irr_str}")
        print(f"  Payback: {payback_str}")

    return scenario_name, result


def main():
    print("=" * 60)
    print("BATTERY CAPACITY SIZING: SCENARIO COMPARISON")
    print("=" * 60)
    print("\nComparing three battery sizes over 1-week horizon")
    print("Goal: Find optimal capacity for maximum profit")

    # Get credentials from environment
    api_url = os.environ.get("INVESTMENT_API_URL_DEV") or os.environ.get("INVESTMENT_API_URL")
    api_key = os.environ.get("INVESTMENT_API_KEY_DEV") or os.environ.get("INVESTMENT_API_KEY")

    if not api_url or not api_key:
        print("\nERROR: Set INVESTMENT_API_URL and INVESTMENT_API_KEY environment variables")
        return

    # Initialize client
    client = InvestmentClient(
        base_url=api_url,
        api_key=api_key,
    )

    # 1-week planning
    timespan = TimeSpanInvestment(
        start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
        intervals=168,  # 1 week
    )
    prices = create_prices(days=7)

    print(f"\nPrices: {len(prices)} hourly values")
    print("  Day price: EUR 80/MWh, Night price: EUR 30/MWh")

    # Test three capacities
    capacities = [10.0, 20.0, 30.0]  # MWh

    scenarios = []
    for capacity in capacities:
        name, result = create_scenario(client, capacity, prices, timespan)
        scenarios.append((name, result))

    # Compare scenarios
    print("\n" + "=" * 60)
    print("SCENARIO COMPARISON")
    print("=" * 60)

    names = [s[0] for s in scenarios]
    results = [s[1] for s in scenarios]

    comparison = compare_scenarios(results, names=names)

    # Print comparison table
    print(f"\n{'Scenario':<20} {'Profit':>15} {'NPV':>15} {'IRR':>10}")
    print("-" * 65)

    for i, name in enumerate(comparison["names"]):
        profit = comparison.get("profit", [None] * len(names))[i]
        npv = comparison.get("npv", [None] * len(names))[i]
        irr = comparison.get("irr", [None] * len(names))[i]

        profit_str = f"EUR {profit:,.0f}" if profit is not None else "N/A"
        npv_str = f"EUR {npv:,.0f}" if npv is not None else "N/A"
        irr_str = f"{irr * 100:.2f}%" if irr is not None else "N/A"

        print(f"{name:<20} {profit_str:>15} {npv_str:>15} {irr_str:>10}")

    # Find optimal by profit
    profit_values = comparison.get("profit", [])
    if profit_values:
        valid_profits = [(i, v) for i, v in enumerate(profit_values) if v is not None]
        if valid_profits:
            best_idx, best_profit = max(valid_profits, key=lambda x: x[1])
            best_name = comparison["names"][best_idx]

            print("\n" + "=" * 60)
            print(f"OPTIMAL CONFIGURATION: {best_name}")
            print("=" * 60)
            print(f"  Profit: EUR {best_profit:,.0f}")
    else:
        print("\nNo profit data available for comparison")

    print("=" * 60)


if __name__ == "__main__":
    main()
