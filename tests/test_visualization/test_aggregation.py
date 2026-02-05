"""Tests for time aggregation functions."""

from site_calc_investment.visualization.aggregation import (
    aggregate_to_daily,
    aggregate_to_monthly,
    aggregate_to_weekly,
    detect_aggregation_level,
)
from site_calc_investment.visualization.types import AggregationLevel


class TestDetectAggregationLevel:
    """Tests for detect_aggregation_level()."""

    def test_hourly_for_168(self) -> None:
        assert detect_aggregation_level(168) == AggregationLevel.HOURLY

    def test_hourly_for_small(self) -> None:
        assert detect_aggregation_level(24) == AggregationLevel.HOURLY

    def test_daily_for_8760(self) -> None:
        assert detect_aggregation_level(8760) == AggregationLevel.DAILY

    def test_daily_for_half_year(self) -> None:
        assert detect_aggregation_level(4380) == AggregationLevel.DAILY

    def test_weekly_for_17520(self) -> None:
        assert detect_aggregation_level(17520) == AggregationLevel.WEEKLY

    def test_weekly_for_3_years(self) -> None:
        assert detect_aggregation_level(8760 * 3) == AggregationLevel.WEEKLY

    def test_monthly_for_30000(self) -> None:
        assert detect_aggregation_level(30000) == AggregationLevel.MONTHLY

    def test_monthly_for_10_years(self) -> None:
        assert detect_aggregation_level(87600) == AggregationLevel.MONTHLY


class TestAggregateToDailyBasic:
    """Tests for aggregate_to_daily()."""

    def test_single_day(self) -> None:
        values = [1.0] * 24
        labels, agg = aggregate_to_daily(values)
        assert len(labels) == 1
        assert len(agg) == 1
        assert agg[0] == 24.0

    def test_two_days(self) -> None:
        values = [1.0] * 24 + [2.0] * 24
        labels, agg = aggregate_to_daily(values)
        assert len(labels) == 2
        assert agg[0] == 24.0
        assert agg[1] == 48.0

    def test_one_year(self) -> None:
        values = [1.0] * 8760
        labels, agg = aggregate_to_daily(values)
        assert len(agg) == 365
        assert all(v == 24.0 for v in agg)

    def test_labels_start_with_year(self) -> None:
        values = [1.0] * 48
        labels, _ = aggregate_to_daily(values, start_year=2026)
        assert labels[0] == "2026-01-01"
        assert labels[1] == "2026-01-02"

    def test_partial_day_remainder(self) -> None:
        values = [1.0] * 30  # 1 day + 6 hours
        labels, agg = aggregate_to_daily(values)
        assert len(agg) == 2
        assert agg[0] == 24.0
        assert agg[1] == 6.0


class TestAggregateToWeekly:
    """Tests for aggregate_to_weekly()."""

    def test_single_week(self) -> None:
        values = [1.0] * 168
        labels, agg = aggregate_to_weekly(values)
        assert len(labels) == 1
        assert agg[0] == 168.0

    def test_two_weeks(self) -> None:
        values = [1.0] * 168 + [2.0] * 168
        labels, agg = aggregate_to_weekly(values)
        assert len(labels) == 2
        assert agg[0] == 168.0
        assert agg[1] == 336.0

    def test_labels_include_week_number(self) -> None:
        values = [1.0] * 336
        labels, _ = aggregate_to_weekly(values, start_year=2025)
        assert "Week 1, 2025" in labels[0]
        assert "Week 2, 2025" in labels[1]

    def test_partial_week_remainder(self) -> None:
        values = [1.0] * 200  # 1 week + 32 hours
        labels, agg = aggregate_to_weekly(values)
        assert len(agg) == 2
        assert agg[0] == 168.0
        assert agg[1] == 32.0


class TestAggregateToMonthly:
    """Tests for aggregate_to_monthly()."""

    def test_january(self) -> None:
        values = [1.0] * (31 * 24)
        labels, agg = aggregate_to_monthly(values, start_year=2025)
        assert len(labels) == 1
        assert labels[0] == "Jan 2025"
        assert agg[0] == 31 * 24

    def test_february_non_leap(self) -> None:
        # Jan + Feb for non-leap year (2025)
        jan_hours = 31 * 24
        feb_hours = 28 * 24
        values = [1.0] * (jan_hours + feb_hours)
        labels, agg = aggregate_to_monthly(values, start_year=2025)
        assert len(labels) == 2
        assert labels[1] == "Feb 2025"
        assert agg[1] == feb_hours

    def test_february_leap_year(self) -> None:
        # 2024 is a leap year
        jan_hours = 31 * 24
        feb_hours = 29 * 24
        values = [1.0] * (jan_hours + feb_hours)
        labels, agg = aggregate_to_monthly(values, start_year=2024)
        assert len(labels) == 2
        assert agg[1] == feb_hours

    def test_full_year(self) -> None:
        # A full year has 365 * 24 = 8760 hours
        values = [1.0] * 8760
        labels, agg = aggregate_to_monthly(values, start_year=2025)
        assert len(labels) == 12
        assert labels[0] == "Jan 2025"
        assert labels[11] == "Dec 2025"
        # Verify month lengths
        expected_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        for i, days in enumerate(expected_days):
            assert agg[i] == days * 24, f"Month {i + 1} should have {days * 24} hours, got {agg[i]}"

    def test_multi_year_wraps_labels(self) -> None:
        # 2 years = 17520 hours
        values = [1.0] * 17520
        labels, agg = aggregate_to_monthly(values, start_year=2025)
        assert len(labels) == 24
        assert labels[0] == "Jan 2025"
        assert labels[12] == "Jan 2026"
        assert labels[23] == "Dec 2026"

    def test_partial_month(self) -> None:
        # 31 days of Jan + 10 days of Feb
        values = [1.0] * (31 * 24 + 10 * 24)
        labels, agg = aggregate_to_monthly(values, start_year=2025)
        assert len(labels) == 2
        assert agg[1] == 10 * 24  # Partial February
