"""Device detail chart builders for the visualization dashboard.

Builds Plotly.js-compatible chart specs for:
- Device dispatch lines (power per device per material)
- Battery/storage SOC curves
- Drill-down data for interactive JS date range selection
"""

import json
from typing import Any, Dict, List, Optional

from site_calc_investment.visualization.types import ChartSpec, DeviceFlowData

# Default window for device detail view (hours)
DEFAULT_DETAIL_WINDOW = 168  # 1 week

# Maximum JSON size for embedded hourly data (bytes)
MAX_EMBED_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


def build_dispatch_chart(
    devices: List[DeviceFlowData],
    window_start: int = 0,
    window_end: Optional[int] = None,
) -> ChartSpec:
    """Build multi-line dispatch chart for all devices.

    Creates one trace per device per material flow for the specified time window.

    :param devices: List of device flow data.
    :param window_start: Start hour index (default 0).
    :param window_end: End hour index (default: window_start + 168).
    :returns: ChartSpec with line traces.
    """
    if window_end is None:
        # Determine total hours from first device
        total_hours = 0
        for dev in devices:
            for values in dev.flows.values():
                total_hours = len(values)
                break
            if total_hours > 0:
                break
        window_end = min(window_start + DEFAULT_DETAIL_WINDOW, total_hours)

    traces: List[Dict[str, Any]] = []
    colors = [
        "#3498db", "#e74c3c", "#2ecc71", "#9b59b6", "#f39c12",
        "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b",
    ]
    color_idx = 0

    hours = list(range(window_start, window_end))

    for device in devices:
        for material, values in device.flows.items():
            window_values = values[window_start:window_end]
            traces.append({
                "x": hours,
                "y": window_values,
                "type": "scatter",
                "mode": "lines",
                "name": f"{device.name} ({material})",
                "line": {"color": colors[color_idx % len(colors)], "width": 1.5},
            })
            color_idx += 1

    layout: Dict[str, Any] = {
        "title": {"text": f"Device Dispatch (Hours {window_start}-{window_end})"},
        "xaxis": {"title": {"text": "Hour"}, "rangeslider": {"visible": True}},
        "yaxis": {"title": {"text": "MW"}},
        "legend": {"orientation": "h", "y": -0.25},
        "hovermode": "x unified",
    }

    return ChartSpec(traces=traces, layout=layout, chart_id="dispatch")


def build_soc_chart(
    devices: List[DeviceFlowData],
    window_start: int = 0,
    window_end: Optional[int] = None,
) -> Optional[ChartSpec]:
    """Build SOC (state of charge) line chart for storage devices.

    Only includes devices that have SOC data.

    :param devices: List of device flow data.
    :param window_start: Start hour index.
    :param window_end: End hour index.
    :returns: ChartSpec with SOC line traces, or None if no devices have SOC data.
    """
    soc_devices = [d for d in devices if d.soc is not None]
    if not soc_devices:
        return None

    if window_end is None:
        total = len(soc_devices[0].soc) if soc_devices[0].soc else 0
        window_end = min(window_start + DEFAULT_DETAIL_WINDOW, total)

    traces: List[Dict[str, Any]] = []
    colors = ["#3498db", "#e74c3c", "#2ecc71", "#9b59b6", "#f39c12"]

    hours = list(range(window_start, window_end))

    for i, device in enumerate(soc_devices):
        if device.soc is None:
            continue
        soc_pct = [v * 100.0 for v in device.soc[window_start:window_end]]
        traces.append({
            "x": hours,
            "y": soc_pct,
            "type": "scatter",
            "mode": "lines",
            "name": f"{device.name} SOC",
            "line": {"color": colors[i % len(colors)], "width": 2},
        })

    layout: Dict[str, Any] = {
        "title": {"text": f"State of Charge (Hours {window_start}-{window_end})"},
        "xaxis": {"title": {"text": "Hour"}, "rangeslider": {"visible": True}},
        "yaxis": {"title": {"text": "SOC (%)"}, "range": [0, 100]},
        "legend": {"orientation": "h", "y": -0.25},
        "hovermode": "x unified",
    }

    return ChartSpec(traces=traces, layout=layout, chart_id="soc")


def should_embed_hourly_data(devices: List[DeviceFlowData]) -> bool:
    """Check if hourly device data is small enough to embed in HTML.

    :param devices: List of device flow data.
    :returns: True if JSON-serialized data is under 15MB.
    """
    data = prepare_drill_down_data(devices)
    json_str = json.dumps(data)
    return len(json_str.encode("utf-8")) < MAX_EMBED_SIZE_BYTES


def prepare_drill_down_data(devices: List[DeviceFlowData]) -> Dict[str, Any]:
    """Prepare device data for JavaScript drill-down embedding.

    Structures data so the JS can render any time window on demand.

    :param devices: List of device flow data.
    :returns: Dict with device names, flows, soc, and timestamps
        suitable for JSON embedding in HTML.
    """
    total_hours = 0
    for dev in devices:
        for values in dev.flows.values():
            total_hours = len(values)
            break
        if total_hours > 0:
            break

    device_data: List[Dict[str, Any]] = []
    for device in devices:
        entry: Dict[str, Any] = {
            "name": device.name,
            "flows": device.flows,
        }
        if device.soc is not None:
            entry["soc"] = device.soc
        device_data.append(entry)

    return {
        "total_hours": total_hours,
        "timestamps": list(range(total_hours)),
        "devices": device_data,
    }
