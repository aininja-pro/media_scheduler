"""
Phase 7.7: Dynamic Capacity Management

Handles day-specific slots, travel days, and blackouts from ops_capacity_calendar.
Capacity constrains start days (not occupancy).
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any


# Default weekday capacity if not specified
DEFAULT_WEEKDAY_SLOTS = 15
DEFAULT_WEEKEND_SLOTS = 0


def load_capacity_calendar(
    ops_capacity_df: pd.DataFrame,
    office: str,
    week_start: str,
    default_weekday_slots: int = DEFAULT_WEEKDAY_SLOTS,
    default_weekend_slots: int = DEFAULT_WEEKEND_SLOTS
) -> Tuple[Dict[datetime.date, int], Dict[datetime.date, str]]:
    """
    Load capacity calendar for a specific office and week.

    Args:
        ops_capacity_df: DataFrame from ops_capacity_calendar table
        office: Target office
        week_start: Monday of the week (YYYY-MM-DD)
        default_weekday_slots: Default for Mon-Fri if not specified
        default_weekend_slots: Default for Sat-Sun if not specified

    Returns:
        Tuple of (capacity_map, notes_map)
        - capacity_map: Dict mapping date to slots
        - notes_map: Dict mapping date to notes (if any)
    """
    week_start_date = pd.to_datetime(week_start)
    capacity_map = {}
    notes_map = {}

    # Process each day of the week
    for day_offset in range(7):  # Mon-Sun
        current_date = week_start_date + timedelta(days=day_offset)
        date_only = current_date.date()

        # Check if this date has explicit capacity
        if not ops_capacity_df.empty:
            date_capacity = ops_capacity_df[
                (ops_capacity_df['office'] == office) &
                (pd.to_datetime(ops_capacity_df['date']).dt.date == date_only)
            ]

            if not date_capacity.empty:
                row = date_capacity.iloc[0]
                slots = int(row['slots']) if pd.notna(row['slots']) else 0
                capacity_map[date_only] = slots

                # Add notes if present
                if 'notes' in row and pd.notna(row['notes']) and row['notes']:
                    notes_map[date_only] = str(row['notes'])
            else:
                # Use default based on weekday
                is_weekend = current_date.dayofweek >= 5  # Saturday=5, Sunday=6
                capacity_map[date_only] = (
                    default_weekend_slots if is_weekend
                    else default_weekday_slots
                )
        else:
            # No capacity data - use defaults
            is_weekend = current_date.dayofweek >= 5
            capacity_map[date_only] = (
                default_weekend_slots if is_weekend
                else default_weekday_slots
            )

    return capacity_map, notes_map


def identify_special_days(
    capacity_map: Dict[datetime.date, int],
    notes_map: Dict[datetime.date, str]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Identify blackouts, travel days, and other special capacity days.

    Args:
        capacity_map: Dict mapping date to slots
        notes_map: Dict mapping date to notes

    Returns:
        Dict with lists of special days by type
    """
    special_days = {
        'blackouts': [],
        'travel_days': [],
        'reduced_capacity': [],
        'increased_capacity': []
    }

    for date, slots in capacity_map.items():
        day_name = date.strftime('%A')
        date_str = date.strftime('%Y-%m-%d')
        notes = notes_map.get(date, '')

        # Blackout (0 slots)
        if slots == 0:
            special_days['blackouts'].append({
                'date': date_str,
                'day': day_name,
                'notes': notes or 'Blackout'
            })

        # Travel day (usually reduced capacity with specific note)
        elif 'travel' in notes.lower():
            special_days['travel_days'].append({
                'date': date_str,
                'day': day_name,
                'slots': slots,
                'notes': notes
            })

        # Reduced capacity (less than default but not 0)
        elif slots > 0 and slots < DEFAULT_WEEKDAY_SLOTS and date.weekday() < 5:
            special_days['reduced_capacity'].append({
                'date': date_str,
                'day': day_name,
                'slots': slots,
                'reduction': DEFAULT_WEEKDAY_SLOTS - slots,
                'notes': notes
            })

        # Increased capacity (more than default)
        elif slots > DEFAULT_WEEKDAY_SLOTS and date.weekday() < 5:
            special_days['increased_capacity'].append({
                'date': date_str,
                'day': day_name,
                'slots': slots,
                'increase': slots - DEFAULT_WEEKDAY_SLOTS,
                'notes': notes
            })

    return special_days


def build_capacity_report(
    selected_assignments: List[Dict[str, Any]],
    capacity_map: Dict[datetime.date, int],
    notes_map: Dict[datetime.date, str],
    week_start: str
) -> Dict[str, Any]:
    """
    Build comprehensive capacity utilization report.

    Args:
        selected_assignments: List of selected assignments
        capacity_map: Dict mapping date to slots
        notes_map: Dict mapping date to notes
        week_start: Monday of the week

    Returns:
        Dict with daily usage and capacity analysis
    """
    week_start_date = pd.to_datetime(week_start)

    # Count starts per day
    starts_per_day = {}
    for assignment in selected_assignments:
        start_day = assignment['start_day']
        starts_per_day[start_day] = starts_per_day.get(start_day, 0) + 1

    # Build daily report
    daily_usage = []
    capacity_notes = []
    total_capacity = 0
    total_used = 0

    for day_offset in range(7):  # Mon-Sun
        current_date = week_start_date + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y-%m-%d')
        day_name = current_date.strftime('%A')
        date_only = current_date.date()

        capacity = capacity_map.get(date_only, 0)
        used = starts_per_day.get(date_str, 0)
        remaining = capacity - used
        utilization = (used / capacity * 100) if capacity > 0 else 0

        daily_entry = {
            'date': date_str,
            'day': day_name,
            'capacity': capacity,
            'used': used,
            'remaining': remaining,
            'utilization_pct': round(utilization, 1)
        }

        # Add notes if present
        if date_only in notes_map:
            daily_entry['notes'] = notes_map[date_only]
            capacity_notes.append({
                'date': date_str,
                'day': day_name,
                'notes': notes_map[date_only]
            })

        daily_usage.append(daily_entry)
        total_capacity += capacity
        total_used += used

    # Identify special days
    special_days = identify_special_days(capacity_map, notes_map)

    # Calculate overall metrics
    overall_utilization = (total_used / total_capacity * 100) if total_capacity > 0 else 0

    return {
        'daily_usage': daily_usage,
        'capacity_notes': capacity_notes,
        'special_days': special_days,
        'summary': {
            'total_capacity': total_capacity,
            'total_used': total_used,
            'total_remaining': total_capacity - total_used,
            'overall_utilization_pct': round(overall_utilization, 1),
            'blackout_days': len(special_days['blackouts']),
            'travel_days': len(special_days['travel_days']),
            'days_with_notes': len(capacity_notes)
        }
    }


def validate_capacity_compliance(
    selected_assignments: List[Dict[str, Any]],
    capacity_map: Dict[datetime.date, int]
) -> Tuple[bool, List[str]]:
    """
    Validate that assignments comply with capacity constraints.

    Args:
        selected_assignments: List of selected assignments
        capacity_map: Dict mapping date to slots

    Returns:
        Tuple of (is_valid, violations)
        - is_valid: True if all constraints met
        - violations: List of violation messages
    """
    violations = []
    starts_per_day = {}

    # Count starts per day
    for assignment in selected_assignments:
        start_date = pd.to_datetime(assignment['start_day']).date()
        starts_per_day[start_date] = starts_per_day.get(start_date, 0) + 1

    # Check each day
    for date, count in starts_per_day.items():
        capacity = capacity_map.get(date, DEFAULT_WEEKDAY_SLOTS)

        if count > capacity:
            violations.append(
                f"{date.strftime('%Y-%m-%d')}: {count} starts exceeds capacity {capacity}"
            )

        if capacity == 0 and count > 0:
            violations.append(
                f"{date.strftime('%Y-%m-%d')}: {count} starts on blackout day"
            )

    return len(violations) == 0, violations