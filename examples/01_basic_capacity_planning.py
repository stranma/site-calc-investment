"""Basic Capacity Planning Example

This example demonstrates a simple 10-year battery optimization
for capacity sizing and investment ROI analysis.
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
)


def main():
    # Initialize client
    client = InvestmentClient(
        base_url="https://api.site-calc.example.com",
        api_key="inv_your_api_key_here",
    )

    # Create 10-year planning horizon (1-hour resolution)
    timespan = TimeSpan.for_years(start_year=2025, years=10)
    print(f"Planning horizon: {timespan.years} years ({timespan.intervals} hourly intervals)")

    # Generate simple price profile with 2% annual escalation
    base_hourly_prices = []
    for hour in range(24):
        # Higher prices during day (peak)
        if 9 <= hour <= 20:
            price = 40.0
        else:
            price = 25.0
        base_hourly_prices.append(price)

    # Extend to 10 years with 2% annual escalation
    prices_10y = []
    for year in range(10):
        escalation_factor = (1.02 ** year)
        year_prices = [p * escalation_factor for p in base_hourly_prices] * 365
        prices_10y.extend(year_prices)

    print(f"Price profile generated: {len(prices_10y)} values")
    print(f"  Year 1 avg: €{sum(prices_10y[:8760])/8760:.2f}/MWh")
    print(f"  Year 10 avg: €{sum(prices_10y[-8760:])/8760:.2f}/MWh")

    # Define 10 MW / 20 MWh battery (2-hour duration)
    battery = Battery(
        name="Battery1",
        properties=BatteryProperties(
            capacity=20.0,           # MWh
            max_power=10.0,          # MW (2-hour discharge)
            efficiency=0.90,         # 90% round-trip
            initial_soc=0.5         # Start at 50%
        )
    )

    # Market devices (grid connections)
    grid_import = ElectricityImport(
        name="GridImport",
        properties=MarketImportProperties(
            price=prices_10y,
            max_import=20.0
        )
    )

    grid_export = ElectricityExport(
        name="GridExport",
        properties=MarketExportProperties(
            price=prices_10y,
            max_export=20.0
        )
    )

    # Create site
    site = Site(
        site_id="battery_investment_site",
        description="10-year battery capacity planning",
        devices=[battery, grid_import, grid_export]
    )

    # Investment parameters
    inv_params = InvestmentParameters(
        discount_rate=0.05,  # 5% discount rate
        device_capital_costs={
            "Battery1": 2_000_000  # €2M CAPEX (€100/kWh)
        },
        device_annual_opex={
            "Battery1": 20_000  # €20k/year O&M
        }
    )

    # Create optimization request
    request = InvestmentPlanningRequest(
        sites=[site],
        timespan=timespan,
        investment_parameters=inv_params,
        optimization_config=OptimizationConfig(
            objective="maximize_npv",
            time_limit_seconds=3600,  # 1 hour
            relax_binary_variables=True
        )
    )

    print("\n" + "="*80)
    print("Submitting optimization job...")
    print("="*80)

    # Submit job
    job = client.create_planning_job(request)
    print(f"\nJob ID: {job.job_id}")
    print(f"Status: {job.status}")

    # Wait for completion (with progress updates)
    print("\nWaiting for optimization to complete...")
    print("(This may take 15-60 minutes for 10-year horizon)")

    result = client.wait_for_completion(
        job.job_id,
        poll_interval=30,  # Check every 30 seconds
        timeout=7200       # 2 hour maximum
    )

    print("\n" + "="*80)
    print("OPTIMIZATION RESULTS")
    print("="*80)

    # Summary
    summary = result.summary
    print(f"\nSolver Status: {summary.solver_status}")
    print(f"Solve Time: {summary.solve_time_seconds:.1f}s ({summary.solve_time_seconds/60:.1f} min)")

    # Financial metrics
    if summary.investment_metrics:
        metrics = summary.investment_metrics
        print("\nFINANCIAL METRICS:")
        print(f"  Total Revenue (10y):  €{metrics.total_revenue_period:>15,.0f}")
        print(f"  Total Costs (10y):    €{metrics.total_costs_period:>15,.0f}")
        print(f"  Net Profit (10y):     €{summary.expected_profit:>15,.0f}")
        print(f"\n  NPV:                  €{metrics.npv:>15,.0f}")
        print(f"  IRR:                   {metrics.irr*100:>15.2f}%")
        print(f"  Payback Period:        {metrics.payback_period_years:>15.1f} years")

        # Annual breakdown
        if metrics.annual_revenue_by_year:
            print("\nANNUAL BREAKDOWN:")
            revenues = metrics.annual_revenue_by_year
            costs = metrics.annual_costs_by_year
            for year, (revenue, cost) in enumerate(zip(revenues, costs), 1):
                print(f"  Year {year:2d}:  Revenue €{revenue:>10,.0f}  |  Cost €{cost:>10,.0f}")

    # Device schedules (first and last 24 hours)
    site_result = result.sites["battery_investment_site"]
    battery_schedule = site_result.device_schedules["Battery1"]

    print("\nBATTERY OPERATION (First 24 hours):")
    el_flow = battery_schedule.flows["electricity"]
    soc = battery_schedule.soc

    for hour in range(24):
        print(f"  Hour {hour:2d}:  Power {el_flow[hour]:>6.2f} MW  |  SOC {soc[hour]:>5.1%}")

    print("\nBATTERY OPERATION (Last 24 hours):")
    for hour in range(-24, 0):
        actual_hour = hour % 24
        print(f"  Hour {actual_hour:2d}:  Power {el_flow[hour]:>6.2f} MW  |  SOC {soc[hour]:>5.1%}")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
