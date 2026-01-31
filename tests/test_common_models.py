"""Tests for common models (TimeSpan, Resolution, Location)."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from site_calc_investment.models.common import Location, Resolution, TimeSpan


class TestResolution:
    """Tests for Resolution enum."""

    def test_resolution_values(self):
        """Test resolution enum values."""
        assert Resolution.MINUTES_15.value == "15min"
        assert Resolution.HOUR_1.value == "1h"

    def test_resolution_minutes(self):
        """Test minutes property."""
        assert Resolution.MINUTES_15.minutes == 15
        assert Resolution.HOUR_1.minutes == 60

    def test_resolution_intervals_per_day(self):
        """Test intervals_per_day property."""
        assert Resolution.MINUTES_15.intervals_per_day == 96
        assert Resolution.HOUR_1.intervals_per_day == 24


class TestTimeSpan:
    """Tests for TimeSpan model."""

    def test_timespan_creation(self, prague_tz):
        """Test basic TimeSpan creation."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        ts = TimeSpan(start=start, intervals=24, resolution=Resolution.HOUR_1)

        assert ts.start == start
        assert ts.intervals == 24
        assert ts.resolution == Resolution.HOUR_1

    def test_timespan_computed_end(self, prague_tz):
        """Test computed end property."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        ts = TimeSpan(start=start, intervals=24, resolution=Resolution.HOUR_1)

        expected_end = start + timedelta(hours=24)
        assert ts.end == expected_end

    def test_timespan_computed_duration(self, prague_tz):
        """Test computed duration property."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        ts = TimeSpan(start=start, intervals=96, resolution=Resolution.MINUTES_15)

        assert ts.duration == timedelta(days=1)

    def test_timespan_computed_years(self, prague_tz):
        """Test computed years property."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        ts = TimeSpan(
            start=start,
            intervals=87600,  # 10 years
            resolution=Resolution.HOUR_1,
        )

        assert abs(ts.years - 10.0) < 0.01  # Allow small floating point error

    def test_timespan_for_day(self):
        """Test for_day factory method."""
        ts = TimeSpan.for_day(date(2025, 1, 1), Resolution.HOUR_1)

        assert ts.intervals == 24
        assert ts.resolution == Resolution.HOUR_1
        assert ts.start.date() == date(2025, 1, 1)
        assert ts.start.hour == 0
        assert ts.duration == timedelta(days=1)

    def test_timespan_for_day_15min(self):
        """Test for_day with 15-minute resolution."""
        ts = TimeSpan.for_day(date(2025, 1, 1), Resolution.MINUTES_15)

        assert ts.intervals == 96
        assert ts.resolution == Resolution.MINUTES_15

    def test_timespan_for_hours(self, prague_tz):
        """Test for_hours factory method."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        ts = TimeSpan.for_hours(start, 48, Resolution.HOUR_1)

        assert ts.intervals == 48
        assert ts.duration == timedelta(hours=48)

    def test_timespan_for_years(self):
        """Test for_years factory method."""
        ts = TimeSpan.for_years(2025, 10)

        assert ts.intervals == 87600  # 10 × 8760
        assert ts.resolution == Resolution.HOUR_1
        assert ts.start.year == 2025
        assert abs(ts.years - 10.0) < 0.01

    def test_timespan_requires_timezone(self):
        """Test that timezone is required."""
        start_without_tz = datetime(2025, 1, 1, 0, 0, 0)

        with pytest.raises(ValueError, match="Timezone must be specified"):
            TimeSpan(start=start_without_tz, intervals=24, resolution=Resolution.HOUR_1)

    def test_timespan_requires_prague_timezone(self):
        """Test that Europe/Prague timezone is required."""
        start_wrong_tz = datetime(2025, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))

        with pytest.raises(ValueError, match="Timezone must be Europe/Prague"):
            TimeSpan(start=start_wrong_tz, intervals=24, resolution=Resolution.HOUR_1)

    def test_timespan_minimum_intervals(self, prague_tz):
        """Test minimum intervals validation."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)

        with pytest.raises(ValueError):
            TimeSpan(
                start=start,
                intervals=0,  # Invalid
                resolution=Resolution.HOUR_1,
            )

    def test_timespan_maximum_intervals(self, prague_tz):
        """Test maximum intervals validation."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)

        with pytest.raises(ValueError):
            TimeSpan(
                start=start,
                intervals=100_001,  # Over limit
                resolution=Resolution.HOUR_1,
            )

    def test_timespan_to_api_dict(self, prague_tz):
        """Test conversion to API format."""
        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz)
        ts = TimeSpan(start=start, intervals=24, resolution=Resolution.HOUR_1)

        api_dict = ts.to_api_dict()

        assert api_dict["period_start"] == start.isoformat()
        assert api_dict["period_end"] == ts.end.isoformat()
        assert api_dict["resolution"] == "1h"


class TestLocation:
    """Tests for Location model."""

    def test_location_creation(self):
        """Test basic location creation."""
        loc = Location(latitude=50.0751, longitude=14.4378)

        assert loc.latitude == 50.0751
        assert loc.longitude == 14.4378

    def test_location_latitude_bounds(self):
        """Test latitude bounds validation."""
        # Valid bounds
        Location(latitude=-90, longitude=0)
        Location(latitude=90, longitude=0)

        # Invalid bounds
        with pytest.raises(ValueError):
            Location(latitude=-91, longitude=0)

        with pytest.raises(ValueError):
            Location(latitude=91, longitude=0)

    def test_location_longitude_bounds(self):
        """Test longitude bounds validation."""
        # Valid bounds
        Location(latitude=0, longitude=-180)
        Location(latitude=0, longitude=180)

        # Invalid bounds
        with pytest.raises(ValueError):
            Location(latitude=0, longitude=-181)

        with pytest.raises(ValueError):
            Location(latitude=0, longitude=181)

    def test_location_prague(self):
        """Test Prague coordinates."""
        prague = Location(latitude=50.0751, longitude=14.4378)

        assert 50.0 < prague.latitude < 51.0
        assert 14.0 < prague.longitude < 15.0
