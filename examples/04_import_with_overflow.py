"""Import with Overflow Example

A net-metered grid connection: consumption is billed at an import price and
the surplus fed back to the grid is paid at an overflow price. The service
treats the connection as ONE meter: in any hour it is either importing or
exporting, never both.

Three parts:

1. The common case: the ``ElectricityImportWithOverflow`` device.
2. The same pairing built by hand: a Czech distribution-tariff import plus a
   plain ``ElectricityExport`` whose ``exclusive_with`` names the import.
3. Why the pairing matters: the number the service would report without it.

Parts 1-3 run offline and print the exact payload sent to the service. The
optional submission at the end needs INVESTMENT_API_URL and INVESTMENT_API_KEY
and a service at API version 1.5 or newer (older services ignore the pairing).
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from site_calc_investment import (
    CzDistributionImport,
    ElectricityExport,
    ElectricityImportWithOverflow,
    FixedConsumption,
    FixedProduction,
    InvestmentClient,
    InvestmentPlanningRequest,
    OptimizationConfig,
    Site,
)
from site_calc_investment.models.requests import TimeSpanInvestment

HOURS = 24
LOAD_MW = 0.6
PV_MW = 1.0  # available from hour 8 to hour 15
IMPORT_PRICE = 10.0  # EUR/MWh paid for energy taken from the grid
OVERFLOW_PRICE = 50.0  # EUR/MWh received for the surplus fed back
CONNECTION_MW = 2.0  # real connection capacity; use the true value


def timespan() -> TimeSpanInvestment:
    return TimeSpanInvestment(start=datetime(2026, 6, 1, tzinfo=ZoneInfo("Europe/Prague")), intervals=HOURS)


def load_and_pv() -> list:
    """A fixed load and a fixed PV profile: nothing for the optimizer to decide except the grid."""
    pv_profile = [PV_MW if 8 <= hour < 16 else 0.0 for hour in range(HOURS)]
    return [
        FixedConsumption(name="Load", properties={"power_profile": [LOAD_MW] * HOURS}),
        FixedProduction(name="PV", properties={"power_profile": pv_profile}),
    ]


def site_with_overflow_device(*, paired: bool = True) -> Site:
    """Part 1: one device describes the whole connection."""
    grid = ElectricityImportWithOverflow(
        name="Grid",
        properties={
            "import_price": [IMPORT_PRICE] * HOURS,
            "overflow_price": [OVERFLOW_PRICE] * HOURS,
            "max_import": CONNECTION_MW,
            "max_overflow": CONNECTION_MW,  # optional, defaults to max_import
            "no_simultaneous_flow": paired,  # True = one direction per hour (the default)
        },
    )
    return Site(site_id="overflow_device", devices=[*load_and_pv(), grid])


def site_built_by_hand() -> Site:
    """Part 2: the same pairing on devices you build yourself.

    Use this form when the import needs something the overflow device does
    not expose -- here the Czech distribution tariff with its T1/T2 menu.
    The export's ``exclusive_with`` names the import it shares the meter with.
    """
    dso_import = CzDistributionImport(
        name="DSO",
        properties={
            "price": [IMPORT_PRICE] * HOURS,
            "max_import": CONNECTION_MW,
            "t1_reserved_price": 86_000.0,
            "t1_peak_price": 30_000.0,
            "t2_reserved_price": 65_000.0,
            "t2_peak_price": 95_000.0,
            "reserved_capacity": CONNECTION_MW,
        },
    )
    overflow = ElectricityExport(
        name="Overflow",
        properties={
            "price": [OVERFLOW_PRICE] * HOURS,
            "max_export": CONNECTION_MW,
            "exclusive_with": "DSO",
        },
    )
    return Site(site_id="hand_built_pair", devices=[*load_and_pv(), dso_import, overflow])


def show_wire(site: Site) -> None:
    """Print what the service receives: the grid devices as sent, prices abbreviated."""
    request = InvestmentPlanningRequest(sites=[site], timespan=timespan())
    for device in request.model_dump_for_api()["sites"][0]["devices"]:
        if device["type"] in ("electricity_import", "electricity_export"):
            props = {k: (f"[{v[0]} x{len(v)}]" if k == "price" else v) for k, v in device["properties"].items()}
            print(f"  {device['name']:<14} {device['type']:<19} {json.dumps(props, default=str)}")


def explain_the_numbers() -> None:
    """Part 3: what the meter settles versus what an unpaired model would claim."""
    surplus_hours = 8
    deficit_hours = HOURS - surplus_hours
    metered = surplus_hours * (PV_MW - LOAD_MW) * OVERFLOW_PRICE - deficit_hours * LOAD_MW * IMPORT_PRICE
    unpaired_per_surplus_hour = PV_MW * OVERFLOW_PRICE - LOAD_MW * IMPORT_PRICE
    print(f"  In a surplus hour the meter pays {(PV_MW - LOAD_MW) * OVERFLOW_PRICE:.0f} EUR: ")
    print(f"    {PV_MW - LOAD_MW:.1f} MWh surplus at {OVERFLOW_PRICE:.0f} EUR/MWh.")
    print(f"  Unpaired import + export would claim {unpaired_per_surplus_hour:.0f} EUR in that hour:")
    print(f"    sell all {PV_MW:.1f} MWh at {OVERFLOW_PRICE:.0f} EUR/MWh")
    print(f"    and buy the {LOAD_MW:.1f} MWh load at {IMPORT_PRICE:.0f} EUR/MWh.")
    print(f"  Over the day the metered value is {metered:.0f} EUR; the paired device reports exactly that.")
    print("  That is a lower bound: with slack in the connection ratings the optimizer also passes")
    print("  grid power straight through, so the unpaired figure grows with the ratings (the live")
    print("  run below shows it). The gap repeats in every hour with the overflow price above the")
    print("  import price, and it misjudges CHP and battery dispatch, not just the total.")


def submit(site: Site, label: str) -> None:
    """Optional: run the site against the service and show the hourly direction."""
    api_url = os.environ.get("INVESTMENT_API_URL")
    api_key = os.environ.get("INVESTMENT_API_KEY")
    if not api_url or not api_key:
        print(f"  ({label}: set INVESTMENT_API_URL and INVESTMENT_API_KEY to submit)")
        return
    request = InvestmentPlanningRequest(
        sites=[site],
        timespan=timespan(),
        optimization_config=OptimizationConfig(mip_gap=0.0, time_limit_seconds=120),
    )
    with InvestmentClient(base_url=api_url, api_key=api_key) as client:
        job = client.create_planning_job(request)
        result = client.wait_for_completion(job.job_id, poll_interval=3, timeout=300)
    flows = result.sites[site.site_id].grid_flows
    if not flows:
        print(f"  {label}: the result carries no grid flows")
        return
    imported = flows["import"]
    exported = [-x for x in flows["export"]]  # export flows are reported as negative values
    both = [h for h in range(HOURS) if imported[h] > 1e-6 and exported[h] > 1e-6]
    print(f"  {label}: expected profit {result.summary.expected_profit:,.2f} EUR, hours with both directions: {both}")


def main() -> None:
    print("=" * 72)
    print("PART 1: ElectricityImportWithOverflow -> sent as a paired import + export")
    print("=" * 72)
    show_wire(site_with_overflow_device())

    print("\n" + "=" * 72)
    print("PART 2: hand-built pairing (Czech tariff import + export with exclusive_with)")
    print("=" * 72)
    show_wire(site_built_by_hand())

    print("\n" + "=" * 72)
    print("PART 3: why the pairing matters")
    print("=" * 72)
    explain_the_numbers()

    print("\n" + "=" * 72)
    print("OPTIONAL: run against the service")
    print("=" * 72)
    submit(site_with_overflow_device(), "paired")
    submit(site_with_overflow_device(paired=False), "unpaired control")


if __name__ == "__main__":
    main()
