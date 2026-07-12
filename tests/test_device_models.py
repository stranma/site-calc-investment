"""Tests for device models."""

import pytest
from pydantic import ValidationError

from site_calc_investment.models.devices import (
    CHP,
    Battery,
    BatteryProperties,
    CHPProperties,
    DemandProperties,
    ElectricityDemand,
    ElectricityExport,
    ElectricityImport,
    FixedConsumption,
    FixedProduction,
    FixedProfileProperties,
    GasImport,
    HeatAccumulator,
    HeatAccumulatorProperties,
    HeatDemand,
    HeatExport,
    MarketExportProperties,
    MarketImportProperties,
    MaxPowerConsumption,
    MaxPowerConsumptionProperties,
    MaxPowerProduction,
    MaxPowerProductionProperties,
    PhotovoltaicNonSteerable,
    PhotovoltaicSteerable,
    PhotovoltaicSteerableProperties,
    Schedule,
)


class TestBattery:
    """Tests for Battery device."""

    def test_battery_creation(self):
        """Test basic battery creation."""
        battery = Battery(
            name="Battery1",
            properties=BatteryProperties(capacity=10.0, max_power=5.0, efficiency=0.90, initial_soc=0.5),
        )

        assert battery.name == "Battery1"
        assert battery.type == "battery"
        assert battery.properties.capacity == 10.0
        assert battery.properties.max_power == 5.0
        assert battery.properties.efficiency == 0.90
        assert battery.properties.initial_soc == 0.5

    def test_battery_no_ancillary_services_field(self):
        """Test that Battery has NO ancillary_services field."""
        battery = Battery(
            name="Battery1",
            properties=BatteryProperties(capacity=10.0, max_power=5.0, efficiency=0.90, initial_soc=0.5),
        )

        # Should not have ancillary_services attribute
        assert not hasattr(battery, "ancillary_services")

    def test_battery_with_schedule(self):
        """Test battery with operational schedule."""
        battery = Battery(
            name="Battery1",
            properties=BatteryProperties(capacity=10.0, max_power=5.0, efficiency=0.90, initial_soc=0.5),
            schedule=Schedule(max_hours_per_day=20.0),
        )

        assert battery.schedule is not None
        assert battery.schedule.max_hours_per_day == 20.0

    def test_battery_properties_validation(self):
        """Test battery properties validation."""
        # Positive values required
        with pytest.raises(ValidationError):
            BatteryProperties(
                capacity=-10.0,  # Invalid
                max_power=5.0,
                efficiency=0.90,
                initial_soc=0.5,
            )

        # Efficiency must be <= 1
        with pytest.raises(ValidationError):
            BatteryProperties(
                capacity=10.0,
                max_power=5.0,
                efficiency=1.5,  # Invalid
                initial_soc=0.5,
            )

        # SOC must be 0-1
        with pytest.raises(ValidationError):
            BatteryProperties(
                capacity=10.0,
                max_power=5.0,
                efficiency=0.90,
                initial_soc=1.5,  # Invalid
            )


class TestCHP:
    """Tests for CHP device."""

    def test_chp_creation(self):
        """Test basic CHP creation."""
        chp = CHP(name="CHP1", properties=CHPProperties(gas_input=8.0, el_output=3.0, heat_output=4.0, is_binary=False))

        assert chp.name == "CHP1"
        assert chp.type == "chp"
        assert chp.properties.gas_input == 8.0
        assert chp.properties.el_output == 3.0
        assert chp.properties.heat_output == 4.0
        assert chp.properties.is_binary is False

    def test_chp_binary_flag(self):
        """Test CHP binary flag (note: auto-relaxed in investment client)."""
        chp_binary = CHP(
            name="CHP1",
            properties=CHPProperties(
                gas_input=8.0,
                el_output=3.0,
                heat_output=4.0,
                is_binary=True,  # Will be relaxed by solver
            ),
        )

        # Flag is stored but will be ignored by optimization
        assert chp_binary.properties.is_binary is True

    def test_chp_min_power(self):
        """Test CHP with min_power constraint."""
        chp = CHP(
            name="CHP1",
            properties=CHPProperties(
                gas_input=8.0,
                el_output=3.0,
                heat_output=4.0,
                is_binary=False,
                min_power=0.5,  # 50% minimum
            ),
        )

        assert chp.properties.min_power == 0.5


class TestHeatAccumulator:
    """Tests for HeatAccumulator device."""

    def test_heat_accumulator_creation(self):
        """Test basic heat accumulator creation."""
        ha = HeatAccumulator(
            name="HeatAcc1",
            properties=HeatAccumulatorProperties(
                capacity=5.0, max_power=2.0, efficiency=0.98, initial_soc=0.6, loss_rate=0.001
            ),
        )

        assert ha.name == "HeatAcc1"
        assert ha.type == "heat_accumulator"
        assert ha.properties.loss_rate == 0.001


class TestPhotovoltaicDevices:
    """Tests for the steerable/nonsteerable photovoltaic devices."""

    def test_photovoltaic_nonsteerable_creation(self):
        """Nonsteerable PV produces exactly its power profile."""
        profile = [0.0, 1.2, 3.5, 4.8, 3.1, 0.0]
        pv = PhotovoltaicNonSteerable(
            name="PV1",
            properties=FixedProfileProperties(power_profile=profile),
        )

        assert pv.name == "PV1"
        assert pv.type == "photovoltaic_nonsteerable"
        assert pv.properties.power_profile == profile

    def test_photovoltaic_steerable_creation(self):
        """Steerable PV takes a max-power profile."""
        profile = [0.0, 1.2, 3.5, 4.8, 3.1, 0.0]
        pv = PhotovoltaicSteerable(
            name="PV2",
            properties=PhotovoltaicSteerableProperties(max_power_profile=profile),
        )

        assert pv.type == "photovoltaic_steerable"
        assert pv.properties.max_power_profile == profile

    def test_photovoltaic_profile_must_be_non_negative(self):
        """PV profiles must be non-negative."""
        with pytest.raises(ValidationError, match="non-negative"):
            FixedProfileProperties(power_profile=[1.0, -0.5])
        with pytest.raises(ValidationError, match="non-negative"):
            PhotovoltaicSteerableProperties(max_power_profile=[-1.0])


class TestProfileDevices:
    """Tests for the fixed/max-power production and consumption devices."""

    def test_fixed_production_creation(self):
        device = FixedProduction(
            name="Gen1",
            properties=FixedProfileProperties(power_profile=[1.0, 1.5, 2.0]),
        )

        assert device.type == "fixed_production"
        assert device.properties.power_profile == [1.0, 1.5, 2.0]

    def test_fixed_consumption_creation(self):
        device = FixedConsumption(
            name="Load1",
            properties=FixedProfileProperties(power_profile=[0.5, 0.8, 1.0]),
        )

        assert device.type == "fixed_consumption"
        assert device.properties.power_profile == [0.5, 0.8, 1.0]

    def test_max_power_production_creation(self):
        device = MaxPowerProduction(
            name="Gen2",
            properties=MaxPowerProductionProperties(max_power_profile=[2.0] * 4, cost_per_mwh=30.0),
        )

        assert device.type == "max_power_production"
        assert device.properties.cost_per_mwh == 30.0

    def test_max_power_production_cost_defaults_to_zero(self):
        device = MaxPowerProduction(
            name="Gen2",
            properties=MaxPowerProductionProperties(max_power_profile=[2.0] * 4),
        )

        assert device.properties.cost_per_mwh == 0

    def test_max_power_consumption_creation(self):
        device = MaxPowerConsumption(
            name="FlexLoad",
            properties=MaxPowerConsumptionProperties(max_power_profile=[3.0] * 4, value_per_mwh=50.0),
        )

        assert device.type == "max_power_consumption"
        assert device.properties.value_per_mwh == 50.0

    def test_max_power_consumption_requires_value(self):
        """value_per_mwh is required -- a value-less flexible load would never run."""
        with pytest.raises(ValidationError):
            MaxPowerConsumptionProperties(max_power_profile=[3.0] * 4)

    def test_profile_must_be_non_negative(self):
        with pytest.raises(ValidationError, match="non-negative"):
            MaxPowerProductionProperties(max_power_profile=[2.0, -1.0])
        with pytest.raises(ValidationError, match="non-negative"):
            MaxPowerConsumptionProperties(max_power_profile=[-2.0], value_per_mwh=50.0)

    def test_empty_profile_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            FixedProfileProperties(power_profile=[])
        with pytest.raises(ValidationError, match="must not be empty"):
            MaxPowerProductionProperties(max_power_profile=[])
        with pytest.raises(ValidationError, match="must not be empty"):
            MaxPowerConsumptionProperties(max_power_profile=[], value_per_mwh=50.0)
        with pytest.raises(ValidationError, match="must not be empty"):
            PhotovoltaicSteerableProperties(max_power_profile=[])

    def test_negative_rates_rejected(self):
        with pytest.raises(ValidationError):
            MaxPowerProductionProperties(max_power_profile=[2.0], cost_per_mwh=-10.0)
        with pytest.raises(ValidationError):
            MaxPowerConsumptionProperties(max_power_profile=[2.0], value_per_mwh=-10.0)


class TestDemandDevices:
    """Tests for demand devices."""

    def test_heat_demand_creation(self):
        """Test heat demand creation."""
        demand = HeatDemand(
            name="HeatDemand1",
            properties=DemandProperties(max_demand_profile=[2.0, 1.8, 1.5], min_demand_profile=[2.0, 1.8, 1.5]),
        )

        assert demand.name == "HeatDemand1"
        assert demand.type == "heat_demand"
        assert len(demand.properties.max_demand_profile) == 3

    def test_electricity_demand_creation(self):
        """Test electricity demand creation."""
        demand = ElectricityDemand(
            name="ElecDemand1",
            properties=DemandProperties(
                max_demand_profile=[3.0] * 24,
                min_demand_profile=2.0,  # Constant minimum
            ),
        )

        assert demand.type == "electricity_demand"
        assert demand.properties.min_demand_profile == 2.0

    def test_demand_validation_positive(self):
        """Test demand values must be non-negative."""
        with pytest.raises(ValidationError):
            DemandProperties(
                max_demand_profile=[-1.0, 2.0, 3.0],  # Invalid: negative
                min_demand_profile=0.0,
            )


class TestMarketDevices:
    """Tests for market interface devices."""

    def test_electricity_import_creation(self):
        """Test electricity import device."""
        prices = [30.0] * 24
        device = ElectricityImport(name="GridImport", properties=MarketImportProperties(price=prices, max_import=8.0))

        assert device.type == "electricity_import"
        assert device.properties.max_import == 8.0
        assert len(device.properties.price) == 24

    def test_electricity_export_creation(self):
        """Test electricity export device."""
        prices = [30.0] * 24
        device = ElectricityExport(name="GridExport", properties=MarketExportProperties(price=prices, max_export=5.0))

        assert device.type == "electricity_export"
        assert device.properties.max_export == 5.0

    def test_gas_import_creation(self):
        """Test gas import device."""
        prices = [25.0] * 24
        device = GasImport(name="GasSupply", properties=MarketImportProperties(price=prices, max_import=10.0))

        assert device.type == "gas_import"

    def test_heat_export_creation(self):
        """Test heat export device."""
        prices = [40.0] * 24
        device = HeatExport(name="HeatExport", properties=MarketExportProperties(price=prices, max_export=3.0))

        assert device.type == "heat_export"

    def test_market_device_with_unit_cost(self):
        """Test market device with capacity cost."""
        prices = [30.0] * 24
        device = ElectricityImport(
            name="GridImport",
            properties=MarketImportProperties(
                price=prices,
                max_import=8.0,
                max_import_unit_cost=144.0,  # EUR/MW/year
            ),
        )

        assert device.properties.max_import_unit_cost == 144.0


class TestSchedule:
    """Tests for Schedule model."""

    def test_schedule_creation(self):
        """Test basic schedule creation."""
        schedule = Schedule(min_continuous_run_hours=2.0, max_hours_per_day=18.0, max_starts_per_day=3)

        assert schedule.min_continuous_run_hours == 2.0
        assert schedule.max_hours_per_day == 18.0
        assert schedule.max_starts_per_day == 3

    def test_schedule_can_run_validation(self):
        """Test can_run array validation."""
        # Valid 24-hour array
        Schedule(can_run=[1] * 24)

        # Valid 96-interval array
        Schedule(can_run=[0, 1] * 48)

        # Invalid length
        with pytest.raises(ValidationError, match="24.*or 96"):
            Schedule(can_run=[1] * 10)

        # Invalid values
        with pytest.raises(ValidationError, match="between 0 and 1"):
            Schedule(can_run=[2] * 24)  # Must be 0-1

    def test_schedule_must_run_validation(self):
        """Test must_run array validation."""
        # Valid binary array
        Schedule(must_run=[0, 1, 0, 1] * 6)  # 24 values

        # Invalid values (must be 0 or 1, not fractional)
        with pytest.raises(ValidationError, match="int_from_float"):
            Schedule(must_run=[0.5] * 24)

    def test_schedule_fractional_can_run_for_pv(self):
        """Test can_run allows fractional values (for PV generation)."""
        # Note: This will fail validation because 100 != 24 or 96
        # Let's fix it:
        with pytest.raises(ValidationError):
            Schedule(can_run=[0.0, 0.2, 0.5, 0.8, 1.0] * 20)  # 100 values (will fail)

        # Correct: 24 values with fractions
        schedule = Schedule(
            can_run=[0.0] * 6 + [0.2, 0.5, 0.8, 1.0] * 4 + [0.5] * 2  # = 24
        )
        assert schedule.can_run[0] == 0.0
        assert schedule.can_run[6] == 0.2
