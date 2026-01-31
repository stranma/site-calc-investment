# SYNC: This file may be synced between investment and operational clients
"""Common models shared across the investment client."""

from datetime import date, datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, computed_field, field_validator


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


class TimeSpan(BaseModel):
    """Time period for optimization.

    Represents a time period with explicit interval count, allowing precise
    control over array sizes and computed end time.

    Examples:
        Full day at 15-minute resolution:
        >>> ts = TimeSpan.for_day(date(2025, 11, 6), Resolution.MINUTES_15)
        >>> ts.intervals
        96
        >>> ts.duration
        timedelta(days=1)

        Custom 10-year planning:
        >>> ts = TimeSpan(
        ...     start=datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Prague")),
        ...     intervals=87600,
        ...     resolution=Resolution.HOUR_1
        ... )
        >>> ts.years
        10.0
    """

    start: datetime = Field(..., description="Start time (Europe/Prague timezone required)")
    intervals: int = Field(..., ge=1, le=100_000, description="Number of time intervals")
    resolution: Resolution = Field(..., description="Time resolution (15min or 1h)")

    @field_validator("start")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        """Ensure timezone is Europe/Prague."""
        prague_tz = ZoneInfo("Europe/Prague")
        if v.tzinfo is None:
            raise ValueError("Timezone must be specified")
        if v.tzinfo != prague_tz:
            raise ValueError(f"Timezone must be Europe/Prague, got {v.tzinfo}")
        return v

    @computed_field  # type: ignore[misc]
    @property
    def end(self) -> datetime:
        """Computed end time based on start, intervals, and resolution."""
        delta = timedelta(minutes=self.intervals * self.resolution.minutes)
        return self.start + delta

    @computed_field  # type: ignore[misc]
    @property
    def duration(self) -> timedelta:
        """Total duration of the time period."""
        return timedelta(minutes=self.intervals * self.resolution.minutes)

    @computed_field  # type: ignore[misc]
    @property
    def years(self) -> float:
        """Duration in years (approximate, using 365.25 days/year)."""
        return self.duration.total_seconds() / (365.25 * 24 * 3600)

    @classmethod
    def for_day(cls, date: date, resolution: Resolution) -> "TimeSpan":
        """Create timespan for a full day.

        Args:
            date: The date to optimize
            resolution: Time resolution (15min or 1h)

        Returns:
            TimeSpan covering the full day

        Example:
            >>> ts = TimeSpan.for_day(date(2025, 11, 6), Resolution.HOUR_1)
            >>> ts.intervals
            24
        """
        start = datetime.combine(date, datetime.min.time()).replace(tzinfo=ZoneInfo("Europe/Prague"))
        return cls(start=start, intervals=resolution.intervals_per_day, resolution=resolution)

    @classmethod
    def for_hours(cls, start: datetime, hours: int, resolution: Resolution) -> "TimeSpan":
        """Create timespan for N hours.

        Args:
            start: Start datetime (must have Europe/Prague timezone)
            hours: Number of hours
            resolution: Time resolution

        Returns:
            TimeSpan covering the specified hours

        Example:
            >>> start = datetime(2025, 11, 6, tzinfo=ZoneInfo("Europe/Prague"))
            >>> ts = TimeSpan.for_hours(start, 48, Resolution.HOUR_1)
            >>> ts.intervals
            48
        """
        intervals = hours * (60 // resolution.minutes)
        return cls(start=start, intervals=intervals, resolution=resolution)

    @classmethod
    def for_years(cls, start_year: int, years: int, resolution: Resolution = Resolution.HOUR_1) -> "TimeSpan":
        """Create timespan for N years.

        Args:
            start_year: Starting year (e.g., 2025)
            years: Number of years
            resolution: Time resolution (defaults to 1h)

        Returns:
            TimeSpan covering the specified years

        Example:
            >>> ts = TimeSpan.for_years(2025, 10)
            >>> ts.intervals
            87600
            >>> ts.years
            10.0
        """
        start = datetime(start_year, 1, 1, tzinfo=ZoneInfo("Europe/Prague"))
        intervals = years * 8760  # 8760 hours per year
        return cls(start=start, intervals=intervals, resolution=resolution)

    def to_api_dict(self) -> dict:
        """Convert to API format.

        Returns:
            Dictionary with period_start, period_end, resolution for API requests
        """
        return {
            "period_start": self.start.isoformat(),
            "period_end": self.end.isoformat(),
            "resolution": self.resolution.value,
        }


class Location(BaseModel):
    """Geographic location for devices like photovoltaic systems.

    Attributes:
        latitude: Latitude in degrees (-90 to 90)
        longitude: Longitude in degrees (-180 to 180)

    Example:
        >>> prague = Location(latitude=50.0751, longitude=14.4378)
    """

    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
