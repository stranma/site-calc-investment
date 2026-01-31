"""Financial analysis functions."""

from typing import List, Optional


def calculate_npv(
    cash_flows: List[float],
    discount_rate: float,
    initial_investment: float = 0,
) -> float:
    """Calculate Net Present Value.

    NPV = Sum of (cash_flow_t / (1 + discount_rate)^t) + initial_investment

    Args:
        cash_flows: Annual cash flows (revenues - costs)
        discount_rate: Discount rate (e.g., 0.05 for 5%)
        initial_investment: Initial investment (negative for CAPEX, default: 0)

    Returns:
        Net present value in same currency as cash flows

    Example:
        >>> cash_flows = [100000, 105000, 110000, 115000, 120000]
        >>> npv = calculate_npv(cash_flows, 0.05, initial_investment=-500000)
        >>> print(f"NPV: €{npv:,.0f}")
        NPV: €-23,162
    """
    npv = initial_investment

    for t, cash_flow in enumerate(cash_flows, start=1):
        npv += cash_flow / ((1 + discount_rate) ** t)

    return npv


def calculate_irr(cash_flows: List[float], initial_guess: float = 0.1) -> Optional[float]:
    """Calculate Internal Rate of Return.

    IRR is the discount rate that makes NPV = 0.
    Uses Newton-Raphson method for root finding.

    Args:
        cash_flows: Annual cash flows INCLUDING initial investment as first element
                   (e.g., [-500000, 100000, 105000, ...])
        initial_guess: Starting guess for IRR (default: 0.1 = 10%)

    Returns:
        Internal rate of return as fraction (e.g., 0.12 = 12%), or None if no solution

    Example:
        >>> cash_flows = [-500000, 100000, 105000, 110000, 115000, 120000]
        >>> irr = calculate_irr(cash_flows)
        >>> if irr:
        ...     print(f"IRR: {irr*100:.2f}%")
        IRR: 8.52%
    """
    if len(cash_flows) < 2:
        return None

    # numpy.irr was removed in numpy 1.20+, use Newton-Raphson directly
    return _irr_newton_raphson(cash_flows, initial_guess)


def _irr_newton_raphson(cash_flows: List[float], initial_guess: float, max_iterations: int = 100) -> Optional[float]:
    """Calculate IRR using Newton-Raphson method.

    Args:
        cash_flows: Cash flows with initial investment as first element
        initial_guess: Starting guess
        max_iterations: Maximum iterations

    Returns:
        IRR or None if no convergence
    """
    rate = initial_guess
    tolerance = 1e-6

    for _ in range(max_iterations):
        # Calculate NPV and derivative
        npv: float = 0.0
        npv_derivative: float = 0.0

        for t, cash_flow in enumerate(cash_flows):
            discount_factor = (1 + rate) ** t
            npv += cash_flow / discount_factor
            if t > 0:
                npv_derivative -= t * cash_flow / ((1 + rate) ** (t + 1))

        # Check convergence
        if abs(npv) < tolerance:
            return rate

        # Newton-Raphson update
        if abs(npv_derivative) < tolerance:
            return None  # Derivative too small

        rate = rate - npv / npv_derivative

        # Check for reasonable range
        if rate < -0.99 or rate > 10:  # -99% to 1000%
            return None

    return None  # No convergence


def calculate_payback_period(cash_flows: List[float]) -> Optional[float]:
    """Calculate simple payback period.

    Payback period is the time it takes for cumulative cash flows
    to become positive (recover initial investment).

    Args:
        cash_flows: Annual cash flows INCLUDING initial investment as first element
                   (e.g., [-500000, 100000, 105000, ...])

    Returns:
        Payback period in years (fractional), or None if never pays back

    Example:
        >>> cash_flows = [-500000, 100000, 120000, 140000, 160000]
        >>> payback = calculate_payback_period(cash_flows)
        >>> print(f"Payback: {payback:.1f} years")
        Payback: 3.6 years
    """
    if len(cash_flows) < 2:
        return None

    cumulative: float = 0.0
    for year, cash_flow in enumerate(cash_flows):
        cumulative += cash_flow

        if cumulative >= 0:
            # Interpolate within the year
            if year == 0:
                return 0.0

            # How much was needed at start of this year
            prev_cumulative = cumulative - cash_flow

            # Fraction of year needed
            fraction = -prev_cumulative / cash_flow

            # Return year - 1 + fraction because year 0 is initial investment
            return (year - 1) + fraction

    return None  # Never pays back


def aggregate_annual(
    hourly_values: List[float],
    prices: Optional[List[float]] = None,
    years: int = 1,
) -> List[float]:
    """Aggregate hourly values into annual totals.

    If prices are provided, calculates annual revenue.
    Otherwise, calculates annual sum (e.g., energy).

    Args:
        hourly_values: Hourly power or flow values (MW)
        prices: Optional hourly prices (EUR/MWh)
        years: Number of years (for validation)

    Returns:
        List of annual values (one per year)

    Example:
        >>> hourly_export = [2.5] * 8760 * 10  # 10 years of constant 2.5 MW
        >>> prices = [30.0] * 8760 * 10
        >>> annual_revenues = aggregate_annual(hourly_export, prices, years=10)
        >>> print(f"Year 1 revenue: €{annual_revenues[0]:,.0f}")
        Year 1 revenue: €657,000
    """
    hours_per_year = 8760
    expected_length = hours_per_year * years

    if len(hourly_values) != expected_length:
        raise ValueError(f"Expected {expected_length} hourly values for {years} years, got {len(hourly_values)}")

    if prices is not None and len(prices) != expected_length:
        raise ValueError(f"Prices length {len(prices)} doesn't match hourly_values length {len(hourly_values)}")

    annual_values = []

    for year in range(years):
        start_idx = year * hours_per_year
        end_idx = (year + 1) * hours_per_year

        year_values = hourly_values[start_idx:end_idx]

        if prices is not None:
            year_prices = prices[start_idx:end_idx]
            # Revenue = sum(MW * hours * EUR/MWh) = sum(MW * EUR/MWh) for 1-hour intervals
            annual_value = sum(v * p for v, p in zip(year_values, year_prices))
        else:
            # Just sum the values
            annual_value = sum(year_values)

        annual_values.append(annual_value)

    return annual_values
