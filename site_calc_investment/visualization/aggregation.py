"""Smart time aggregation for visualization charts.

Automatically selects the appropriate aggregation level based on
the optimization horizon length and provides functions to aggregate
hourly data into daily, weekly, or monthly buckets.
"""

import calendar
from typing import List, Tuple

from site_calc_investment.visualization.types import AggregationLevel

# Thresholds for aggregation level selection (in hours/intervals)
_HOURLY_MAX = 168  # Up to 1 week -> hourly
_DAILY_MAX = 8760  # Up to 1 year -> daily
_WEEKLY_MAX = 8760 * 3  # Up to 3 years -> weekly
# Above 3 years -> monthly


def detect_aggregation_level(num_intervals: int) -> AggregationLevel:
    """Determine the best aggregation level for the given number of intervals.

    :param num_intervals: Number of hourly intervals in the optimization.
    :returns: Appropriate aggregation level.

    Rules:
        - <= 168 (1 week): HOURLY
        - <= 8760 (1 year): DAILY
        - <= 26280 (3 years): WEEKLY
        - > 26280: MONTHLY
    """
    if num_intervals <= _HOURLY_MAX:
        return AggregationLevel.HOURLY
    elif num_intervals <= _DAILY_MAX:
        return AggregationLevel.DAILY
    elif num_intervals <= _WEEKLY_MAX:
        return AggregationLevel.WEEKLY
    else:
        return AggregationLevel.MONTHLY


def aggregate_to_daily(values: List[float], start_year: int = 2025) -> Tuple[List[str], List[float]]:
    """Aggregate hourly values into daily sums.

    :param values: Hourly values to aggregate.
    :param start_year: Start year for generating labels (default 2025).
    :returns: Tuple of (labels, aggregated_values) where labels are date strings.
    """
    hours_per_day = 24
    num_days = len(values) // hours_per_day
    remainder = len(values) % hours_per_day

    labels: List[str] = []
    aggregated: List[float] = []

    # Generate day labels using calendar
    day_counter = 0
    year = start_year
    month = 1
    day_of_month = 1

    for d in range(num_days):
        start = d * hours_per_day
        end = start + hours_per_day
        daily_sum = sum(values[start:end])
        aggregated.append(daily_sum)
        labels.append(f"{year}-{month:02d}-{day_of_month:02d}")

        # Advance day
        days_in_month = calendar.monthrange(year, month)[1]
        day_of_month += 1
        if day_of_month > days_in_month:
            day_of_month = 1
            month += 1
            if month > 12:
                month = 1
                year += 1
        day_counter += 1

    # Handle remainder hours as partial last day
    if remainder > 0:
        partial_sum = sum(values[num_days * hours_per_day :])
        aggregated.append(partial_sum)
        labels.append(f"{year}-{month:02d}-{day_of_month:02d}")

    return labels, aggregated


def aggregate_to_weekly(values: List[float], start_year: int = 2025) -> Tuple[List[str], List[float]]:
    """Aggregate hourly values into weekly sums.

    :param values: Hourly values to aggregate.
    :param start_year: Start year for generating labels.
    :returns: Tuple of (labels, aggregated_values) where labels are "Week N, YYYY" strings.
    """
    hours_per_week = 168
    num_weeks = len(values) // hours_per_week
    remainder = len(values) % hours_per_week

    labels: List[str] = []
    aggregated: List[float] = []

    for w in range(num_weeks):
        start = w * hours_per_week
        end = start + hours_per_week
        weekly_sum = sum(values[start:end])
        aggregated.append(weekly_sum)

        # Calculate which year this week falls in
        hours_elapsed = w * hours_per_week
        year_offset = hours_elapsed // 8760
        week_in_year = ((hours_elapsed % 8760) // hours_per_week) + 1
        labels.append(f"Week {week_in_year}, {start_year + year_offset}")

    # Handle remainder
    if remainder > 0:
        partial_sum = sum(values[num_weeks * hours_per_week :])
        aggregated.append(partial_sum)
        hours_elapsed = num_weeks * hours_per_week
        year_offset = hours_elapsed // 8760
        week_in_year = ((hours_elapsed % 8760) // hours_per_week) + 1
        labels.append(f"Week {week_in_year}, {start_year + year_offset}")

    return labels, aggregated


def aggregate_to_monthly(values: List[float], start_year: int = 2025) -> Tuple[List[str], List[float]]:
    """Aggregate hourly values into monthly sums.

    Handles variable month lengths (28/29/30/31 days) correctly.

    :param values: Hourly values to aggregate.
    :param start_year: Start year for generating labels.
    :returns: Tuple of (labels, aggregated_values) where labels are "Mon YYYY" strings.
    """
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    labels: List[str] = []
    aggregated: List[float] = []

    idx = 0
    year = start_year
    month = 1

    while idx < len(values):
        days_in_month = calendar.monthrange(year, month)[1]
        hours_in_month = days_in_month * 24
        end = min(idx + hours_in_month, len(values))

        monthly_sum = sum(values[idx:end])
        aggregated.append(monthly_sum)
        labels.append(f"{month_names[month - 1]} {year}")

        idx = end
        month += 1
        if month > 12:
            month = 1
            year += 1

    return labels, aggregated
