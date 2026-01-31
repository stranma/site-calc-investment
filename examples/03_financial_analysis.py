"""Financial Analysis Example

This example demonstrates using the financial analysis helpers to
perform detailed ROI analysis on an optimization result.
"""

from site_calc_investment import (
    aggregate_annual,
    calculate_irr,
    calculate_npv,
    calculate_payback_period,
)


def main():
    print("="*80)
    print("FINANCIAL ANALYSIS EXAMPLE")
    print("="*80)

    # Example 1: Simple NPV calculation
    print("\n1. NET PRESENT VALUE (NPV)")
    print("-" * 80)

    annual_revenues = [100_000, 105_000, 110_000, 115_000, 120_000,
                       125_000, 130_000, 135_000, 140_000, 145_000]
    annual_costs = [30_000, 31_000, 32_000, 33_000, 34_000,
                    35_000, 36_000, 37_000, 38_000, 39_000]
    annual_cash_flows = [r - c for r, c in zip(annual_revenues, annual_costs)]
    initial_investment = -500_000  # €500k CAPEX

    discount_rate = 0.05  # 5%

    npv = calculate_npv(annual_cash_flows, discount_rate, initial_investment)

    print(f"Initial Investment:  €{-initial_investment:,.0f}")
    print(f"Discount Rate:        {discount_rate*100:.1f}%")
    print(f"Planning Horizon:     {len(annual_cash_flows)} years")
    print("\nAnnual Cash Flows:")
    for year, cf in enumerate(annual_cash_flows, 1):
        print(f"  Year {year:2d}:  €{cf:>10,.0f}")

    print(f"\nNPV:  €{npv:,.0f}")

    if npv > 0:
        print("✅ Positive NPV - Investment is profitable")
    else:
        print("❌ Negative NPV - Investment not recommended")

    # Example 2: IRR calculation
    print("\n2. INTERNAL RATE OF RETURN (IRR)")
    print("-" * 80)

    cash_flows_with_capex = [initial_investment] + annual_cash_flows

    irr = calculate_irr(cash_flows_with_capex)

    print("Cash Flows (including CAPEX):")
    for year, cf in enumerate(cash_flows_with_capex):
        if year == 0:
            print(f"  Year {year:2d} (CAPEX):  €{cf:>10,.0f}")
        else:
            print(f"  Year {year:2d}:          €{cf:>10,.0f}")

    if irr is not None:
        print(f"\nIRR:  {irr*100:.2f}%")

        if irr > discount_rate:
            print(f"✅ IRR ({irr*100:.2f}%) > Discount Rate ({discount_rate*100:.1f}%) - Good investment")
        else:
            print(f"❌ IRR ({irr*100:.2f}%) < Discount Rate ({discount_rate*100:.1f}%) - Poor investment")
    else:
        print("\n⚠️  Could not calculate IRR")

    # Example 3: Payback Period
    print("\n3. PAYBACK PERIOD")
    print("-" * 80)

    payback = calculate_payback_period(cash_flows_with_capex)

    print("Cumulative Cash Flow:")
    cumulative = 0
    for year, cf in enumerate(cash_flows_with_capex):
        cumulative += cf
        if year == 0:
            print(f"  Year {year:2d} (CAPEX):  €{cf:>10,.0f}  =>  €{cumulative:>10,.0f}")
        else:
            print(f"  Year {year:2d}:          €{cf:>10,.0f}  =>  €{cumulative:>10,.0f}")

    if payback is not None:
        print(f"\nPayback Period:  {payback:.2f} years")

        if payback < 5:
            print("✅ Quick payback (<5 years) - Low risk")
        elif payback < 8:
            print("⚠️  Moderate payback (5-8 years) - Medium risk")
        else:
            print("❌ Long payback (>8 years) - High risk")
    else:
        print("\n⚠️  Investment never pays back")

    # Example 4: Aggregate hourly data to annual
    print("\n4. AGGREGATING HOURLY DATA")
    print("-" * 80)

    # Simulate 2 years of hourly battery discharge
    hours_per_year = 8760
    years = 2

    # Average 2 MW discharge, 50% of the time
    hourly_discharge = []
    for hour in range(hours_per_year * years):
        hour_of_day = hour % 24
        # Discharge during high-price hours (9am-8pm)
        if 9 <= hour_of_day <= 20:
            discharge = 2.0  # MW
        else:
            discharge = 0.0
        hourly_discharge.append(discharge)

    # Prices: €40/MWh during day, €25/MWh at night
    hourly_prices = []
    for hour in range(hours_per_year * years):
        hour_of_day = hour % 24
        if 9 <= hour_of_day <= 20:
            price = 40.0
        else:
            price = 25.0
        hourly_prices.append(price)

    annual_revenues = aggregate_annual(hourly_discharge, hourly_prices, years=2)

    print(f"Hourly Data Points:  {len(hourly_discharge):,}")
    print(f"Years:               {years}")
    print("\nAggregated Annual Revenues:")
    for year, revenue in enumerate(annual_revenues, 1):
        print(f"  Year {year}:  €{revenue:,.0f}")

    # Total energy discharged
    annual_energy = aggregate_annual(hourly_discharge, years=2)
    print("\nAnnual Energy Discharged:")
    for year, energy in enumerate(annual_energy, 1):
        print(f"  Year {year}:  {energy:,.0f} MWh")

    # Example 5: Sensitivity Analysis
    print("\n5. NPV SENSITIVITY TO DISCOUNT RATE")
    print("-" * 80)

    discount_rates = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08]

    print(f"{'Discount Rate':<20} {'NPV':>15}")
    print("-" * 40)

    for rate in discount_rates:
        npv = calculate_npv(annual_cash_flows, rate, initial_investment)
        print(f"{rate*100:>6.1f}%              €{npv:>12,.0f}")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
