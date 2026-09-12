# SYNC: This file may be synced between investment and operational clients
"""Common models shared across the investment client."""

import warnings
from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone
from enum import Enum
from typing import Annotated, Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, Field, TypeAdapter, computed_field, model_validator


class Resolution(str, Enum):
    """Time resolution for optimization intervals."""

    MINUTES_15 = "15min"
    HOUR_1 = "1h"

    @property
    def minutes(self) -> int:
        """Get resolution in minutes."""
        return 15 if self == Resolution.MINUTES_15 else 60

    @property
    def intervals_per_day(self) -> int:
        """Get number of intervals per day."""
        return 96 if self == Resolution.MINUTES_15 else 24


def validate_iana_zone(value: str) -> str:
    """Validate a named timezone supported by the installed IANA database."""
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Invalid IANA timezone: {value}") from exc
    return value


IANATimezone = Annotated[str, AfterValidator(validate_iana_zone)]
_DATETIME = TypeAdapter(datetime)


def normalize_endpoint(value: Any, zone: ZoneInfo) -> datetime:
    """Preserve an aware instant and validate its civil time and numeric offset."""
    endpoint = _DATETIME.validate_python(value)
    if endpoint.tzinfo is None or endpoint.utcoffset() is None:
        raise ValueError("Timezone must be specified; endpoints must be aware")
    instant = endpoint.astimezone(datetime_timezone.utc)
    if isinstance(endpoint.tzinfo, ZoneInfo):
        restored = instant.astimezone(endpoint.tzinfo)
        if restored.replace(tzinfo=None) != endpoint.replace(tzinfo=None):
            raise ValueError("Nonexistent civil time in IANA timezone")
    localized = instant.astimezone(zone)
    if endpoint.utcoffset() != timedelta(0) and endpoint.utcoffset() != localized.utcoffset():
        raise ValueError("Endpoint offset does not agree with timezone at this instant")
    return localized


class TimeSpan(BaseModel):
    """Planning period measured in elapsed intervals, with a named calendar zone.

    Supply an aware ``start`` and ``timezone`` (IANA name). Existing Python
    constructors may omit timezone only when start carries a ZoneInfo key.
    Numeric offsets alone cannot identify a calendar. UTC transport is accepted
    with an explicit zone; other offsets must match that zone at the instant.
    Nonexistent civil times are rejected; Python fold=0 and fold=1 select the
    two occurrences of an ambiguous hour.
    """

    start: datetime = Field(..., description="Aware start instant; ZoneInfo or explicit timezone required")
    intervals: int = Field(..., ge=1, le=100_000, description="Number of elapsed time intervals")
    resolution: Resolution = Field(..., description="Time resolution (15min or 1h)")
    timezone: Optional[IANATimezone] = Field(
        default=None, description="IANA planning zone; inferred only from an aware Python start's ZoneInfo key"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_timespan(cls, value: Any) -> Any:
        """Normalize Python and wire inputs without guessing a zone from offsets."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        start = data.get("start", data.get("period_start"))
        if start is None:
            return data
        parsed = _DATETIME.validate_python(start)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Timezone must be specified; endpoints must be aware")
        name = data.get("timezone")
        if name is None and isinstance(parsed.tzinfo, ZoneInfo):
            name = parsed.tzinfo.key
        if not isinstance(name, str):
            raise ValueError("Explicit IANA timezone required for offset-only input")
        zone = ZoneInfo(validate_iana_zone(name))
        data["timezone"] = name
        data["start"] = normalize_endpoint(parsed, zone)
        if "period_end" in data:
            end = normalize_endpoint(data["period_end"], zone)
            resolution = Resolution(data.get("resolution", Resolution.HOUR_1))
            seconds = (end.astimezone(datetime_timezone.utc) - parsed.astimezone(datetime_timezone.utc)).total_seconds()
            count, remainder = divmod(seconds, resolution.minutes * 60)
            if count < 1 or remainder:
                raise ValueError("Endpoints must define positive, whole resolution intervals")
            if "intervals" in data and data["intervals"] != count:
                raise ValueError("Endpoint duration does not match intervals")
            data["intervals"] = int(count)
        return data

    @computed_field  # type: ignore[misc]
    @property
    def end(self) -> datetime:
        """Exclusive end after elapsed UTC arithmetic, in the planning zone."""
        return (self.start.astimezone(datetime_timezone.utc) + self.duration).astimezone(self.start.tzinfo)

    @computed_field  # type: ignore[misc]
    @property
    def duration(self) -> timedelta:
        """Total elapsed duration."""
        return timedelta(minutes=self.intervals * self.resolution.minutes)

    @computed_field  # type: ignore[misc]
    @property
    def years(self) -> float:
        """Approximate elapsed years, using 365.25 days per year."""
        return self.duration.total_seconds() / (365.25 * 24 * 3600)

    @classmethod
    def for_day(cls, date: date, resolution: Resolution, *, timezone: str = "Europe/Prague") -> "TimeSpan":
        """Cover a civil day, including 23/25-hour DST days in Prague.

        :param date: Local calendar date.
        :param resolution: Elapsed interval resolution.
        :param timezone: IANA planning zone; defaults to Europe/Prague.
        """
        zone = ZoneInfo(validate_iana_zone(timezone))
        start = datetime.combine(date, datetime.min.time(), tzinfo=zone)
        end = datetime.combine(date + timedelta(days=1), datetime.min.time(), tzinfo=zone)
        return cls.model_validate(dict(period_start=start, period_end=end, resolution=resolution, timezone=timezone))

    @classmethod
    def for_hours(
        cls, start: datetime, hours: int, resolution: Resolution, *, timezone: Optional[str] = None
    ) -> "TimeSpan":
        """Cover N elapsed hours; infer timezone only from an aware ZoneInfo start."""
        return cls(start=start, intervals=hours * (60 // resolution.minutes), resolution=resolution, timezone=timezone)

    @classmethod
    def for_fixed_years(
        cls,
        start_year: int,
        years: int,
        resolution: Resolution = Resolution.HOUR_1,
        *,
        timezone: str = "Europe/Prague",
    ) -> "TimeSpan":
        """Cover years * 365 elapsed days from local January 1.

        :param start_year: Year of the local January 1 start.
        :param years: Number of fixed 365-day durations.
        :param resolution: Elapsed interval resolution.
        :param timezone: IANA planning zone.
        """
        start = datetime(start_year, 1, 1, tzinfo=ZoneInfo(validate_iana_zone(timezone)))
        return cls.for_hours(start, years * 8760, resolution)

    @classmethod
    def for_years(cls, start_year: int, years: int, resolution: Resolution = Resolution.HOUR_1) -> "TimeSpan":
        """Deprecated fixed-year alias; preserves historical years * 8760 counts.

        At 1h this means 365 elapsed days per year. The legacy 15min behavior
        also keeps years * 8760 intervals, only 91.25 days per year. Use
        for_fixed_years for 365-day durations at either resolution, or
        for_calendar_years for actual January-to-January calendar spans.
        """
        warnings.warn(
            "for_years is deprecated; use for_fixed_years (365 elapsed days) or for_calendar_years. "
            "Legacy 15min counts remain years * 8760.",
            DeprecationWarning,
            stacklevel=2,
        )
        if resolution == Resolution.HOUR_1:
            return cls.for_fixed_years(start_year, years, resolution)
        start = datetime(start_year, 1, 1, tzinfo=ZoneInfo("Europe/Prague"))
        return cls(start=start, intervals=years * 8760, resolution=resolution, timezone="Europe/Prague")

    @classmethod
    def for_calendar_years(
        cls,
        start_year: int,
        years: int,
        resolution: Resolution = Resolution.HOUR_1,
        *,
        timezone: str = "Europe/Prague",
    ) -> "TimeSpan":
        """Cover local January 1 to January 1 after N years, including leap days."""
        zone = ZoneInfo(validate_iana_zone(timezone))
        return cls.model_validate(
            dict(
                period_start=datetime(start_year, 1, 1, tzinfo=zone),
                period_end=datetime(start_year + years, 1, 1, tzinfo=zone),
                resolution=resolution,
                timezone=timezone,
            )
        )

    def to_api_dict(self) -> dict:
        """Return aware endpoints, resolution and the named planning timezone."""
        return {
            "period_start": self.start.isoformat(),
            "period_end": self.end.isoformat(),
            "resolution": self.resolution.value,
            "timezone": self.timezone,
        }


class Location(BaseModel):
    """Geographic location (latitude/longitude).

    Attributes:
        latitude: Latitude in degrees (-90 to 90)
        longitude: Longitude in degrees (-180 to 180)

    Example:
        >>> prague = Location(latitude=50.0751, longitude=14.4378)
    """

    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
