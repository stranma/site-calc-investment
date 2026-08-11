"""Tests for device models."""

import pytest
from pydantic import ValidationError

from site_calc_investment.models.capacity import CapacityReservation, CapacityTariff, DeviceInvestment
from site_calc_investment.models.devices import (
    CHP,
    Battery,
    BatteryProperties,
    CHPProperties,
    CzDistributionImport,
    CzDistributionImportProperties,
    DemandProperties,
    ElectricityDemand,
    ElectricityExport,
    ElectricityImport,
    FixedConsumption,
    FixedProduction,
    FixedProfileProperties,
    GasImport,
    GasImportProperties,
    HeatAccumulator,
    HeatAccumulatorProperties,
    HeatDemand,
    HeatExport,
    HeatExportProperties,
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
        device = GasImport(name="GasSupply", properties=GasImportProperties(price=prices, max_import=10.0))

        assert device.type == "gas_import"

    def test_heat_export_creation(self):
        """Test heat export device."""
        prices = [40.0] * 24
        device = HeatExport(name="HeatExport", properties=HeatExportProperties(price=prices, max_export=3.0))

        assert device.type == "heat_export"

    def test_market_unit_cost_fields_removed(self):
        """The old unit-cost fields must be rejected (use capacity_reservation)."""
        prices = [30.0] * 24
        with pytest.raises(ValidationError):
            MarketImportProperties(price=prices, max_import=8.0, max_import_unit_cost=144.0)
        with pytest.raises(ValidationError):
            MarketExportProperties(price=prices, max_export=8.0, max_export_unit_cost=144.0)

    def test_market_device_with_capacity_reservation(self):
        """Market devices accept a capacity reservation."""
        prices = [30.0] * 24
        device = ElectricityImport(
            name="GridImport",
            properties=MarketImportProperties(
                price=prices,
                max_import=8.0,
                capacity_reservation=CapacityReservation(
                    periods="calendar_month",
                    reserved=5.0,
                    tariffs=[CapacityTariff(name="T1", reserved_price=80_000.0, peak_price=30_000.0)],
                ),
            ),
        )

        assert device.properties.capacity_reservation.reserved == 5.0
        assert device.properties.capacity_reservation.tariffs[0].name == "T1"

    def test_gas_heat_props_reject_capacity_reservation(self):
        """Gas import and heat export do not support capacity reservations."""
        reservation = {"periods": "calendar_month", "reserved": 2.0}
        with pytest.raises(ValidationError):
            GasImportProperties(price=[25.0] * 24, max_import=10.0, capacity_reservation=reservation)
        with pytest.raises(ValidationError):
            HeatExportProperties(price=[40.0] * 24, max_export=3.0, capacity_reservation=reservation)


class TestCapacityReservation:
    """Tests for the CapacityReservation/CapacityTariff models."""

    def test_tariff_defaults_and_validation(self):
        tariff = CapacityTariff(name="T1", reserved_price=80_000.0, peak_price=30_000.0)
        assert tariff.fixed_price == 0.0

        with pytest.raises(ValidationError):
            CapacityTariff(name="", reserved_price=1.0, peak_price=0.0)
        with pytest.raises(ValidationError):
            CapacityTariff(name="T1", reserved_price=-1.0, peak_price=0.0)

    def test_unpriced_limit_requires_fixed_reserved(self):
        """An optimized R needs every tariff to carry a positive reserved price."""
        # No tariffs and no reserved value -> invalid
        with pytest.raises(ValidationError, match="reserved_price"):
            CapacityReservation(periods="calendar_month")
        # Zero reserved_price tariff with optimized R -> invalid
        with pytest.raises(ValidationError, match="reserved_price"):
            CapacityReservation(
                periods="calendar_month",
                tariffs=[CapacityTariff(name="T1", reserved_price=0.0, peak_price=10.0)],
            )
        # Fixed reserved value -> valid even unpriced
        reservation = CapacityReservation(periods="calendar_month", reserved=5.0)
        assert reservation.reserved == 5.0

    def test_bounds_consistency(self):
        with pytest.raises(ValidationError, match="min_reserved cannot exceed"):
            CapacityReservation(periods="horizon", reserved=5.0, min_reserved=6.0, max_reserved=5.5)
        with pytest.raises(ValidationError, match="below min_reserved"):
            CapacityReservation(periods="horizon", reserved=1.0, min_reserved=2.0)
        with pytest.raises(ValidationError, match="exceed max_reserved"):
            CapacityReservation(periods="horizon", reserved=9.0, max_reserved=8.0)

    def test_tariff_menu_size_bounded(self):
        tariffs = [CapacityTariff(name=f"T{i}", reserved_price=1000.0, peak_price=0.0) for i in range(51)]
        with pytest.raises(ValidationError):
            CapacityReservation(periods="calendar_month", tariffs=tariffs, reserved=5.0)

    def test_invalid_periods_and_timezone(self):
        with pytest.raises(ValidationError):
            CapacityReservation(periods="weekly", reserved=5.0)
        with pytest.raises(ValidationError, match="timezone"):
            CapacityReservation(periods="calendar_month", reserved=5.0, timezone="Not/AZone")

    def test_battery_power_sizing_accepted(self):
        props = BatteryProperties(
            capacity=8.0,
            max_power=10.0,
            efficiency=0.92,
            power_sizing=CapacityReservation(
                periods="horizon",
                tariffs=[
                    CapacityTariff(name="string-inverter", reserved_price=95_000.0, peak_price=0.0),
                    CapacityTariff(
                        name="central-inverter", reserved_price=70_000.0, peak_price=0.0, fixed_price=40_000.0
                    ),
                ],
            ),
        )
        assert len(props.power_sizing.tariffs) == 2

    def test_battery_capacity_sizing_full_form_accepted(self):
        """capacity_sizing accepts the full reservation form (menus, calendar periods)."""
        simple = CapacityReservation(
            periods="horizon",
            tariffs=[CapacityTariff(name="capex", reserved_price=30_000.0, peak_price=0.0)],
        )
        props = BatteryProperties(capacity=8.0, max_power=10.0, efficiency=0.92, capacity_sizing=simple)
        assert props.capacity_sizing.tariffs[0].reserved_price == 30_000.0

        rich = CapacityReservation(
            periods="calendar_month",
            tariffs=[
                CapacityTariff(name="a", reserved_price=30_000.0, peak_price=0.0),
                CapacityTariff(name="b", reserved_price=20_000.0, peak_price=0.0, fixed_price=50_000.0),
            ],
            timezone="Europe/Prague",
        )
        props = BatteryProperties(capacity=8.0, max_power=10.0, efficiency=0.92, capacity_sizing=rich)
        assert len(props.capacity_sizing.tariffs) == 2

    def test_battery_optimized_capacity_sizing_defaults_initial_soc_to_zero(self):
        """Sizing runs default initial_soc to 0 (the server rejects free starting energy)."""
        sizing = CapacityReservation(
            periods="horizon",
            tariffs=[CapacityTariff(name="capex", reserved_price=30_000.0, peak_price=0.0)],
        )
        props = BatteryProperties(capacity=8.0, max_power=10.0, efficiency=0.92, capacity_sizing=sizing)
        assert props.initial_soc == 0.0
        # No sizing -> stock default stays
        assert BatteryProperties(capacity=8.0, max_power=10.0, efficiency=0.92).initial_soc == 0.5

    def test_battery_optimized_capacity_sizing_rejects_positive_initial_soc(self):
        """Explicit initial_soc > 0 with an optimizer-sized capacity is rejected."""
        sizing = CapacityReservation(
            periods="horizon",
            tariffs=[CapacityTariff(name="capex", reserved_price=30_000.0, peak_price=0.0)],
        )
        with pytest.raises(ValidationError, match="initial_soc"):
            BatteryProperties(capacity=8.0, max_power=10.0, efficiency=0.92, initial_soc=0.5, capacity_sizing=sizing)

    def test_battery_fixed_capacity_sizing_keeps_initial_soc(self):
        """A fixed reserved capacity keeps the stock initial_soc default and allows > 0."""
        sizing = CapacityReservation(
            periods="horizon",
            tariffs=[CapacityTariff(name="capex", reserved_price=30_000.0, peak_price=0.0)],
            reserved=5.0,
        )
        props = BatteryProperties(capacity=8.0, max_power=10.0, efficiency=0.92, capacity_sizing=sizing)
        assert props.initial_soc == 0.5
        props = BatteryProperties(
            capacity=8.0, max_power=10.0, efficiency=0.92, initial_soc=0.7, capacity_sizing=sizing
        )
        assert props.initial_soc == 0.7

    def test_battery_capacity_sizing_rejects_soc_anchors(self):
        """capacity_sizing is incompatible with SOC anchor points."""
        sizing = CapacityReservation(
            periods="horizon",
            tariffs=[CapacityTariff(name="capex", reserved_price=30_000.0, peak_price=0.0)],
        )
        with pytest.raises(ValidationError, match="anchor"):
            BatteryProperties(
                capacity=8.0,
                max_power=10.0,
                efficiency=0.92,
                soc_anchor_interval_hours=4320,
                capacity_sizing=sizing,
            )


class TestBatteryDegradation:
    """Tests for the yearly degradation curve on BatteryProperties."""

    def _props(self, **extra):
        return BatteryProperties(capacity=10.0, max_power=5.0, efficiency=0.9, **extra)

    def test_curve_accepted_and_serialized(self):
        props = self._props(degradation_yearly=[5, 3, 2])
        assert props.degradation_yearly == [5, 3, 2]
        assert props.model_dump()["degradation_yearly"] == [5, 3, 2]

    def test_zero_and_fractional_entries_accepted(self):
        props = self._props(degradation_yearly=[0, 2.5])
        assert props.degradation_yearly == [0, 2.5]

    def test_empty_curve_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            self._props(degradation_yearly=[])

    def test_out_of_range_entries_rejected(self):
        with pytest.raises(ValidationError, match="0, 100"):
            self._props(degradation_yearly=[-1])
        with pytest.raises(ValidationError, match="0, 100"):
            self._props(degradation_yearly=[100])

    def test_soc_anchors_rejected(self):
        with pytest.raises(ValidationError, match="anchor"):
            self._props(degradation_yearly=[5], soc_anchor_interval_hours=4320)

    def test_optimized_capacity_sizing_rejected(self):
        sizing = CapacityReservation(
            periods="horizon",
            tariffs=[CapacityTariff(name="capex", reserved_price=30_000.0, peak_price=0.0)],
        )
        with pytest.raises(ValidationError, match="optimizer-sized"):
            self._props(degradation_yearly=[5], capacity_sizing=sizing)

    def test_fixed_capacity_sizing_allowed(self):
        sizing = CapacityReservation(
            periods="horizon",
            tariffs=[CapacityTariff(name="capex", reserved_price=30_000.0, peak_price=0.0)],
            reserved=8.0,
        )
        props = self._props(degradation_yearly=[5], capacity_sizing=sizing)
        assert props.degradation_yearly == [5]


class TestCzDistributionImport:
    """Tests for the Czech distribution-tariff import device."""

    def _props(self, **overrides):
        base = dict(
            price=[85.0] * 24,
            max_import=10.0,
            t1_reserved_price=86_000.0,
            t1_peak_price=30_000.0,
            t2_reserved_price=65_000.0,
            t2_peak_price=95_000.0,
        )
        base.update(overrides)
        return CzDistributionImportProperties(**base)

    def test_creation_with_fixed_reserved(self):
        props = self._props(reserved_capacity=5.0)
        device = CzDistributionImport(name="DSO", properties=props)
        assert device.type == "cz_distribution_import"
        assert device.properties.timezone == "Europe/Prague"

    def test_optimized_reserved_requires_positive_prices(self):
        # None reserved_capacity with positive prices -> OK (optimizer sizes R)
        props = self._props(reserved_capacity=None)
        assert props.reserved_capacity is None

        # Zero reserved price with optimized R -> rejected
        with pytest.raises(ValidationError):
            self._props(reserved_capacity=None, t2_reserved_price=0.0)

    def test_to_capacity_reservation_mapping(self):
        reservation = self._props(reserved_capacity=5.0).to_capacity_reservation()
        assert reservation.periods == "calendar_month"
        assert reservation.timezone == "Europe/Prague"
        assert [t.name for t in reservation.tariffs] == ["T1", "T2"]
        assert reservation.tariffs[0].reserved_price == 86_000.0
        assert reservation.tariffs[1].peak_price == 95_000.0
        assert reservation.reserved == 5.0

    def test_bounds_validation(self):
        with pytest.raises(ValidationError):
            self._props(reserved_capacity=1.0, min_reserved=2.0)


class TestDeviceInvestment:
    """Tests for the per-device investment block."""

    def test_investment_on_any_device(self):
        battery = Battery(
            name="BESS",
            properties=BatteryProperties(capacity=8.0, max_power=10.0, efficiency=0.92),
            investment=DeviceInvestment(capital_cost=2_000_000.0, annual_opex=20_000.0),
        )
        assert battery.investment.capital_cost == 2_000_000.0

        pv = PhotovoltaicSteerable(
            name="PV",
            properties=PhotovoltaicSteerableProperties(max_power_profile=[1.0] * 24),
            investment=DeviceInvestment(capital_cost=500_000.0),
        )
        assert pv.investment.annual_opex is None

    def test_investment_defaults_to_none(self):
        battery = Battery(name="BESS", properties=BatteryProperties(capacity=8.0, max_power=10.0, efficiency=0.92))
        assert battery.investment is None

    def test_negative_costs_rejected(self):
        with pytest.raises(ValidationError):
            DeviceInvestment(capital_cost=-1.0)


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
