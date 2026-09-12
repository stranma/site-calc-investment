# Planning timezones and API compatibility

Contract for **site-calc-investment 1.5.5** with **investment server 1.5.3**
advertising `planning_timezone` (API 1.5). Deploy that server before upgrading
the client. Package numbers alone do not replace capability verification. These
changes are absent from client 1.5.4 and the server deployed 2026-09-11; historical
limitations below identify that older combination.

## Client contract

`TimeSpan` and `TimeSpanInvestment` accept an optional `timezone` input containing
an IANA name. After validation it is populated. Existing aware Python constructors
using `ZoneInfo("Europe/Prague")` keep working: omission is inferred only from an
aware `ZoneInfo.key`. A datetime parsed from an ISO offset, including UTC, needs
an explicit `timezone`. Naive datetimes and invalid IANA names are rejected.
The input schema permits omission/null for Python constructor compatibility,
but JSON clients must supply the IANA name: `timezone=None` with
`datetime.timezone.utc` or a parsed `Z` timestamp fails validation. An aware
`ZoneInfo("UTC")` start can infer `"UTC"`. Schema optionality does not imply that
an offset-only request has a default calendar.

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo
from site_calc_investment.models import Resolution, TimeSpanInvestment

span = TimeSpanInvestment(start=datetime(2026, 3, 29, tzinfo=ZoneInfo("Europe/Prague")), intervals=23)
assert span.timezone == "Europe/Prague"
assert span.end == datetime(2026, 3, 30, tzinfo=ZoneInfo("Europe/Prague"))
restored = TimeSpanInvestment.model_validate_json(span.model_dump_json())
assert restored.start.tzinfo.key == "Europe/Prague"
civil_day = TimeSpanInvestment.for_day(date(2026, 10, 25), Resolution.HOUR_1)
assert civil_day.intervals == 25
```

Wire requests contain exactly `timespan: {period_start, period_end, resolution,
timezone}`. Both endpoints are aware ISO timestamps. `TimeSpan.model_validate`
and `TimeSpanInvestment.model_validate` also accept this wire shape and validate
positive whole interval counts and agreement with an explicit `intervals` value.
UTC endpoints (`Z` or `+00:00`) with an explicit zone are valid transport; the
client reconstructs `ZoneInfo` without changing the instant. Every nonzero input
offset must agree with the declared zone at that instant. Offset alone never
selects the planning calendar. The endpoint is exclusive.

Nonexistent ZoneInfo civil times in a spring gap are rejected. Autumn folds
`fold=0` and `fold=1` are accepted as distinct instants; Python defaults to fold=0,
so callers entering the repeated civil hour should make their choice explicit.
An offset plus the IANA name also identifies the occurrence. `end` and interval
counts use elapsed UTC arithmetic. `for_day` covers the actual civil day (23 or
25 hours at Prague transitions). `for_hours` covers elapsed hours.

`for_fixed_years(start_year, years, resolution=...)` means exactly `years * 365`
elapsed days from local January 1. `for_calendar_years` ends on local January 1
after the requested number of years and includes leap days. Both accept a
keyword-only IANA `timezone`, defaulting to Europe/Prague, as does `for_day`.
`for_hours` accepts explicit `timezone` or infers it from its ZoneInfo start.
`for_years` emits `DeprecationWarning` and keeps the old `years * 8760` interval
count. At 1h it delegates to `for_fixed_years`; its historical 15min count is also
preserved (91.25 days per nominal year). The new fixed helper correctly scales
intervals at 15min. Investment models still allow only 1h and at most 100,000
intervals. Fixed-count constructors do not resize profiles automatically. Across
DST, corrected elapsed arithmetic can move endpoints compared with the old
wall-clock implementation; `for_day` now changes its count to match the actual
civil day. Audit recorded endpoints and rebuild profiles when migrating those
cases; the migration guide gives explicit examples.

MCP continues using fixed 365-day years and Prague January 1 starts; it now calls
`for_fixed_years` and sends `timezone`. Exact `intervals` retain their old meaning.
Calendar-year horizons are available through the Python helper.

Fixed duration does not remove leap days: a fixed 365-day horizon starting
2028-01-01 includes February 29 and ends at 2028-12-31 local midnight. Local
months remain real Gregorian months. The helper chooses duration, not a
synthetic calendar.

Existing annual financial aggregation and yearly degradation still use fixed
8,760-hour model years. A 2025-to-2035 civil horizon has 87,648 hourly values,
so annual arrays can contain ten full buckets and a 48-hour eleventh bucket;
financial helpers do not turn these into civil years. The MCP `monthly` display
also retains its legacy limit of twelve 730-hour chunks (the first 8,760 hours),
not named-zone months. See [MCP result detail levels](MCP_SERVER_SPEC.md#get_job_result)
and [the annual result convention](INVESTMENT_CLIENT_SPEC.md#71-investment-metrics).
Use complete schedules and explicit calendar boundaries when civil-period
reporting is required. These reporting conventions do not change calendar tariff
periods or SOC anchors in the solved model.

For before/after code, preserving legacy UTC calendars and resizing profiles,
follow [timezone migration](../MIGRATION_GUIDE.md#timezone-and-calendar-migration).

## Compatible service and responses

Use a service revision that implements this contract and advertises
`"features": ["planning_timezone"]` in a successful `GET /health` response.
The client caches this list during its existing once-per-client version
check, with no additional health roundtrip. Before any timezone-bearing planning
POST, it requires the `planning_timezone` feature. Missing, malformed, non-200,
or unavailable health data raises `ForbiddenFeatureError` with code
`planning_timezone_unsupported`; no job is submitted. There is no bypass option.
Status checks, old-result reads, and other existing non-submission operations
remain available even when capability verification fails.

The check (including a failed check) is cached for the client lifetime. After a
service upgrade or health/connection repair, create a new `InvestmentClient`.
An API version match alone does not grant the capability. Published 1.5.4 cannot
submit this new named-zone contract; conversely client 1.5.5
cannot submit to an older server that does not advertise support. Old published
clients can still use a compatible new service's legacy missing-zone behavior.
Operator verification and integration acceptance remain necessary; the feature
advertisement does not constitute production or ten-year test evidence.

The compatible service treats old requests omitting timezone as legacy UTC and
returns a deprecation message on submission; the new client always sends a zone.
A different billing timezone is allowed if its period boundaries agree with the
planning timezone over the actual span. Otherwise the compatible service rejects
the request with HTTP 400. Legacy callers with valid aware, aligned spans remain
supported; the client does not
silently rewrite tariff zones or impose timezone-name equality.

Retaining a legacy UTC calendar does not preserve every formerly accepted input:
new admission and replay reject naive endpoints, nonpositive spans and endpoints
not aligned to whole resolution intervals. Operators should drain the queue
before rollout and inspect outstanding retries; invalid legacy payloads require
explicit correction and resubmission, not silent date or profile changes.

`InvestmentPlanningResponse.timespan` is optional typed `TimeSpanMetadata` with
aware `period_start` and `period_end` (UTC ISO transport from the service),
`resolution: str`, `timezone: IANA str`, and
`timezone_source: "explicit" | "legacy_utc"`. Deserialization and model JSON retain
these fields. Optional `timezone_rules_sha256` retains a 64-hex SHA-256 hash of
the planning zone's actual TZif rule data reported by the server; older metadata
without it yields `None`. This identifies the rules independently of whether
they came from the operating system or a Python timezone-data package. The
compatible service records the hash on admission and fails with an explanation
if the rules change before a later processing attempt. The client does not
compute or submit this server-owned field. Older results have `timespan=None`;
no zone is guessed. Arrays
remain in elapsed interval order, including both occurrences of repeated hours.

`Job.error_message` retains the service's string failure explanation, alongside
`error_code`. `wait_for_completion` uses these when legacy `error` dictionary
message/code fields are absent; dictionary details and precedence are preserved.

## What client 1.5.4 actually preserves

`TimeSpan` / `TimeSpanInvestment` requires an aware Python start datetime whose
`tzinfo` is `ZoneInfo("Europe/Prague")`. It rejects naive values and other zone
objects, including a numeric offset alone. This validation is local to the
client; it is not a guarantee about the service's calendar interpretation.

Serialization emits `period_start`, `period_end` and `resolution`. The ISO 8601
timestamps contain offsets; **there is no named planning-zone field**. A tariff's
`timezone` describes billing, not the whole planning horizon. The service release
above does not preserve Prague as the planning calendar. Monthly SOC boundaries
can therefore differ from Prague tariff months, and explicit `decomposed` jobs
with these tariffs can fail. A real ten-year request demonstrated this failure.
`auto` fallback does not establish that the intended Prague SOC policy was used.

Do not add a guessed `timezone` keyword and assume support. Use a service/client
combination with explicitly verified named-zone support before relying on local
monthly SOC and tariff alignment. No fixed-offset workaround is equivalent for
multi-month or multi-year Prague planning.

There are additional limitations in the existing helpers: `end` adds a duration
to a local datetime, `for_day` assumes 24 hourly intervals, and `for_years` uses
8,760 hours per year. These are not general DST-safe calendar constructors.
An 87,600-hour benchmark is a fixed-duration convention, not ten full calendar
years including leap days. Do not infer arbitrary DST-horizon correctness from
the winter-to-winter benchmark.

## Published 1.5.4 upgrade requirements (historical guidance)

A future compatible client/API revision must retain the named planning zone
separately from aware endpoint instants. UTC transport is acceptable; discarding
the named calendar is not. The field name and supported versions must be published
with that revision. These were requirements for published 1.5.4, not available constructor args in that release.
Client 1.5.5 supplies the client fields described above.

The client must validate zone support, aware instants, consistent interval counts,
aligned endpoints and profile lengths before submission. Civil-time entry must
reject spring gaps and distinguish both occurrences of ambiguous autumn times. UTC arithmetic
must determine elapsed interval counts. Calendar tariff period boundaries must agree with the
declared planning calendar over the actual span; zone names may differ. Do not
silently adjust a tariff.
MCP scenario submission must follow the same rules as Python submission.

On deserialization, preserve both returned instants and the named zone when the
negotiated response contract supplies it. An offset parsed from JSON is not an
IANA zone and may not pass the 1.5.4 start validator when replayed. Keep the
original request context for older results; do not infer a zone from a result
offset or pretend missing metadata proves the service used Prague. Schedule
arrays must retain their interval order across repeated local hours. Job creation
and completion timestamps are service events, not the planning calendar.

The published status model can report a failed job with null error details due
to the current service/client field mismatch. Treat `status="failed"` as failure;
retain its job ID for operator diagnosis. The next compatible contract must
preserve explanatory status errors rather than discard them.

## Prague example: offset is not the calendar

This standard-library example explains the required representation; it does not
construct or submit an unsupported request:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

planning_zone = "Europe/Prague"  # retain separately from endpoint strings
zone = ZoneInfo(planning_zone)
start = datetime(2026, 3, 29, 0, 0, tzinfo=zone)
end = datetime(2026, 3, 30, 0, 0, tzinfo=zone)
start_utc = start.astimezone(timezone.utc)
end_utc = end.astimezone(timezone.utc)
assert (end_utc - start_utc).total_seconds() / 3600 == 23
assert start.isoformat().endswith("+01:00")
assert end.isoformat().endswith("+02:00")
```

The autumn Prague day 2026-10-25 has 25 hours; its repeated 02:30 times have
different offsets and are distinct instants. Neither `+01:00` nor `+02:00`
encodes the rule that switches between them.

## Backwards compatibility and acceptance

Keep existing request semantics explicit. Older servers may ignore unknown
fields; matching API MAJOR.MINOR alone does not prove named-zone support. An
upgrade must check the service capability/release contract and reject unsupported
zone-dependent requests rather than silently dropping the zone. Document any
legacy missing-zone default and the effect on calendar boundaries. Do not
reinterpret old results as having new semantics.

Acceptance must round-trip the zone and instants through Python and MCP, test
23/25-hour days, reject nonexistent civil times and preserve explicit autumn folds, retain
both autumn intervals, and verify profile/schedule counts. It must also verify
monthly SOC and tariff alignment, partial final boundaries, result metadata and
useful failure details against a compatible service. The simple serialization tests accompanying published 1.5.4 did not establish
those guarantees. For the current implementation and its compatibility
requirements, see [Client contract](#client-contract) and
[Compatible service and responses](#compatible-service-and-responses).
