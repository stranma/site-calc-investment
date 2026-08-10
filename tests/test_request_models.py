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
        )

        assert params.discount_rate == 0.05
        assert params.project_lifetime_years == 10

    def test_investment_params_removed_fields_rejected(self):
        """Removed per-device dicts must fail loudly (moved onto devices)."""
        with pytest.raises(ValueError):
            InvestmentParameters(
                discount_rate=0.05,
                project_lifetime_years=10,
                device_capital_costs={"Battery1": 500000},
            )
        with pytest.raises(ValueError):
            InvestmentParameters(
                discount_rate=0.05,
                project_lifetime_years=10,
                device_annual_opex={"Battery1": 5000},
            )
        with pytest.raises(ValueError):
            InvestmentParameters(
                discount_rate=0.05,
                project_lifetime_years=10,
                price_escalation_rate=0.02,
            )
        with pytest.raises(ValueError):
            InvestmentParameters(
                discount_rate=0.05,
                project_lifetime_years=10,
                investment_budget=1_000_000,
            )

    def test_investment_params_lifetime_required(self):
        """project_lifetime_years is required."""
        with pytest.raises(ValueError):
            InvestmentParameters(discount_rate=0.05)


class TestOptimizationConfig:
    """Tests for OptimizationConfig model."""

    def test_optimization_config_defaults(self):
        """Test default optimization config."""
        config = OptimizationConfig()

        assert config.objective == "maximize_profit"
        assert config.time_limit_seconds == 300
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
        """Test timeout validation (max 15 minutes for investment)."""
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

        # Client-only investment blocks are stripped from every device
        for device in api_dict["sites"][0]["devices"]:
            assert "investment" not in device


class TestWireFormat:
    """Wire-shape tests: the payload must match the server's request schema exactly."""

    def _make_request(self, devices, prague_tz):
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        timespan = TimeSpanInvestment(start=start, intervals=8760, resolution=Resolution.HOUR_1)
        site = Site(site_id="wire_site", devices=devices)
        return InvestmentPlanningRequest(sites=[site], timespan=timespan)

    def test_battery_power_sizing_survives_as_nested_dict(self, prague_tz):
        """Battery power_sizing dumps to the exact reservation wire shape."""
        from site_calc_investment.models import Battery, BatteryProperties, CapacityReservation, CapacityTariff

        battery = Battery(
            name="BESS",
            properties=BatteryProperties(
                capacity=8.0,
                max_power=10.0,
                efficiency=0.92,
                power_sizing=CapacityReservation(
                    periods="horizon",
                    tariffs=[CapacityTariff(name="capex", reserved_price=95_000.0, peak_price=0.0)],
                ),
            ),
        )
        api_dict = self._make_request([battery], prague_tz).model_dump_for_api()

        wire = api_dict["sites"][0]["devices"][0]
        assert wire["type"] == "battery"
        sizing = wire["properties"]["power_sizing"]
        assert sizing == {
            "periods": "horizon",
            "tariffs": [{"name": "capex", "reserved_price": 95_000.0, "peak_price": 0.0, "fixed_price": 0.0}],
            "reserved": None,
            "min_reserved": 0.0,
            "max_reserved": None,
            "timezone": None,
        }

    def test_cz_distribution_import_converts_to_electricity_import(self, prague_tz):
        """The CZ sugar device serializes as electricity_import + monthly reservation."""
        from site_calc_investment.models import CzDistributionImport
        from site_calc_investment.models.devices import CzDistributionImportProperties

        cz = CzDistributionImport(
            name="DSO",
            properties=CzDistributionImportProperties(
                price=[85.0] * 8760,
                max_import=10.0,
                t1_reserved_price=86_000.0,
                t1_peak_price=30_000.0,
                t2_reserved_price=65_000.0,
                t2_peak_price=95_000.0,
                reserved_capacity=5.0,
            ),
        )
        api_dict = self._make_request([cz], prague_tz).model_dump_for_api()

        wire = api_dict["sites"][0]["devices"][0]
        assert wire["name"] == "DSO"
        assert wire["type"] == "electricity_import"
        assert wire["properties"]["max_import"] == 10.0
        assert wire["properties"]["price"] == [85.0] * 8760
        reservation = wire["properties"]["capacity_reservation"]
        assert reservation == {
            "periods": "calendar_month",
            "tariffs": [
                {"name": "T1", "reserved_price": 86_000.0, "peak_price": 30_000.0, "fixed_price": 0.0},
                {"name": "T2", "reserved_price": 65_000.0, "peak_price": 95_000.0, "fixed_price": 0.0},
            ],
            "reserved": 5.0,
            "min_reserved": 0.0,
            "max_reserved": None,
            "timezone": "Europe/Prague",
        }

    def test_in_memory_model_keeps_cz_identity(self, prague_tz):
        """The sugar conversion happens only at the wire boundary."""
        from site_calc_investment.models import CzDistributionImport
        from site_calc_investment.models.devices import CzDistributionImportProperties

        cz = CzDistributionImport(
            name="DSO",
            properties=CzDistributionImportProperties(
                price=[85.0] * 8760,
                max_import=10.0,
                t1_reserved_price=86_000.0,
                t1_peak_price=30_000.0,
                t2_reserved_price=65_000.0,
                t2_peak_price=95_000.0,
                reserved_capacity=5.0,
            ),
        )
        request = self._make_request([cz], prague_tz)
        request.model_dump_for_api()

        # The request object itself is untouched
        assert request.sites[0].devices[0].type == "cz_distribution_import"
        assert request.model_dump()["sites"][0]["devices"][0]["type"] == "cz_distribution_import"
