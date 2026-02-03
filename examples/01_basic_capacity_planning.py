"""Basic Capacity Planning Example

This example demonstrates a simple 1-week battery optimization
for capacity sizing and investment ROI analysis.
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
)
from site_calc_investment.models.requests import TimeSpanInvestment


def main():
    """Run basic capacity planning example with 1-week battery optimization."""
    # Get credentials from environment
    api_url = os.environ.get("INVESTMENT_API_URL_DEV") or os.environ.get("INVESTMENT_API_URL")
    api_key = os.environ.get("INVESTMENT_API_KEY_DEV") or os.environ.get("INVESTMENT_API_KEY")

    if not api_url or not api_key:
        print("ERROR: Set INVESTMENT_API_URL and INVESTMENT_API_KEY environment variables")
        return

    # Initialize client
    client = InvestmentClient(
        base_url=api_url,
        api_key=api_key,
    )

    # Create 1-week planning horizon (1-hour resolution)
    timespan = TimeSpanInvestment(
        start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
        intervals=168,  # 1 week = 7 days x 24 hours
    )
    print(f"Planning horizon: {timespan.intervals} hourly intervals ({timespan.intervals / 24:.0f} days)")

    # Generate price profile with day/night pattern
    prices = []
    for hour in range(168):
        hour_of_day = hour % 24
        if 9 <= hour_of_day <= 20:
            prices.append(80.0)  # Day: high price
        else:
            prices.append(30.0)  # Night: low price

    print(f"Price profile generated: {len(prices)} values")
    print("  Day price: EUR 80/MWh, Night price: EUR 30/MWh")

    # Define 10 MW / 20 MWh battery (2-hour duration)
    battery = Battery(
        name="Battery1",
        properties={
            "capacity": 20.0,  # MWh
            "max_power": 10.0,  # MW (2-hour discharge)
            "efficiency": 0.90,  # 90% round-trip
            "initial_soc": 0.5,  # Start at 50%
        },
    )

    # Market devices (grid connections)
    grid_import = ElectricityImport(
        name="GridImport",
        properties={"price": prices, "max_import": 20.0},
    )

    grid_export = ElectricityExport(
        name="GridExport",
        properties={"price": prices, "max_export": 20.0},
    )

    # Create site
    site = Site(
        site_id="battery_investment_site",
        description="Battery capacity planning example",
        devices=[battery, grid_import, grid_export],
    )

    # Investment parameters
    inv_params = InvestmentParameters(
        discount_rate=0.05,  # 5% discount rate
        project_lifetime_years=10,  # Required field
        device_capital_costs={
            "Battery1": 2_000_000  # EUR 2M CAPEX (EUR 100/kWh)
        },
        device_annual_opex={
            "Battery1": 20_000  # EUR 20k/year O&M
        },
    )

    # Create optimization request
    request = InvestmentPlanningRequest(
        sites=[site],
        timespan=timespan,
        investment_parameters=inv_params,
        optimization_config=OptimizationConfig(
            objective="maximize_profit",  # Options: maximize_profit, minimize_cost, maximize_self_consumption
            time_limit_seconds=300,  # 5 minutes max
            relax_binary_variables=True,
        ),
    )

    print("\n" + "=" * 60)
    print("Submitting optimization job...")
    print("=" * 60)

    # Submit job
    job = client.create_planning_job(request)
    print(f"\nJob ID: {job.job_id}")
    print(f"Status: {job.status}")

    # Wait for completion
    print("\nWaiting for optimization to complete...")

    result = client.wait_for_completion(
        job.job_id,
        poll_interval=5,  # Check every 5 seconds
        timeout=600,  # 10 minute maximum
    )

    print("\n" + "=" * 60)
    print("OPTIMIZATION RESULTS")
    print("=" * 60)

    # Summary
    summary = result.summary
    print(f"\nSolver Status: {summary.solver_status}")
    print(f"Solve Time: {summary.solve_time_seconds:.1f}s")

    if summary.expected_profit is not None:
        print(f"Expected Profit: EUR {summary.expected_profit:,.2f}")

    # Investment metrics (if available)
    if result.investment_metrics:
        metrics = result.investment_metrics
        print("\nINVESTMENT METRICS:")
        if metrics.total_revenue_10y is not None:
            print(f"  Total Revenue (10y):  EUR {metrics.total_revenue_10y:>15,.0f}")
        if metrics.total_costs_10y is not None:
            print(f"  Total Costs (10y):    EUR {metrics.total_costs_10y:>15,.0f}")
        if metrics.npv is not None:
            print(f"  NPV:                  EUR {metrics.npv:>15,.0f}")
        if metrics.irr is not None:
            print(f"  IRR:                       {metrics.irr * 100:>15.2f}%")
        if metrics.payback_period_years is not None:
            print(f"  Payback Period:            {metrics.payback_period_years:>15.1f} years")

    # Device schedules (first 24 hours)
    site_result = result.sites.get("battery_investment_site")
    if site_result:
        battery_schedule = site_result.device_schedules.get("Battery1")
        if battery_schedule and battery_schedule.flows.get("electricity"):
            print("\nBATTERY OPERATION (First 24 hours):")
            el_flow = battery_schedule.flows["electricity"]
            soc = battery_schedule.soc or []

            for hour in range(min(24, len(el_flow))):
                soc_str = f"{soc[hour]:.1%}" if hour < len(soc) else "N/A"
                print(f"  Hour {hour:2d}:  Power {el_flow[hour]:>7.2f} MW  |  SOC {soc_str}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
