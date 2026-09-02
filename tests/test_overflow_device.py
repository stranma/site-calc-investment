"""Tests for the ``electricity_import_with_overflow`` sugar device and the
``exclusive_with`` pairing on ``electricity_export``."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from site_calc_investment.models import (
    Battery,
    BatteryProperties,
    CapacityReservation,
    CapacityTariff,
    CzDistributionImport,
    CzDistributionImportProperties,
    ElectricityExport,
    ElectricityImport,
    ElectricityImportWithOverflow,
    ElectricityImportWithOverflowProperties,
    InvestmentPlanningRequest,
    MarketExportProperties,
    MarketImportProperties,
    Site,
    TimeSpanInvestment,
)
from site_calc_investment.models.devices import device_to_wire

HOURS = 24
IMPORT_PRICE = [90.0] * HOURS
OVERFLOW_PRICE = [120.0] * HOURS


def _props(**overrides) -> ElectricityImportWithOverflowProperties:
    base = dict(import_price=IMPORT_PRICE, overflow_price=OVERFLOW_PRICE, max_import=2.0)
    base.update(overrides)
    return ElectricityImportWithOverflowProperties(**base)


def _sugar(name: str = "Grid", **overrides) -> ElectricityImportWithOverflow:
    return ElectricityImportWithOverflow(name=name, properties=_props(**overrides))


def _plain_import(name: str = "GridImport") -> ElectricityImport:
    return ElectricityImport(name=name, properties=MarketImportProperties(price=IMPORT_PRICE, max_import=2.0))


def _plain_export(target: str | None, name: str = "GridExport") -> ElectricityExport:
    return ElectricityExport(
        name=name,
        properties=MarketExportProperties(price=OVERFLOW_PRICE, max_export=2.0, exclusive_with=target),
    )


def _api(devices: list) -> list[dict]:
    request = InvestmentPlanningRequest(
        sites=[Site(site_id="S", devices=devices)],
        timespan=TimeSpanInvestment(start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")), intervals=HOURS),
    )
    return request.model_dump_for_api()["sites"][0]["devices"]


class TestElectricityImportWithOverflowProperties:
    def test_defaults(self) -> None:
        props = _props()
        assert props.max_overflow is None
        assert props.no_simultaneous_flow is True
        assert props.capacity_reservation is None

    def test_rejects_non_positive_max_import(self) -> None:
        with pytest.raises(ValidationError):
            _props(max_import=0.0)

    def test_rejects_non_positive_max_overflow(self) -> None:
        with pytest.raises(ValidationError):
            _props(max_overflow=-1.0)

    def test_rejects_empty_price(self) -> None:
        with pytest.raises(ValidationError):
            _props(overflow_price=[])

    def test_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            _props(price=IMPORT_PRICE)

    def test_in_memory_model_keeps_its_identity(self) -> None:
        device = _sugar()
        assert device.type == "electricity_import_with_overflow"
        assert device.model_dump()["properties"]["overflow_price"] == OVERFLOW_PRICE


class TestWireExpansion:
    def test_expands_to_paired_import_and_export(self) -> None:
        wire = _api([_sugar()])
        assert wire == [
            {"name": "Grid", "type": "electricity_import", "properties": {"price": IMPORT_PRICE, "max_import": 2.0}},
            {
                "name": "Grid_overflow",
                "type": "electricity_export",
                "properties": {"price": OVERFLOW_PRICE, "max_export": 2.0, "exclusive_with": "Grid"},
            },
        ]

    def test_max_overflow_is_used_for_the_export_rating(self) -> None:
        wire = _api([_sugar(max_overflow=1.5)])
        assert wire[1]["properties"]["max_export"] == 1.5
        assert wire[0]["properties"]["max_import"] == 2.0

    def test_relaxed_pairing_drops_exclusive_with(self) -> None:
        wire = _api([_sugar(no_simultaneous_flow=False)])
        assert "exclusive_with" not in wire[1]["properties"]
        assert wire[1]["name"] == "Grid_overflow"

    def test_capacity_reservation_goes_to_the_import_leg(self) -> None:
        reservation = CapacityReservation(
            periods="calendar_month",
            tariffs=[CapacityTariff(name="T1", reserved_price=1000.0, peak_price=10.0)],
            reserved=2.0,
        )
        wire = _api([_sugar(capacity_reservation=reservation)])
        assert wire[0]["properties"]["capacity_reservation"] == reservation.model_dump()
        assert "capacity_reservation" not in wire[1]["properties"]

    def test_investment_block_is_stripped_from_both_legs(self) -> None:
        device = ElectricityImportWithOverflow(
            name="Grid", properties=_props(), investment={"capital_cost": 1000.0, "annual_opex": 10.0}
        )
        wire = _api([device])
        assert all("investment" not in d for d in wire)

    def test_device_to_wire_returns_one_entry_for_plain_devices(self) -> None:
        wire = device_to_wire(_plain_import().model_dump())
        assert len(wire) == 1
        assert wire[0]["type"] == "electricity_import"

    def test_plain_export_without_pairing_omits_the_key(self) -> None:
        wire = _api([_plain_import(), _plain_export(None)])
        assert "exclusive_with" not in wire[1]["properties"]

    def test_plain_export_pairing_is_sent_by_name(self) -> None:
        wire = _api([_plain_import(), _plain_export("GridImport")])
        assert wire[1]["properties"]["exclusive_with"] == "GridImport"


class TestSiteValidation:
    def test_derived_overflow_name_must_be_free(self) -> None:
        with pytest.raises(ValidationError, match="Grid_overflow"):
            Site(site_id="S", devices=[_sugar(), _plain_import(name="Grid_overflow")])

    def test_pairing_target_must_exist(self) -> None:
        with pytest.raises(ValidationError, match="Nope"):
            Site(site_id="S", devices=[_plain_import(), _plain_export("Nope")])

    def test_pairing_target_must_be_an_import(self) -> None:
        battery = Battery(name="Bess", properties=BatteryProperties(capacity=2.0, max_power=1.0, efficiency=0.9))
        with pytest.raises(ValidationError, match="must be an electricity import"):
            Site(site_id="S", devices=[battery, _plain_import(), _plain_export("Bess")])

    def test_plain_export_may_pair_with_a_cz_distribution_import(self) -> None:
        dso = CzDistributionImport(
            name="DSO",
            properties=CzDistributionImportProperties(
                price=IMPORT_PRICE,
                max_import=2.0,
                t1_reserved_price=86_000.0,
                t1_peak_price=30_000.0,
                t2_reserved_price=65_000.0,
                t2_peak_price=95_000.0,
                reserved_capacity=2.0,
            ),
        )
        wire = _api([dso, _plain_export("DSO")])
        assert wire[0]["type"] == "electricity_import"
        assert wire[1]["properties"]["exclusive_with"] == "DSO"

    def test_one_export_per_import(self) -> None:
        with pytest.raises(ValidationError, match="already paired"):
            Site(site_id="S", devices=[_sugar(), _plain_export("Grid")])

    def test_relaxed_sugar_leaves_its_import_free_to_pair(self) -> None:
        wire = _api([_sugar(no_simultaneous_flow=False), _plain_export("Grid")])
        assert [d["name"] for d in wire] == ["Grid", "Grid_overflow", "GridExport"]
        assert "exclusive_with" not in wire[1]["properties"]
        assert wire[2]["properties"]["exclusive_with"] == "Grid"
