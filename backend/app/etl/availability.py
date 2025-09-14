"""
ETL module for building vehicle availability grids.

This module provides functions to determine vehicle availability for scheduling
based on lifecycle dates and current activity blocks.
"""

from datetime import date, datetime, timedelta
from typing import List, Tuple
import pandas as pd


def parse_date_string(date_str) -> date:
    """Parse date string in YYYY-MM-DD format to date object."""
    # Check datetime first since datetime is a subclass of date
    if isinstance(date_str, datetime):
        return date_str.date()
    if isinstance(date_str, date):
        return date_str
    if isinstance(date_str, str):
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    raise ValueError(f"Unable to parse date: {date_str}")


def generate_week_range(week_start: str) -> List[date]:
    """Generate 7-day range starting from week_start (Monday)."""
    start_date = parse_date_string(week_start)
    return [start_date + timedelta(days=i) for i in range(7)]


def is_date_in_lifecycle_window(target_date: date, in_service_date, expected_turn_in_date) -> bool:
    """
    Check if target_date falls within the vehicle's lifecycle window.

    Args:
        target_date: The date to check
        in_service_date: Vehicle's in-service date (or None/NaN)
        expected_turn_in_date: Vehicle's expected turn-in date (or None/NaN)

    Returns:
        True if the date is within the lifecycle window, False otherwise
    """
    # Convert None/NaN to None for consistent handling
    if pd.isna(in_service_date):
        in_service_date = None
    if pd.isna(expected_turn_in_date):
        expected_turn_in_date = None

    # If in_service_date exists and target_date is before it, unavailable
    if in_service_date is not None:
        if isinstance(in_service_date, str):
            in_service_date = parse_date_string(in_service_date)
        elif isinstance(in_service_date, datetime):
            in_service_date = in_service_date.date()

        if target_date < in_service_date:
            return False

    # If expected_turn_in_date exists and target_date is after it, unavailable
    if expected_turn_in_date is not None:
        if isinstance(expected_turn_in_date, str):
            expected_turn_in_date = parse_date_string(expected_turn_in_date)
        elif isinstance(expected_turn_in_date, datetime):
            expected_turn_in_date = expected_turn_in_date.date()

        if target_date > expected_turn_in_date:
            return False

    return True


def has_overlapping_activity(vin: str, target_date: date, activity_df: pd.DataFrame) -> bool:
    """
    Check if VIN has any overlapping activity on the target date.

    Args:
        vin: Vehicle VIN to check
        target_date: The date to check for activities
        activity_df: DataFrame with activity records

    Returns:
        True if there's an overlapping activity, False otherwise
    """
    if activity_df.empty:
        return False

    # Filter activities for this VIN
    vin_activities = activity_df[activity_df['vin'] == vin]

    if vin_activities.empty:
        return False

    # Check each activity for date overlap
    for _, activity in vin_activities.iterrows():
        activity_type = activity.get('activity_type', '')
        start_date = activity.get('start_date')
        end_date = activity.get('end_date')

        # Skip activities that don't block availability
        if activity_type not in {'loan', 'service', 'hold', 'event', 'storage'}:
            continue

        # Convert dates to date objects
        if pd.isna(start_date) or pd.isna(end_date):
            continue

        if isinstance(start_date, str):
            start_date = parse_date_string(start_date)
        elif isinstance(start_date, datetime):
            start_date = start_date.date()

        if isinstance(end_date, str):
            end_date = parse_date_string(end_date)
        elif isinstance(end_date, datetime):
            end_date = end_date.date()

        # Check if target_date overlaps with activity period
        if start_date <= target_date <= end_date:
            return True

    return False


def build_availability_grid(
    vehicles_df: pd.DataFrame,
    activity_df: pd.DataFrame,
    week_start: str,
    office: str
) -> pd.DataFrame:
    """
    Build a 7-day availability grid for vehicles in a specific office.

    Args:
        vehicles_df: DataFrame with vehicle information
        activity_df: DataFrame with current vehicle activities
        week_start: Start date of the week in YYYY-MM-DD format (Monday)
        office: Office to filter vehicles by

    Returns:
        DataFrame with columns [vin, day, office, available] covering 7 days
        Each row represents one VIN for one day with availability status
    """
    # Filter vehicles to the specified office
    office_vehicles = vehicles_df[vehicles_df['office'] == office].copy()

    # Generate 7-day range
    week_days = generate_week_range(week_start)

    # Build result rows
    result_rows = []

    for _, vehicle in office_vehicles.iterrows():
        vin = vehicle['vin']
        in_service_date = vehicle.get('in_service_date')
        expected_turn_in_date = vehicle.get('expected_turn_in_date')

        for day in week_days:
            # Check lifecycle window
            lifecycle_available = is_date_in_lifecycle_window(
                day, in_service_date, expected_turn_in_date
            )

            # Check for overlapping activities
            has_activity = has_overlapping_activity(vin, day, activity_df)

            # Available if within lifecycle window AND no blocking activities
            available = lifecycle_available and not has_activity

            result_rows.append({
                'vin': vin,
                'day': day,
                'office': office,
                'available': available
            })

    # Convert to DataFrame with proper column order
    result_df = pd.DataFrame(result_rows, columns=['vin', 'day', 'office', 'available'])

    return result_df