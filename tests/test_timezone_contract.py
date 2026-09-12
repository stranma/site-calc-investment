"""Local named-zone contract, elapsed helpers, and response compatibility."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from site_calc_investment import InvestmentClient, OptimizationError, TimeSpanMetadata
from site_calc_investment.models import InvestmentPlanningRequest, InvestmentPlanningResponse, Job
from site_calc_investment.models.common import Resolution, TimeSpan
from site_calc_investment.models.requests import TimeSpanInvestment

PRAGUE = ZoneInfo("Europe/Prague")


def span(start, **kwargs):
    return TimeSpanInvestment(start=start, intervals=24, **kwargs)


@pytest.mark.parametrize("model", [TimeSpan, TimeSpanInvestment])
@pytest.mark.parametrize("fold", [0, 1])
def test_named_zone_model_and_wire_roundtrip(model, fold):
    original = model(
        start=datetime(2026, 10, 25, 2, tzinfo=PRAGUE, fold=fold), intervals=24, resolution=Resolution.HOUR_1
    )
    for restored in (
        model.model_validate_json(original.model_dump_json()),
        model.model_validate(original.to_api_dict()),
    ):
        assert restored.timezone == "Europe/Prague"
        assert restored.start.tzinfo.key == "Europe/Prague"
        assert restored.start.fold == fold
        assert restored.start.timestamp() == original.start.timestamp()
        assert restored.end.timestamp() - restored.start.timestamp() == 86400
        assert restored.intervals == 24


@pytest.mark.parametrize("start", [datetime(2026, 1, 1), "2026-01-01T00:00:00"])
def test_naive_rejected(start):
    with pytest.raises(ValueError, match="aware"):
        span(start, timezone="Europe/Prague")


@pytest.mark.parametrize(
    "start",
    [
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1))),
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00+01:00",
    ],
)
def test_offset_only_requires_explicit_iana(start):
    with pytest.raises(ValueError, match="Explicit IANA"):
        span(start)


@pytest.mark.parametrize("name", ["Bad/Zone", "", "+01:00", "../UTC"])
def test_invalid_zone(name):
    with pytest.raises(ValueError, match="IANA"):
        span("2026-01-01T00:00:00Z", timezone=name)


@pytest.mark.parametrize(
    "start,expected_hour",
    [
        ("2026-01-01T00:00:00Z", 1),
        ("2026-01-01T00:00:00+00:00", 1),
        ("2026-07-01T00:00:00Z", 2),
        ("2026-01-01T00:00:00+01:00", 0),
        ("2026-07-01T00:00:00+02:00", 0),
    ],
)
def test_explicit_zone_reconstructs_zoneinfo(start, expected_hour):
    ts = span(start, timezone="Europe/Prague")
    assert ts.start.tzinfo.key == "Europe/Prague"
    assert ts.start.hour == expected_hour


@pytest.mark.parametrize(
    "start,name",
    [
        ("2026-01-01T00:00:00+02:00", "Europe/Prague"),
        ("2026-07-01T00:00:00+01:00", "Europe/Prague"),
        ("2026-01-01T00:00:00+01:00", "UTC"),
        ("2026-03-29T02:30:00+01:00", "Europe/Prague"),
    ],
)
def test_nonzero_offset_must_match(start, name):
    with pytest.raises(ValueError, match="offset"):
        span(start, timezone=name)


@pytest.mark.parametrize("fold", [0, 1])
def test_zoneinfo_gap_rejected(fold):
    with pytest.raises(ValueError, match="Nonexistent"):
        span(datetime(2026, 3, 29, 2, 30, tzinfo=PRAGUE, fold=fold))


@pytest.mark.parametrize("day,hours", [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25)])
@pytest.mark.parametrize("resolution,multiplier", [(Resolution.HOUR_1, 1), (Resolution.MINUTES_15, 4)])
def test_civil_day(day, hours, resolution, multiplier):
    ts = TimeSpan.for_day(day, resolution)
    assert ts.intervals == hours * multiplier
    assert ts.duration == timedelta(hours=hours)
    assert ts.end.date() == day + timedelta(days=1)
    assert ts.end.hour == 0


def test_elapsed_hours_cross_gap_and_fold():
    spring = TimeSpan.for_hours(datetime(2026, 3, 29, 1, tzinfo=PRAGUE), 1, Resolution.HOUR_1)
    assert spring.end.hour == 3
    autumn = TimeSpan.for_hours(datetime(2026, 10, 25, 2, tzinfo=PRAGUE, fold=0), 1, Resolution.HOUR_1)
    assert autumn.end.hour == 2
    assert autumn.end.fold == 1
    assert autumn.end.timestamp() - autumn.start.timestamp() == 3600


def test_year_helpers_preserve_counts_and_distinguish_calendar():
    with pytest.warns(DeprecationWarning):
        legacy = TimeSpanInvestment.for_years(2025, 10)
    fixed = TimeSpanInvestment.for_fixed_years(2025, 10)
    calendar = TimeSpanInvestment.for_calendar_years(2025, 10)
    assert legacy.intervals == fixed.intervals == 87600
    assert calendar.intervals == 87648
    assert calendar.end == datetime(2035, 1, 1, tzinfo=PRAGUE)
    with pytest.warns(DeprecationWarning):
        assert TimeSpan.for_years(2024, 1, Resolution.MINUTES_15).intervals == 8760
    assert TimeSpan.for_fixed_years(2024, 1, Resolution.MINUTES_15).intervals == 35040
    assert TimeSpan.for_calendar_years(2024, 1, Resolution.MINUTES_15).intervals == 35136


def test_request_roundtrips(simple_site):
    request = InvestmentPlanningRequest(sites=[simple_site], timespan=span(datetime(2026, 1, 1, tzinfo=PRAGUE)))
    wire = request.model_dump_for_api()
    assert set(wire["timespan"]) == {"period_start", "period_end", "resolution", "timezone"}
    for restored in (
        InvestmentPlanningRequest.model_validate(wire),
        InvestmentPlanningRequest.model_validate_json(request.model_dump_json()),
    ):
        assert restored.timespan.start.tzinfo.key == "Europe/Prague"
        assert restored.timespan.to_api_dict() == wire["timespan"]


@pytest.mark.parametrize(
    "end,count",
    [
        ("2026-01-01T02:30:00Z", None),
        ("2026-01-01T00:00:00Z", None),
        ("2026-01-01T02:00:00Z", 3),
        ("2026-01-01T02:00:00+02:00", None),
    ],
)
def test_wire_endpoints_validated(end, count):
    data = dict(period_start="2026-01-01T00:00:00Z", period_end=end, resolution="1h", timezone="Europe/Prague")
    if count is not None:
        data["intervals"] = count
    with pytest.raises(ValueError):
        TimeSpanInvestment.model_validate(data)


def test_utc_wire_endpoints():
    ts = TimeSpanInvestment.model_validate(
        dict(
            period_start="2026-03-28T23:00:00Z",
            period_end="2026-03-29T22:00:00Z",
            resolution="1h",
            timezone="Europe/Prague",
        )
    )
    assert ts.intervals == 23
    assert ts.start.hour == ts.end.hour == 0


@pytest.mark.parametrize("source", ["explicit", "legacy_utc"])
def test_response_metadata(source):
    metadata = dict(
        period_start="2026-03-28T23:00:00Z",
        period_end="2026-03-29T22:00:00Z",
        resolution="1h",
        timezone="UTC" if source == "legacy_utc" else "Europe/Prague",
        timezone_source=source,
    )
    data = dict(job_id="test", sites={}, summary=dict(solver_status="optimal", solve_time_seconds=0))
    assert InvestmentPlanningResponse.model_validate(data).timespan is None
    result = InvestmentPlanningResponse.model_validate(dict(**data, timespan=metadata))
    restored = InvestmentPlanningResponse.model_validate_json(result.model_dump_json())
    assert isinstance(restored.timespan, TimeSpanMetadata)
    assert restored.timespan == result.timespan
    assert restored.timespan.timezone_source == source
    for field, value in [
        ("period_start", "2026-01-01T00:00:00"),
        ("timezone", "Bad/Zone"),
        ("timezone_source", "guessed"),
    ]:
        with pytest.raises(ValueError):
            TimeSpanMetadata.model_validate(dict(metadata, **{field: value}))


@pytest.mark.parametrize(
    "payload,message,code,details",
    [
        (
            {"error_message": "Calendar mismatch", "error_code": "INVALID_TIMEZONE"},
            "Calendar mismatch",
            "INVALID_TIMEZONE",
            None,
        ),
        (
            {
                "error": {"message": "Old detail", "code": "OLD", "details": {"field": "start"}},
                "error_message": "Fallback",
                "error_code": "NEW",
            },
            "Old detail",
            "OLD",
            {"field": "start"},
        ),
        ({"error": {}, "error_message": "Fallback", "error_code": "NEW"}, "Fallback", "NEW", None),
    ],
)
def test_wait_failure_preserves_error_formats(payload, message, code, details):
    job = Job.model_validate(dict(job_id="test", status="failed", **payload))
    with InvestmentClient("https://api.example.com", "inv_test") as client:
        with patch.object(client, "get_job_status", return_value=job):
            with pytest.raises(OptimizationError, match=message) as caught:
                client.wait_for_completion("test")
    assert caught.value.code == code
    assert caught.value.details == (details or {})


def test_mcp_fixed_year_request_includes_zone():
    from site_calc_investment.mcp.scenario import ScenarioStore

    store = ScenarioStore()
    sid = store.create(name="Timezone contract")
    store.add_device(sid, "battery", "Battery", {"capacity": 10.0, "max_power": 5.0, "efficiency": 0.9})
    store.set_timespan(sid, start_year=2024, years=1)
    request = store.build_request(sid)
    assert request.timespan.intervals == 8760
    assert request.model_dump_for_api()["timespan"]["timezone"] == "Europe/Prague"


@pytest.mark.parametrize("name", [None, "UTC"])
def test_utc_zoneinfo_optional_timezone(name):
    assert span(datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")), timezone=name).timezone == "UTC"


def test_utc_fixed_offset_null_timezone_rejected():
    with pytest.raises(ValueError, match="Explicit IANA"):
        span(datetime(2026, 1, 1, tzinfo=timezone.utc), timezone=None)


def test_metadata_roundtrip_through_api():
    metadata = dict(
        period_start="2026-01-01T00:00:00Z",
        period_end="2026-01-02T00:00:00Z",
        resolution="1h",
        timezone="Europe/Prague",
        timezone_source="explicit",
    )
    response = dict(
        job_id="test", sites={}, summary=dict(solver_status="optimal", solve_time_seconds=0), timespan=metadata
    )
    with InvestmentClient("https://api.example.com", "inv_test") as client:
        with patch.object(
            client,
            "_request_with_retry",
            return_value=Mock(json=Mock(return_value={"job_id": "test", "status": "completed", "result": response})),
        ):
            result = client.get_job_result("test")
    assert result.timespan.timezone == "Europe/Prague"
    assert result.timespan.period_start.utcoffset() == timedelta(0)


@pytest.mark.parametrize("rules_hash", [None, "a1" * 32, "AB" * 32])
def test_optional_timezone_rules_hash_roundtrip(rules_hash: str | None) -> None:
    metadata = dict(
        period_start="2026-01-01T00:00:00Z",
        period_end="2026-01-02T00:00:00Z",
        resolution="1h",
        timezone="Europe/Prague",
        timezone_source="explicit",
    )
    if rules_hash is not None:
        metadata["timezone_rules_sha256"] = rules_hash
    result = InvestmentPlanningResponse.model_validate(
        dict(job_id="test", sites={}, timespan=metadata, summary=dict(solver_status="optimal", solve_time_seconds=0))
    )
    restored = InvestmentPlanningResponse.model_validate_json(result.model_dump_json())
    assert restored.timespan.timezone_rules_sha256 == rules_hash
    assert set(span(datetime(2026, 1, 1, tzinfo=PRAGUE)).to_api_dict()) == {
        "period_start",
        "period_end",
        "resolution",
        "timezone",
    }


@pytest.mark.parametrize("rules_hash", ["", "a" * 63, "a" * 65, "g" * 64, "a" * 64 + "\n", 123])
def test_invalid_timezone_rules_hash_rejected(rules_hash: object) -> None:
    with pytest.raises(ValueError):
        TimeSpanMetadata(
            period_start="2026-01-01T00:00:00Z",
            period_end="2026-01-02T00:00:00Z",
            resolution="1h",
            timezone="Europe/Prague",
            timezone_source="explicit",
            timezone_rules_sha256=rules_hash,
        )
