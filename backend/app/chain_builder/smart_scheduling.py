"""
Smart scheduling logic for Chain Builder

Finds available gaps in partner's schedule to thread chain through existing commitments
"""

import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def get_partner_busy_periods(
    person_id: int,
    current_activity_df: pd.DataFrame,
    scheduled_assignments_df: pd.DataFrame,
    start_date: str,
    end_date: str
) -> List[Tuple[datetime, datetime]]:
    """
    Get all periods when partner is busy (has existing commitments).

    Args:
        person_id: Partner ID
        current_activity_df: Current active loans
        scheduled_assignments_df: Scheduled assignments
        start_date: Start of chain period (YYYY-MM-DD)
        end_date: End of chain period (YYYY-MM-DD)

    Returns:
        List of (start_datetime, end_datetime) tuples representing busy periods
    """
    busy_periods = []

    # Parse chain period
    chain_start = datetime.strptime(start_date, '%Y-%m-%d')
    chain_end = datetime.strptime(end_date, '%Y-%m-%d')

    # Add current active loans
    if not current_activity_df.empty:
        # Ensure person_id type matching
        current_activity_df = current_activity_df.copy()
        if 'person_id' in current_activity_df.columns:
            current_activity_df['person_id'] = current_activity_df['person_id'].astype(int)

        partner_active = current_activity_df[current_activity_df['person_id'] == int(person_id)]
        logger.info(f"Found {len(partner_active)} current active loans for partner {person_id}")
        for _, activity in partner_active.iterrows():
            if pd.notna(activity.get('start_date')) and pd.notna(activity.get('end_date')):
                act_start = pd.to_datetime(activity['start_date'])
                act_end = pd.to_datetime(activity['end_date'])

                # Only include if overlaps with chain period
                if act_end >= chain_start and act_start <= chain_end:
                    busy_periods.append((act_start, act_end))

    # Add scheduled assignments
    if not scheduled_assignments_df.empty:
        partner_scheduled = scheduled_assignments_df[
            scheduled_assignments_df['person_id'] == int(person_id)
        ]
        for _, assignment in partner_scheduled.iterrows():
            if pd.notna(assignment.get('start_day')) and pd.notna(assignment.get('end_day')):
                # Parse as local dates (avoid timezone issues)
                start_parts = str(assignment['start_day']).split('-')
                end_parts = str(assignment['end_day']).split('-')

                if len(start_parts) == 3 and len(end_parts) == 3:
                    sched_start = datetime(int(start_parts[0]), int(start_parts[1]), int(start_parts[2]))
                    sched_end = datetime(int(end_parts[0]), int(end_parts[1]), int(end_parts[2]))

                    # Only include if overlaps with chain period
                    if sched_end >= chain_start and sched_start <= chain_end:
                        busy_periods.append((sched_start, sched_end))

    # Sort by start date
    busy_periods.sort(key=lambda x: x[0])

    logger.info(f"Partner {person_id} has {len(busy_periods)} busy periods in chain window")

    return busy_periods


def find_available_slots(
    busy_periods: List[Tuple[datetime, datetime]],
    chain_start: datetime,
    chain_end: datetime,
    num_slots: int,
    days_per_slot: int = 7
) -> List[Dict[str, Any]]:
    """
    Find available time slots that thread through busy periods.

    Args:
        busy_periods: List of (start, end) tuples when partner is busy
        chain_start: Desired chain start date
        chain_end: End of chain search period
        num_slots: Number of slots to find
        days_per_slot: Days per vehicle loan

    Returns:
        List of slot dictionaries with start_date, end_date
    """
    slots = []
    current_date = chain_start

    while len(slots) < num_slots and current_date <= chain_end:
        # Skip weekends for start dates
        while current_date.weekday() >= 5:  # 5=Sat, 6=Sun
            current_date += timedelta(days=1)

        if current_date > chain_end:
            logger.warning(f"Reached end of search window at {current_date.strftime('%Y-%m-%d')}, found {len(slots)}/{num_slots} slots")
            break

        # Calculate slot end date
        slot_end = current_date + timedelta(days=days_per_slot - 1)

        # If slot ends on weekend, extend to Monday (dropoff on weekday)
        while slot_end.weekday() >= 5:  # 5=Sat, 6=Sun
            slot_end += timedelta(days=1)

        # Check if this slot conflicts with any busy period
        conflicts = False
        for busy_start, busy_end in busy_periods:
            # Check if slot overlaps with busy period
            # Allow same-day pickup: if busy ends on date X, we can start on date X
            # So conflict only if: slot_start < busy_end (not <=)
            if current_date < busy_end and slot_end >= busy_start:
                conflicts = True

                # Jump to end of busy period (same day pickup allowed)
                current_date = busy_end

                # Skip weekends
                while current_date.weekday() >= 5:  # 5=Sat, 6=Sun
                    current_date += timedelta(days=1)

                break

        if not conflicts:
            # This slot is available!
            slots.append({
                'slot': len(slots) + 1,
                'start_date': current_date.strftime('%Y-%m-%d'),
                'end_date': slot_end.strftime('%Y-%m-%d')
            })

            # Move to next potential slot - start the NEXT vehicle same day this one ends
            # This creates a true "chain" where pickup/dropoff happen same day
            current_date = slot_end

            # Skip weekends
            while current_date.weekday() >= 5:  # 5=Sat, 6=Sun
                current_date += timedelta(days=1)
        # If conflicts, current_date was already updated in the loop

    logger.info(f"Found {len(slots)} available slots (requested {num_slots})")

    return slots


def adjust_chain_for_existing_commitments(
    person_id: int,
    start_date: str,
    num_vehicles: int,
    days_per_loan: int,
    current_activity_df: pd.DataFrame,
    scheduled_assignments_df: pd.DataFrame
) -> List[Dict[str, Any]]:
    """
    Smart chain building that works around existing commitments.

    Instead of blocking dates with existing assignments, this finds
    gaps and threads the chain through them.

    Args:
        person_id: Partner ID
        start_date: Desired chain start date
        num_vehicles: Number of vehicles in chain
        days_per_loan: Days per vehicle
        current_activity_df: Current active loans
        scheduled_assignments_df: Scheduled assignments

    Returns:
        List of available slots with start/end dates that avoid conflicts
    """
    # Calculate search window (generous - look 2x expected duration)
    chain_start = datetime.strptime(start_date, '%Y-%m-%d')
    expected_duration = num_vehicles * days_per_loan
    chain_end = chain_start + timedelta(days=expected_duration * 2)

    # Get partner's busy periods
    busy_periods = get_partner_busy_periods(
        person_id=person_id,
        current_activity_df=current_activity_df,
        scheduled_assignments_df=scheduled_assignments_df,
        start_date=start_date,
        end_date=chain_end.strftime('%Y-%m-%d')
    )

    # Find available slots that thread through busy periods
    available_slots = find_available_slots(
        busy_periods=busy_periods,
        chain_start=chain_start,
        chain_end=chain_end,
        num_slots=num_vehicles,
        days_per_slot=days_per_loan
    )

    return available_slots
