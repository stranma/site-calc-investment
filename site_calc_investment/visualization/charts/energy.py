"""Energy balance chart builders for the visualization dashboard.

Builds Plotly.js-compatible chart specs for:
- Energy balance stacked bar chart (generation, consumption, grid)
- Energy summary KPIs (total generation, consumption, net grid)
"""

from typing import Any, Dict, List, Optional, Tuple

from site_calc_investment.visualization.aggregation import (
    aggregate_to_daily,
    aggregate_to_monthly,
    aggregate_to_weekly,
)
from site_calc_investment.visualization.types import (
    AggregationLevel,
    ChartSpec,
    DeviceFlowData,
    EnergyData,
)

# Device types that produce energy (positive = generation)
_GENERATION_KEYWORDS = {"export", "discharge", "output", "generation"}
# Device types that consume energy (positive = consumption)
_CONSUMPTION_KEYWORDS = {"import", "input", "demand", "charge", "consumption"}


def categorize_device_flows(
    devices: List[DeviceFlowData],
    grid_import: Optional[List[float]] = None,
    grid_export: Optional[List[float]] = None,
) -> Dict[str, List[Tuple[str, List[float]]]]:
    """Categorize device flows into generation and consumption.

    Heuristics:
    - Battery electricity flow: positive values = discharge (generation), negative = charge (consumption)
    - Grid import = consumption
    - Grid export = generation
    - CHP electricity/heat output = generation, gas input = consumption
    - PV electricity = generation
    - Demand flows = consumption

    :param devices: List of device flow data.
    :param grid_import: Grid import flow (if separate from device flows).
    :param grid_export: Grid export flow (if separate from device flows).
    :returns: Dict with 'generation' and 'consumption' keys, each containing
        a list of (label, values) tuples.
    """
    generation: List[Tuple[str, List[float]]] = []
    consumption: List[Tuple[str, List[float]]] = []

    for device in devices:
        dev_lower = device.name.lower()

        for material, values in device.flows.items():
            mat_lower = material.lower()
            label = f"{device.name} ({material})"

            # Battery: split positive (discharge) and negative (charge)
            if "battery" in dev_lower or "batt" in dev_lower:
                if mat_lower == "electricity" or mat_lower == "power":
                    discharge = [max(0.0, v) for v in values]
                    charge = [abs(min(0.0, v)) for v in values]
                    if any(v > 0 for v in discharge):
                        generation.append((f"{device.name} discharge", discharge))
                    if any(v > 0 for v in charge):
                        consumption.append((f"{device.name} charge", charge))
                    continue

            # CHP: electricity and heat are generation, gas is consumption
            if "chp" in dev_lower:
                if mat_lower in ("gas", "fuel"):
                    consumption.append((label, [abs(v) for v in values]))
                else:
                    generation.append((label, [abs(v) for v in values]))
                continue

            # PV: always generation
            if "pv" in dev_lower or "photovoltaic" in dev_lower or "solar" in dev_lower:
                generation.append((label, [abs(v) for v in values]))
                continue

            # Demand devices: consumption
            if "demand" in dev_lower:
                consumption.append((label, [abs(v) for v in values]))
                continue

            # Heat accumulator: similar to battery
            if "accumulator" in dev_lower or "storage" in dev_lower:
                discharge = [max(0.0, v) for v in values]
                charge = [abs(min(0.0, v)) for v in values]
                if any(v > 0 for v in discharge):
                    generation.append((f"{device.name} discharge ({material})", discharge))
                if any(v > 0 for v in charge):
                    consumption.append((f"{device.name} charge ({material})", charge))
                continue

            # Generic: use keywords in material name
            if any(kw in mat_lower for kw in _GENERATION_KEYWORDS):
                generation.append((label, [abs(v) for v in values]))
            elif any(kw in mat_lower for kw in _CONSUMPTION_KEYWORDS):
                consumption.append((label, [abs(v) for v in values]))
            else:
                # Default: positive = generation
                pos = [max(0.0, v) for v in values]
                neg = [abs(min(0.0, v)) for v in values]
                if any(v > 0 for v in pos):
                    generation.append((label, pos))
                if any(v > 0 for v in neg):
                    consumption.append((label, neg))

    # Grid flows
    if grid_import is not None and any(v > 0 for v in grid_import):
        consumption.append(("Grid Import", grid_import))
    if grid_export is not None and any(v > 0 for v in grid_export):
        generation.append(("Grid Export", grid_export))

    return {"generation": generation, "consumption": consumption}


def build_energy_balance_chart(
    energy: EnergyData,
    aggregation_level: AggregationLevel,
    start_year: int = 2025,
) -> ChartSpec:
    """Build stacked bar chart showing energy balance.

    :param energy: Energy data with device flows and grid flows.
    :param aggregation_level: Time aggregation level for the bars.
    :param start_year: Start year for label generation.
    :returns: ChartSpec with stacked bar traces.
    """
    categorized = categorize_device_flows(
        energy.devices,
        grid_import=energy.grid_import,
        grid_export=energy.grid_export,
    )

    traces: List[Dict[str, Any]] = []

    # Generation traces (positive bars)
    gen_colors = ["#2ecc71", "#27ae60", "#1abc9c", "#16a085", "#3498db"]
    for i, (label, values) in enumerate(categorized["generation"]):
        agg_labels, agg_values = _aggregate_values(values, aggregation_level, start_year)
        color = gen_colors[i % len(gen_colors)]
        traces.append({
            "x": agg_labels,
            "y": agg_values,
            "type": "bar",
            "name": label,
            "marker": {"color": color},
        })

    # Consumption traces (negative bars for visual clarity)
    con_colors = ["#e74c3c", "#c0392b", "#e67e22", "#d35400", "#f39c12"]
    for i, (label, values) in enumerate(categorized["consumption"]):
        agg_labels, agg_values = _aggregate_values(values, aggregation_level, start_year)
        neg_values = [-v for v in agg_values]
        color = con_colors[i % len(con_colors)]
        traces.append({
            "x": agg_labels,
            "y": neg_values,
            "type": "bar",
            "name": label,
            "marker": {"color": color},
        })

    layout: Dict[str, Any] = {
        "title": {"text": "Energy Balance"},
        "barmode": "relative",
        "xaxis": {"title": {"text": "Period"}},
        "yaxis": {"title": {"text": "MWh"}},
        "legend": {"orientation": "h", "y": -0.2},
    }

    return ChartSpec(traces=traces, layout=layout, chart_id="energy_balance")


def build_energy_summary_kpis(energy: EnergyData) -> Dict[str, Any]:
    """Build energy summary KPIs.

    :param energy: Energy data with device flows and grid flows.
    :returns: Dict with total_generation, total_consumption, and net_grid_position in MWh.
    """
    categorized = categorize_device_flows(
        energy.devices,
        grid_import=energy.grid_import,
        grid_export=energy.grid_export,
    )

    total_gen = 0.0
    for _, values in categorized["generation"]:
        total_gen += sum(values)

    total_con = 0.0
    for _, values in categorized["consumption"]:
        total_con += sum(values)

    # Net grid = export - import
    grid_export_total = sum(energy.grid_export) if energy.grid_export else 0.0
    grid_import_total = sum(energy.grid_import) if energy.grid_import else 0.0
    net_grid = grid_export_total - grid_import_total

    return {
        "total_generation_mwh": round(total_gen, 2),
        "total_consumption_mwh": round(total_con, 2),
        "net_grid_position_mwh": round(net_grid, 2),
    }


def _aggregate_values(
    values: List[float],
    level: AggregationLevel,
    start_year: int,
) -> Tuple[List[str], List[float]]:
    """Apply aggregation to hourly values based on level.

    :param values: Hourly values.
    :param level: Aggregation level.
    :param start_year: Start year for labels.
    :returns: Tuple of (labels, aggregated_values).
    """
    if level == AggregationLevel.HOURLY:
        labels = [f"H{i}" for i in range(len(values))]
        return labels, list(values)
    elif level == AggregationLevel.DAILY:
        return aggregate_to_daily(values, start_year)
    elif level == AggregationLevel.WEEKLY:
        return aggregate_to_weekly(values, start_year)
    else:
        return aggregate_to_monthly(values, start_year)
