"""Tests for energy balance chart builders."""

from site_calc_investment.visualization.charts.energy import (
    build_energy_balance_chart,
    build_energy_summary_kpis,
    categorize_device_flows,
)
from site_calc_investment.visualization.types import (
    AggregationLevel,
    DeviceFlowData,
    EnergyData,
)


class TestCategorizeDeviceFlows:
    """Tests for categorize_device_flows()."""

    def test_battery_discharge_as_generation(self) -> None:
        devices = [
            DeviceFlowData(
                name="Battery1",
                flows={"electricity": [2.0, -1.0, 3.0, -2.0]},
            )
        ]
        result = categorize_device_flows(devices)
        gen_labels = [label for label, _ in result["generation"]]
        assert "Battery1 discharge" in gen_labels

    def test_battery_charge_as_consumption(self) -> None:
        devices = [
            DeviceFlowData(
                name="Battery1",
                flows={"electricity": [2.0, -1.0, 3.0, -2.0]},
            )
        ]
        result = categorize_device_flows(devices)
        con_labels = [label for label, _ in result["consumption"]]
        assert "Battery1 charge" in con_labels

    def test_battery_discharge_values_correct(self) -> None:
        devices = [
            DeviceFlowData(
                name="Battery1",
                flows={"electricity": [2.0, -1.0, 3.0, -2.0]},
            )
        ]
        result = categorize_device_flows(devices)
        discharge = next(v for label, v in result["generation"] if "discharge" in label)
        assert discharge == [2.0, 0.0, 3.0, 0.0]

    def test_battery_charge_values_correct(self) -> None:
        devices = [
            DeviceFlowData(
                name="Battery1",
                flows={"electricity": [2.0, -1.0, 3.0, -2.0]},
            )
        ]
        result = categorize_device_flows(devices)
        charge = next(v for label, v in result["consumption"] if "charge" in label)
        assert charge == [0.0, 1.0, 0.0, 2.0]

    def test_grid_import_as_consumption(self) -> None:
        result = categorize_device_flows(
            [],
            grid_import=[1.0, 2.0, 3.0],
        )
        con_labels = [label for label, _ in result["consumption"]]
        assert "Grid Import" in con_labels

    def test_grid_export_as_generation(self) -> None:
        result = categorize_device_flows(
            [],
            grid_export=[1.0, 2.0, 3.0],
        )
        gen_labels = [label for label, _ in result["generation"]]
        assert "Grid Export" in gen_labels

    def test_chp_electricity_as_generation(self) -> None:
        devices = [
            DeviceFlowData(
                name="CHP1",
                flows={"electricity": [1.5] * 4, "gas": [-3.0] * 4, "heat": [1.0] * 4},
            )
        ]
        result = categorize_device_flows(devices)
        gen_labels = [label for label, _ in result["generation"]]
        assert "CHP1 (electricity)" in gen_labels
        assert "CHP1 (heat)" in gen_labels

    def test_chp_gas_as_consumption(self) -> None:
        devices = [
            DeviceFlowData(
                name="CHP1",
                flows={"electricity": [1.5] * 4, "gas": [-3.0] * 4},
            )
        ]
        result = categorize_device_flows(devices)
        con_labels = [label for label, _ in result["consumption"]]
        assert "CHP1 (gas)" in con_labels

    def test_pv_as_generation(self) -> None:
        devices = [DeviceFlowData(name="PV1", flows={"electricity": [0.8] * 4})]
        result = categorize_device_flows(devices)
        gen_labels = [label for label, _ in result["generation"]]
        assert "PV1 (electricity)" in gen_labels

    def test_empty_grid_flows_not_added(self) -> None:
        result = categorize_device_flows(
            [],
            grid_import=[0.0, 0.0],
            grid_export=[0.0, 0.0],
        )
        assert len(result["generation"]) == 0
        assert len(result["consumption"]) == 0


class TestBuildEnergyBalanceChart:
    """Tests for build_energy_balance_chart()."""

    def test_returns_chart_spec(self) -> None:
        energy = EnergyData(
            devices=[DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 24})],
            grid_import=[0.5] * 24,
            grid_export=[1.5] * 24,
        )
        spec = build_energy_balance_chart(energy, AggregationLevel.HOURLY)
        assert spec.chart_id == "energy_balance"

    def test_stacked_bar_traces(self) -> None:
        energy = EnergyData(
            devices=[DeviceFlowData(name="Battery1", flows={"electricity": [2.0, -1.0] * 12})],
            grid_import=[0.5] * 24,
            grid_export=[1.5] * 24,
        )
        spec = build_energy_balance_chart(energy, AggregationLevel.HOURLY)
        for trace in spec.traces:
            assert trace["type"] == "bar"
        assert spec.layout["barmode"] == "relative"

    def test_has_generation_and_consumption_traces(self) -> None:
        energy = EnergyData(
            devices=[DeviceFlowData(name="Battery1", flows={"electricity": [2.0, -1.0] * 12})],
            grid_import=[0.5] * 24,
            grid_export=[1.5] * 24,
        )
        spec = build_energy_balance_chart(energy, AggregationLevel.HOURLY)
        # Should have: Battery discharge (gen), Grid Export (gen), Battery charge (con), Grid Import (con)
        assert len(spec.traces) >= 3

    def test_consumption_traces_are_negative(self) -> None:
        energy = EnergyData(
            devices=[],
            grid_import=[1.0] * 24,
        )
        spec = build_energy_balance_chart(energy, AggregationLevel.HOURLY)
        # Grid Import should be consumption (negative)
        import_trace = next(t for t in spec.traces if "Import" in t["name"])
        assert all(v <= 0 for v in import_trace["y"])

    def test_monthly_aggregation(self) -> None:
        num = 8760 * 4  # 4 years
        energy = EnergyData(
            devices=[DeviceFlowData(name="PV1", flows={"electricity": [1.0] * num})],
        )
        spec = build_energy_balance_chart(energy, AggregationLevel.MONTHLY, start_year=2025)
        pv_trace = spec.traces[0]
        assert "Jan 2025" in pv_trace["x"][0]

    def test_daily_aggregation(self) -> None:
        num = 8760
        energy = EnergyData(
            devices=[DeviceFlowData(name="PV1", flows={"electricity": [1.0] * num})],
        )
        spec = build_energy_balance_chart(energy, AggregationLevel.DAILY, start_year=2025)
        pv_trace = spec.traces[0]
        assert len(pv_trace["x"]) == 365


class TestBuildEnergySummaryKpis:
    """Tests for build_energy_summary_kpis()."""

    def test_total_generation(self) -> None:
        energy = EnergyData(
            devices=[DeviceFlowData(name="PV1", flows={"electricity": [1.0] * 100})],
            grid_export=[2.0] * 100,
        )
        kpis = build_energy_summary_kpis(energy)
        # PV generation = 100, Grid export = 200
        assert kpis["total_generation_mwh"] == 300.0

    def test_total_consumption(self) -> None:
        energy = EnergyData(
            devices=[],
            grid_import=[1.5] * 100,
        )
        kpis = build_energy_summary_kpis(energy)
        assert kpis["total_consumption_mwh"] == 150.0

    def test_net_grid_position(self) -> None:
        energy = EnergyData(
            devices=[],
            grid_import=[1.0] * 100,
            grid_export=[3.0] * 100,
        )
        kpis = build_energy_summary_kpis(energy)
        # Net = export - import = 300 - 100 = 200
        assert kpis["net_grid_position_mwh"] == 200.0

    def test_no_grid_flows(self) -> None:
        energy = EnergyData(
            devices=[DeviceFlowData(name="PV1", flows={"electricity": [1.0] * 10})],
        )
        kpis = build_energy_summary_kpis(energy)
        assert kpis["net_grid_position_mwh"] == 0.0
        assert kpis["total_generation_mwh"] == 10.0
