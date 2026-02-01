"""Scenario Comparison Example

This example compares three different battery sizes to find the optimal
capacity for a 10-year investment.
"""

from site_calc_investment import (
    Battery,
    BatteryProperties,
    ElectricityExport,
    ElectricityImport,
    InvestmentClient,
    InvestmentParameters,
    InvestmentPlanningRequest,
    MarketExportProperties,
    MarketImportProperties,
    OptimizationConfig,
    Site,
    TimeSpan,
    compare_scenarios,
)


def create_prices(years: int = 10, escalation_rate: float = 0.02):
    """Create price profile with daily pattern and annual escalation."""
    base_hourly = []
    for hour in range(24):
        if 9 <= hour <= 20:
            price = 40.0
        else:
            price = 25.0
        base_hourly.append(price)

    prices = []
    for year in range(years):
        factor = (1 + escalation_rate) ** year
        prices.extend([p * factor for p in base_hourly] * 365)

    return prices


def create_scenario(
    client: InvestmentClient,
    capacity_mwh: float,
    prices: list,
    timespan: TimeSpan,
) -> tuple:
    """Create and run a scenario with given battery capacity.

    Returns:
        (scenario_name, result)
    """
    scenario_name = f"{capacity_mwh:.0f} MWh Battery"
    print(f"\n{'=' * 80}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'=' * 80}")

    # Battery sized for 2-hour duration
    battery = Battery(
        name="Battery1",
        properties=BatteryProperties(
            capacity=capacity_mwh,
            max_power=capacity_mwh / 2,  # 2-hour discharge
            efficiency=0.90,
            initial_soc=0.5,
        ),
    )

    grid_import = ElectricityImport(name="GridImport", properties=MarketImportProperties(price=prices, max_import=50.0))

    grid_export = ElectricityExport(name="GridExport", properties=MarketExportProperties(price=prices, max_export=50.0))

    site = Site(site_id=f"site_{capacity_mwh:.0f}mwh", devices=[battery, grid_import, grid_export])

    # Capital cost: €100/kWh
    capex = capacity_mwh * 1000 * 100  # €100/kWh

    # O&M: €1/kWh/year
    opex = capacity_mwh * 1000 * 1  # €1/kWh/year

    inv_params = InvestmentParameters(
        discount_rate=0.05, device_capital_costs={"Battery1": capex}, device_annual_opex={"Battery1": opex}
    )

    request = InvestmentPlanningRequest(
        sites=[site],
        timespan=timespan,
        investment_parameters=inv_params,
        optimization_config=OptimizationConfig(objective="maximize_npv", time_limit_seconds=300),
    )

    print(f"  Capacity:  {capacity_mwh:.0f} MWh")
    print(f"  Power:     {capacity_mwh / 2:.0f} MW")
    print(f"  CAPEX:     €{capex:,.0f}")
    print(f"  Annual O&M: €{opex:,.0f}")

    job = client.create_planning_job(request)
    print(f"\n  Job ID: {job.job_id}")
    print("  Waiting for completion...")

    result = client.wait_for_completion(job.job_id, poll_interval=30, timeout=7200)

    print(f"  ✅ Completed in {result.summary.solve_time_seconds:.0f}s")

    if result.summary.investment_metrics:
        metrics = result.summary.investment_metrics
        print(f"\n  NPV:       €{metrics.npv:>12,.0f}")
        print(f"  IRR:        {metrics.irr * 100:>12.2f}%")
        print(f"  Payback:    {metrics.payback_period_years:>12.1f} years")

    return scenario_name, result


def main():
    print("=" * 80)
    print("BATTERY CAPACITY SIZING: SCENARIO COMPARISON")
    print("=" * 80)
    print("\nComparing three battery sizes over 10-year horizon")
    print("Goal: Find optimal capacity for maximum NPV")

    # Initialize client
    client = InvestmentClient(
        base_url="https://api.site-calc.example.com",
        api_key="inv_your_api_key_here",
    )

    # 10-year planning
    timespan = TimeSpan.for_years(2025, 10)
    prices = create_prices(years=10, escalation_rate=0.02)

    print(f"\nPrices: {len(prices)} hourly values")
    print(f"  Year 1 avg: €{sum(prices[:8760]) / 8760:.2f}/MWh")
    print(f"  Year 10 avg: €{sum(prices[-8760:]) / 8760:.2f}/MWh")

    # Test three capacities
    capacities = [10.0, 20.0, 30.0]  # MWh

    scenarios = []
    for capacity in capacities:
        name, result = create_scenario(client, capacity, prices, timespan)
        scenarios.append((name, result))

    # Compare scenarios
    print("\n" + "=" * 80)
    print("SCENARIO COMPARISON")
    print("=" * 80)

    names = [s[0] for s in scenarios]
    results = [s[1] for s in scenarios]

    comparison = compare_scenarios(results, names=names)

    # Print comparison table
    print(f"\n{'Scenario':<20} {'NPV':>15} {'IRR':>10} {'Payback':>12} {'Revenue':>15} {'Costs':>15}")
    print("-" * 100)

    for i, name in enumerate(comparison["names"]):
        npv = comparison["npv"][i]
        irr = comparison["irr"][i]
        payback = comparison["payback_years"][i]
        revenue = comparison["total_revenue"][i]
        costs = comparison["total_costs"][i]

        npv_str = f"€{npv:,.0f}" if npv is not None else "N/A"
        irr_str = f"{irr * 100:.2f}%" if irr is not None else "N/A"
        payback_str = f"{payback:.1f} yrs" if payback is not None else "N/A"

        print(f"{name:<20} {npv_str:>15} {irr_str:>10} {payback_str:>12} €{revenue:>13,.0f} €{costs:>13,.0f}")

    # Find optimal
    npv_values = [(i, v) for i, v in enumerate(comparison["npv"]) if v is not None]
    if npv_values:
        best_idx, best_npv = max(npv_values, key=lambda x: x[1])
        best_name = comparison["names"][best_idx]

        print("\n" + "=" * 80)
        print(f"OPTIMAL CONFIGURATION: {best_name}")
        print("=" * 80)
        print(f"  NPV:       €{best_npv:,.0f}")
        print(f"  IRR:        {comparison['irr'][best_idx] * 100:.2f}%")
        print(f"  Payback:    {comparison['payback_years'][best_idx]:.1f} years")
        print(f"  10y Revenue: €{comparison['total_revenue'][best_idx]:,.0f}")
        print(f"  10y Costs:   €{comparison['total_costs'][best_idx]:,.0f}")
        print(f"  10y Profit:  €{comparison['profit'][best_idx]:,.0f}")
        print("=" * 80)

    # Calculate NPV per MWh of capacity
    print("\nCAPEX EFFICIENCY:")
    for i, capacity in enumerate(capacities):
        npv = comparison["npv"][i]
        if npv is not None:
            npv_per_mwh = npv / capacity
            print(f"  {capacity:.0f} MWh:  €{npv_per_mwh:,.0f} NPV per MWh")


if __name__ == "__main__":
    main()
