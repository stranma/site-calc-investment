"""Tests for device detail chart builders."""

from site_calc_investment.visualization.charts.dispatch import (
    build_dispatch_chart,
    build_soc_chart,
    prepare_drill_down_data,
    should_embed_hourly_data,
)
from site_calc_investment.visualization.types import DeviceFlowData


class TestBuildDispatchChart:
    """Tests for build_dispatch_chart()."""

    def test_creates_trace_per_device_per_flow(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 168}),
            DeviceFlowData(name="CHP1", flows={"electricity": [1.5] * 168, "heat": [1.0] * 168}),
        ]
        spec = build_dispatch_chart(devices)
        # Battery1 electricity + CHP1 electricity + CHP1 heat = 3 traces
        assert len(spec.traces) == 3

    def test_default_window_168h(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 8760}),
        ]
        spec = build_dispatch_chart(devices)
        assert len(spec.traces[0]["y"]) == 168

    def test_custom_window(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 8760}),
        ]
        spec = build_dispatch_chart(devices, window_start=100, window_end=200)
        assert len(spec.traces[0]["y"]) == 100
        assert spec.traces[0]["x"][0] == 100
        assert spec.traces[0]["x"][-1] == 199

    def test_trace_names_include_device_and_material(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 168}),
        ]
        spec = build_dispatch_chart(devices)
        assert spec.traces[0]["name"] == "Battery1 (electricity)"

    def test_line_chart_type(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 168}),
        ]
        spec = build_dispatch_chart(devices)
        assert spec.traces[0]["type"] == "scatter"
        assert spec.traces[0]["mode"] == "lines"

    def test_chart_id(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 168}),
        ]
        spec = build_dispatch_chart(devices)
        assert spec.chart_id == "dispatch"

    def test_window_clamped_to_data_length(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 100}),
        ]
        spec = build_dispatch_chart(devices)
        # Default window is 168 but data is only 100
        assert len(spec.traces[0]["y"]) == 100


class TestBuildSocChart:
    """Tests for build_soc_chart()."""

    def test_only_devices_with_soc(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 168}, soc=[0.5] * 168),
            DeviceFlowData(name="PV1", flows={"electricity": [0.8] * 168}),
        ]
        spec = build_soc_chart(devices)
        assert spec is not None
        assert len(spec.traces) == 1
        assert "Battery1" in spec.traces[0]["name"]

    def test_returns_none_when_no_soc_devices(self) -> None:
        devices = [
            DeviceFlowData(name="PV1", flows={"electricity": [0.8] * 168}),
        ]
        spec = build_soc_chart(devices)
        assert spec is None

    def test_soc_values_as_percentage(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 10}, soc=[0.5] * 10),
        ]
        spec = build_soc_chart(devices, window_start=0, window_end=10)
        assert spec is not None
        # 0.5 * 100 = 50%
        assert spec.traces[0]["y"][0] == 50.0

    def test_y_axis_range_0_100(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 168}, soc=[0.5] * 168),
        ]
        spec = build_soc_chart(devices)
        assert spec is not None
        assert spec.layout["yaxis"]["range"] == [0, 100]

    def test_chart_id(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 168}, soc=[0.5] * 168),
        ]
        spec = build_soc_chart(devices)
        assert spec is not None
        assert spec.chart_id == "soc"

    def test_multiple_storage_devices(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 168}, soc=[0.5] * 168),
            DeviceFlowData(name="HeatStore1", flows={"heat": [0.5] * 168}, soc=[0.7] * 168),
        ]
        spec = build_soc_chart(devices)
        assert spec is not None
        assert len(spec.traces) == 2


class TestShouldEmbedHourlyData:
    """Tests for should_embed_hourly_data()."""

    def test_small_dataset_returns_true(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 8760}, soc=[0.5] * 8760),
        ]
        assert should_embed_hourly_data(devices) is True

    def test_large_dataset_returns_false(self) -> None:
        # Create data that exceeds 15MB when serialized
        # Each float is ~4-6 chars, so 15M / 5 = 3M values needed
        # Use multiple devices with long arrays
        large_values = [1.23456789] * 500_000
        devices = [
            DeviceFlowData(name=f"Dev{i}", flows={"electricity": large_values, "heat": large_values})
            for i in range(10)
        ]
        assert should_embed_hourly_data(devices) is False


class TestPrepareDrillDownData:
    """Tests for prepare_drill_down_data()."""

    def test_structure(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0, 2.0, 3.0]}, soc=[0.5, 0.6, 0.7]),
        ]
        data = prepare_drill_down_data(devices)
        assert "total_hours" in data
        assert "timestamps" in data
        assert "devices" in data

    def test_total_hours(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 100}),
        ]
        data = prepare_drill_down_data(devices)
        assert data["total_hours"] == 100

    def test_timestamps(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 50}),
        ]
        data = prepare_drill_down_data(devices)
        assert data["timestamps"] == list(range(50))

    def test_device_names(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0] * 10}),
            DeviceFlowData(name="CHP1", flows={"electricity": [1.5] * 10}),
        ]
        data = prepare_drill_down_data(devices)
        names = [d["name"] for d in data["devices"]]
        assert names == ["Battery1", "CHP1"]

    def test_device_flows_included(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0, 2.0]}),
        ]
        data = prepare_drill_down_data(devices)
        assert data["devices"][0]["flows"]["electricity"] == [1.0, 2.0]

    def test_soc_included_when_present(self) -> None:
        devices = [
            DeviceFlowData(name="Battery1", flows={"electricity": [1.0]}, soc=[0.5]),
        ]
        data = prepare_drill_down_data(devices)
        assert data["devices"][0]["soc"] == [0.5]

    def test_soc_absent_when_not_present(self) -> None:
        devices = [
            DeviceFlowData(name="PV1", flows={"electricity": [0.8]}),
        ]
        data = prepare_drill_down_data(devices)
        assert "soc" not in data["devices"][0]
