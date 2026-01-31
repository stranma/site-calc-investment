"""Tests for request models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from site_calc_investment.models.common import Resolution, TimeSpan
from site_calc_investment.models.requests import (
    InvestmentParameters,
    InvestmentPlanningRequest,
    OptimizationConfig,
    Site,
    TimeSpanInvestment,
)


class TestSite:
    """Tests for Site model."""

    def test_site_creation(self, simple_site):
        """Test basic site creation."""
        assert simple_site.site_id == "test_site"
        assert simple_site.description == "Test site for investment planning"
        assert len(simple_site.devices) == 3

    def test_site_unique_device_names(self, battery_10mw, grid_import):
        """Test that device names must be unique."""
        # Create duplicate name
        battery_dup = battery_10mw.model_copy()
        battery_dup.name = "Battery1"
        grid_import.name = "Battery1"  # Duplicate!

        with pytest.raises(ValueError, match="unique"):
            Site(site_id="test", devices=[battery_10mw, battery_dup])

    def test_site_requires_at_least_one_device(self):
        """Test that site requires at least one device."""
        with pytest.raises(ValueError):
            Site(site_id="test", devices=[])


class TestInvestmentParameters:
    """Tests for InvestmentParameters model."""

    def test_investment_params_creation(self):
        """Test basic investment parameters creation."""
        params = InvestmentParameters(
            discount_rate=0.05,
            project_lifetime_years=10,
            device_capital_costs={"Battery1": 500000},
            device_annual_opex={"Battery1": 5000},
        )

        assert params.discount_rate == 0.05
        assert params.project_lifetime_years == 10
        assert params.device_capital_costs["Battery1"] == 500000
        assert params.device_annual_opex["Battery1"] == 5000

    def test_investment_params_price_escalation(self):
        """Test price escalation rate."""
        params = InvestmentParameters(
            discount_rate=0.05,
            project_lifetime_years=10,
            price_escalation_rate=0.02,  # 2% annual
        )

        assert params.price_escalation_rate == 0.02

    def test_investment_params_optional_fields(self):
        """Test that CAPEX and OPEX are optional."""
        params = InvestmentParameters(discount_rate=0.05, project_lifetime_years=10)

        assert params.device_capital_costs is None
        assert params.device_annual_opex is None


class TestOptimizationConfig:
    """Tests for OptimizationConfig model."""

    def test_optimization_config_defaults(self):
        """Test default optimization config."""
        config = OptimizationConfig()

        assert config.objective == "maximize_profit"
        assert config.time_limit_seconds == 3600
        assert config.relax_binary_variables is True

    def test_optimization_config_objectives(self):
        """Test different objectives."""
        config1 = OptimizationConfig(objective="maximize_profit")
        config2 = OptimizationConfig(objective="maximize_self_consumption")
        config3 = OptimizationConfig(objective="minimize_cost")

        assert config1.objective == "maximize_profit"
        assert config2.objective == "maximize_self_consumption"
        assert config3.objective == "minimize_cost"

    def test_optimization_config_timeout_validation(self):
        """Test timeout validation (max 1 hour for investment)."""
        # Valid
        OptimizationConfig(time_limit_seconds=3600)

        # Invalid: exceeds limit
        with pytest.raises(ValueError):
            OptimizationConfig(time_limit_seconds=3601)

        # Invalid: negative
        with pytest.raises(ValueError):
            OptimizationConfig(time_limit_seconds=0)


class TestTimeSpanInvestment:
    """Tests for TimeSpanInvestment model (investment-specific validation)."""

    def test_timespan_investment_creation(self, prague_tz):
        """Test basic TimeSpanInvestment creation."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        ts = TimeSpanInvestment(
            start=start,
            intervals=8760,  # 1 year
            resolution=Resolution.HOUR_1,
        )

        assert ts.intervals == 8760
        assert ts.resolution == Resolution.HOUR_1

    def test_timespan_investment_max_intervals(self, prague_tz):
        """Test investment client interval limit (100,000)."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)

        # Valid: exactly at limit
        TimeSpanInvestment(start=start, intervals=100_000, resolution=Resolution.HOUR_1)

        # Invalid: exceeds limit
        with pytest.raises(ValidationError, match="less than or equal to 100000"):
            TimeSpanInvestment(start=start, intervals=100_001, resolution=Resolution.HOUR_1)

    def test_timespan_investment_only_1h_resolution(self, prague_tz):
        """Test that investment client only supports 1-hour resolution."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)

        # Valid: 1-hour
        TimeSpanInvestment(start=start, intervals=24, resolution=Resolution.HOUR_1)

        # Invalid: 15-minute not allowed
        with pytest.raises(ValidationError, match="literal_error"):
            TimeSpanInvestment(start=start, intervals=96, resolution=Resolution.MINUTES_15)

    def test_timespan_investment_for_years(self):
        """Test for_years factory for investment."""
        # Note: TimeSpanInvestment inherits from TimeSpan
        # We need to use the base class method then validate
        base_ts = TimeSpan.for_years(2025, 10)

        # Convert to investment timespan
        ts = TimeSpanInvestment(start=base_ts.start, intervals=base_ts.intervals, resolution=base_ts.resolution)

        assert ts.intervals == 87600
        assert abs(ts.years - 10.0) < 0.01


class TestInvestmentPlanningRequest:
    """Tests for InvestmentPlanningRequest model."""

    def test_investment_planning_request_creation(self, simple_site, prague_tz, investment_params, optimization_config):
        """Test basic request creation."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        timespan = TimeSpanInvestment(start=start, intervals=87600, resolution=Resolution.HOUR_1)

        request = InvestmentPlanningRequest(
            sites=[simple_site],
            timespan=timespan,
            investment_parameters=investment_params,
            optimization_config=optimization_config,
        )

        assert len(request.sites) == 1
        assert request.timespan.intervals == 87600
        assert request.investment_parameters.discount_rate == 0.05
        assert request.optimization_config.objective == "maximize_profit"

    def test_investment_planning_request_optional_params(self, simple_site, prague_tz):
        """Test request with optional parameters."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        timespan = TimeSpanInvestment(start=start, intervals=8760, resolution=Resolution.HOUR_1)

        # Investment parameters optional
        request = InvestmentPlanningRequest(sites=[simple_site], timespan=timespan)

        assert request.investment_parameters is None
        # Config should have defaults
        assert request.optimization_config.objective == "maximize_profit"

    def test_investment_planning_request_site_limit(self, simple_site, prague_tz):
        """Test maximum sites limit (50)."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        timespan = TimeSpanInvestment(start=start, intervals=8760, resolution=Resolution.HOUR_1)

        # Valid: 50 sites
        many_sites = []
        for i in range(50):
            site = simple_site.model_copy()
            site.site_id = f"site_{i}"
            many_sites.append(site)

        request = InvestmentPlanningRequest(sites=many_sites, timespan=timespan)
        assert len(request.sites) == 50

        # Invalid: 51 sites
        too_many_sites = many_sites + [simple_site.model_copy()]
        with pytest.raises(ValueError):
            InvestmentPlanningRequest(sites=too_many_sites, timespan=timespan)

    def test_investment_planning_request_to_api_dict(self, simple_site, prague_tz, investment_params):
        """Test conversion to API format."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        timespan = TimeSpanInvestment(start=start, intervals=8760, resolution=Resolution.HOUR_1)

        request = InvestmentPlanningRequest(
            sites=[simple_site], timespan=timespan, investment_parameters=investment_params
        )

        api_dict = request.model_dump_for_api()

        # Check timespan converted to API format
        assert "timespan" in api_dict
        assert "period_start" in api_dict["timespan"]
        assert "period_end" in api_dict["timespan"]
        assert "resolution" in api_dict["timespan"]

        # Check sites included
        assert "sites" in api_dict
        assert len(api_dict["sites"]) == 1
