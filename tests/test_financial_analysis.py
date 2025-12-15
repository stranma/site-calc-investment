"""Tests for financial analysis functions."""

import pytest
from site_calc_investment.analysis.financial import (
    calculate_npv,
    calculate_irr,
    calculate_payback_period,
    aggregate_annual,
)


class TestCalculateNPV:
    """Tests for NPV calculation."""

    def test_npv_basic(self):
        """Test basic NPV calculation."""
        cash_flows = [100, 100, 100]
        discount_rate = 0.1
        initial_investment = -250

        npv = calculate_npv(cash_flows, discount_rate, initial_investment)

        # Manual calculation:
        # NPV = -250 + 100/1.1 + 100/1.1^2 + 100/1.1^3
        #     = -250 + 90.91 + 82.64 + 75.13 = -1.32
        assert abs(npv - (-1.32)) < 0.01

    def test_npv_positive(self):
        """Test positive NPV (profitable investment)."""
        cash_flows = [200, 200, 200]
        discount_rate = 0.05
        initial_investment = -500

        npv = calculate_npv(cash_flows, discount_rate, initial_investment)

        # Should be positive (profitable)
        assert npv > 0

    def test_npv_zero_discount_rate(self):
        """Test NPV with zero discount rate."""
        cash_flows = [100, 100, 100]
        discount_rate = 0.0
        initial_investment = -250

        npv = calculate_npv(cash_flows, discount_rate, initial_investment)

        # With 0% discount: NPV = -250 + 300 = 50
        assert npv == 50.0

    def test_npv_10_years(self):
        """Test NPV with 10-year cash flows."""
        cash_flows = [100_000] * 10
        discount_rate = 0.05
        initial_investment = -500_000

        npv = calculate_npv(cash_flows, discount_rate, initial_investment)

        # NPV should be positive
        assert npv > 0
        # Approximate check
        assert 250_000 < npv < 300_000


class TestCalculateIRR:
    """Tests for IRR calculation."""

    def test_irr_basic(self):
        """Test basic IRR calculation."""
        # Investment that returns 10% IRR
        cash_flows = [-1000, 100, 100, 100, 100, 100, 100, 100, 100, 100, 1100]

        irr = calculate_irr(cash_flows)

        # Should be approximately 10%
        assert irr is not None
        assert abs(irr - 0.10) < 0.01

    def test_irr_exact_case(self):
        """Test IRR with known exact solution."""
        # Simple case: invest 100, get 110 next year
        # IRR should be exactly 10%
        cash_flows = [-100, 110]

        irr = calculate_irr(cash_flows)

        assert irr is not None
        assert abs(irr - 0.10) < 0.001

    def test_irr_no_solution(self):
        """Test IRR when no solution exists."""
        # All positive cash flows (no investment)
        cash_flows = [100, 100, 100]

        irr = calculate_irr(cash_flows)

        # Should return None (no meaningful IRR)
        # Note: This depends on implementation, may return inf or None
        assert irr is None or irr > 10  # If not None, should be very high

    def test_irr_negative_return(self):
        """Test IRR with negative returns."""
        # Invest 1000, lose money every year
        cash_flows = [-1000, -100, -100, -100]

        irr = calculate_irr(cash_flows)

        # Should be very negative or None
        assert irr is None or irr < -0.5

    def test_irr_high_return(self):
        """Test IRR with high returns."""
        cash_flows = [-100, 200]  # 100% return

        irr = calculate_irr(cash_flows)

        assert irr is not None
        assert abs(irr - 1.0) < 0.01  # 100% IRR


class TestCalculatePaybackPeriod:
    """Tests for payback period calculation."""

    def test_payback_basic(self):
        """Test basic payback calculation."""
        cash_flows = [-1000, 300, 300, 300, 300]

        payback = calculate_payback_period(cash_flows)

        # Payback after year 3 + fraction of year 4
        # After 3 years: -1000 + 900 = -100
        # Year 4: need 100 out of 300 = 0.33
        # Total: 3.33 years
        assert payback is not None
        assert abs(payback - 3.33) < 0.01

    def test_payback_exact(self):
        """Test exact payback at year boundary."""
        cash_flows = [-1000, 500, 500]

        payback = calculate_payback_period(cash_flows)

        # Exactly 2 years
        assert payback is not None
        assert abs(payback - 2.0) < 0.01

    def test_payback_first_year(self):
        """Test payback in first year."""
        cash_flows = [-1000, 1500]

        payback = calculate_payback_period(cash_flows)

        # Fraction of first year
        assert payback is not None
        assert 0 < payback < 1

    def test_payback_never(self):
        """Test when investment never pays back."""
        cash_flows = [-1000, 100, 100, 100]

        payback = calculate_payback_period(cash_flows)

        # Never pays back
        assert payback is None

    def test_payback_immediate(self):
        """Test immediate payback."""
        cash_flows = [0, 100]

        payback = calculate_payback_period(cash_flows)

        # Immediate (year 0)
        assert payback == 0.0


class TestAggregateAnnual:
    """Tests for aggregate_annual function."""

    def test_aggregate_annual_energy(self):
        """Test aggregating hourly energy to annual."""
        # Constant 1 MW for 1 year
        hourly_values = [1.0] * 8760

        annual = aggregate_annual(hourly_values, years=1)

        # Should be 8760 MWh
        assert len(annual) == 1
        assert annual[0] == 8760.0

    def test_aggregate_annual_revenue(self):
        """Test aggregating hourly revenue."""
        # 2 MW discharge at €30/MWh
        hourly_power = [2.0] * 8760
        hourly_prices = [30.0] * 8760

        annual = aggregate_annual(hourly_power, hourly_prices, years=1)

        # Revenue = 2 MW × €30/MWh × 8760 hours = €525,600
        assert len(annual) == 1
        assert abs(annual[0] - 525_600.0) < 1.0

    def test_aggregate_annual_10_years(self):
        """Test aggregating 10 years of data."""
        # Variable power over 10 years
        hourly_power = [2.0] * (8760 * 10)
        hourly_prices = [30.0] * (8760 * 10)

        annual = aggregate_annual(hourly_power, hourly_prices, years=10)

        # Should have 10 annual values
        assert len(annual) == 10
        # Each year should be same (constant power/price)
        for year_revenue in annual:
            assert abs(year_revenue - 525_600.0) < 1.0

    def test_aggregate_annual_varying_prices(self):
        """Test with varying prices each year."""
        years = 3
        hourly_power = []
        hourly_prices = []

        # Year 1: €30, Year 2: €35, Year 3: €40
        for year, price in enumerate([30.0, 35.0, 40.0]):
            hourly_power.extend([2.0] * 8760)
            hourly_prices.extend([price] * 8760)

        annual = aggregate_annual(hourly_power, hourly_prices, years=years)

        # Year 1: 2 × 30 × 8760 = 525,600
        # Year 2: 2 × 35 × 8760 = 613,200
        # Year 3: 2 × 40 × 8760 = 700,800
        assert abs(annual[0] - 525_600.0) < 1.0
        assert abs(annual[1] - 613_200.0) < 1.0
        assert abs(annual[2] - 700_800.0) < 1.0

    def test_aggregate_annual_length_validation(self):
        """Test length validation."""
        # Wrong length
        hourly_values = [1.0] * 100

        with pytest.raises(ValueError, match="Expected"):
            aggregate_annual(hourly_values, years=1)

    def test_aggregate_annual_price_length_mismatch(self):
        """Test price length must match values length."""
        hourly_values = [1.0] * 8760
        hourly_prices = [30.0] * 100  # Wrong length

        with pytest.raises(ValueError, match="doesn't match"):
            aggregate_annual(hourly_values, hourly_prices, years=1)

    def test_aggregate_annual_zero_values(self):
        """Test with zero power (no generation)."""
        hourly_values = [0.0] * 8760
        hourly_prices = [30.0] * 8760

        annual = aggregate_annual(hourly_values, hourly_prices, years=1)

        # Zero revenue
        assert annual[0] == 0.0


class TestFinancialAnalysisIntegration:
    """Integration tests combining multiple financial functions."""

    def test_typical_battery_investment(self):
        """Test typical battery investment analysis."""
        # 10-year battery investment
        initial_capex = -2_000_000  # €2M
        annual_revenue = [450_000, 460_000, 470_000, 480_000, 490_000,
                          500_000, 510_000, 520_000, 530_000, 540_000]
        annual_costs = [180_000, 185_000, 190_000, 195_000, 200_000,
                        205_000, 210_000, 215_000, 220_000, 225_000]
        annual_cash_flows = [r - c for r, c in zip(annual_revenue, annual_costs)]

        # NPV at 5%
        npv = calculate_npv(annual_cash_flows, 0.05, initial_capex)
        assert npv > 0  # Should be profitable

        # IRR
        cash_flows_with_capex = [initial_capex] + annual_cash_flows
        irr = calculate_irr(cash_flows_with_capex)
        assert irr is not None
        assert 0.05 < irr < 0.20  # Reasonable range

        # Payback
        payback = calculate_payback_period(cash_flows_with_capex)
        assert payback is not None
        assert 5 < payback < 10  # Should pay back within 10 years

    def test_unprofitable_investment(self):
        """Test unprofitable investment."""
        initial_capex = -2_000_000
        annual_cash_flows = [50_000] * 10  # Not enough to cover CAPEX

        # NPV should be negative
        npv = calculate_npv(annual_cash_flows, 0.05, initial_capex)
        assert npv < 0

        # Payback should be None or very long
        cash_flows_with_capex = [initial_capex] + annual_cash_flows
        payback = calculate_payback_period(cash_flows_with_capex)
        assert payback is None or payback > 10
