"""
Smart scheduling logic for Chain Builder

Finds available gaps in partner's schedule to thread chain through existing
commitments — or, when double-booking is allowed, keeps the requested dates and
reports the overlaps instead of moving them.
"""

import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Statuses that mean a scheduled assignment really occupies the partner.
# Anything else (cancelled, rejected, ...) must not push a chain around.
# Mirrors _is_real_partner_blocker in routers/chain_builder.py.
BLOCKING_STATUSES = {'planned', 'manual', 'requested', 'active'}


def _is_real_blocker(status) -> bool:
    if status is None or pd.isna(status):
        return True
    return str(status).strip().lower() in BLOCKING_STATUSES


def _overlaps(slot_start: datetime, slot_end: datetime,
              busy_start: datetime, busy_end: datetime) -> bool:
    """True when a slot genuinely collides with a busy period.

    Strict on both edges so same-day handoffs are allowed in either direction:
    a slot may start the day a loan ends, and may end the day one begins.
    """
    return slot_start < busy_end and slot_end > busy_start


def build_vehicle_lookup(vehicles_df: pd.DataFrame) -> Dict[str, str]:
    """Map VIN -> 'Make Model'.

    current_activity stores only vehicle_vin — no make or model — so without
    this every active loan is labelled by its activity_type alone. Two loans
    then both read 'Loan' and look like one row duplicated.
    """
    if vehicles_df is None or vehicles_df.empty or 'vin' not in vehicles_df.columns:
        return {}

    lookup = {}
    for _, vehicle in vehicles_df.iterrows():
        vin = vehicle.get('vin')
        if not vin or pd.isna(vin):
            continue
        name = ' '.join(
            str(p) for p in (vehicle.get('make'), vehicle.get('model'))
            if p and pd.notna(p)
        ).strip()
        if name:
            lookup[str(vin)] = name

    return lookup


def _vehicle_name(row, vin_key: str, vehicle_lookup: Dict[str, str]) -> str:
    """Name the vehicle on a busy period, most specific source first."""
    name = ' '.join(
        str(p) for p in (row.get('make'), row.get('model')) if p and pd.notna(p)
    ).strip()
    if name:
        return name

    vin = row.get(vin_key)
    if vin and pd.notna(vin):
        # Fall back to the VIN suffix so two loans are never labelled alike
        return vehicle_lookup.get(str(vin)) or f"VIN ...{str(vin)[-6:]}"

    return ''


def _describe(row, vin_key: str, start, end, vehicle_lookup: Dict[str, str],
              include_activity_type: bool = False) -> str:
    """Human-readable label for a busy period.

    e.g. 'Loan: Toyota Camry (2026-02-24 to 2027-02-24)'. current_activity rows
    keep their activity_type because they are not always loans — Hold, Service
    and Event rows land in the same table.
    """
    name = _vehicle_name(row, vin_key, vehicle_lookup)

    if include_activity_type:
        activity_type = str(row.get('activity_type') or '').strip()
        if activity_type and name:
            name = f"{activity_type}: {name}"
        elif activity_type:
            name = activity_type

    if not name:
        name = 'Existing loan'

    return f"{name} ({_fmt(start)} to {_fmt(end)})"


def _fmt(value) -> str:
    parsed = pd.to_datetime(value, errors='coerce')
    return str(value) if pd.isna(parsed) else parsed.strftime('%Y-%m-%d')


def get_partner_busy_periods(
    person_id: int,
    current_activity_df: pd.DataFrame,
    scheduled_assignments_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    vehicles_df: pd.DataFrame = None
) -> List[Dict[str, Any]]:
    """
    Get all periods when partner is busy (has existing commitments).

    Args:
        person_id: Partner ID
        current_activity_df: Current active loans
        scheduled_assignments_df: Scheduled assignments
        start_date: Start of chain period (YYYY-MM-DD)
        end_date: End of chain period (YYYY-MM-DD)

    Returns:
        List of {'start': datetime, 'end': datetime, 'label': str} busy periods
    """
    busy_periods = []
    vehicle_lookup = build_vehicle_lookup(vehicles_df)

    # Parse chain period
    chain_start = datetime.strptime(start_date, '%Y-%m-%d')
    chain_end = datetime.strptime(end_date, '%Y-%m-%d')

    # Add current active loans
    if not current_activity_df.empty:
        # Ensure person_id type matching (drop NULL person_id rows before casting to int)
        current_activity_df = current_activity_df.copy()
        if 'person_id' in current_activity_df.columns:
            current_activity_df = current_activity_df.dropna(subset=['person_id'])
            current_activity_df['person_id'] = current_activity_df['person_id'].astype(int)

        partner_active = current_activity_df[current_activity_df['person_id'] == int(person_id)]
        logger.info(f"Found {len(partner_active)} current active loans for partner {person_id}")
        for _, activity in partner_active.iterrows():
            if pd.notna(activity.get('start_date')) and pd.notna(activity.get('end_date')):
                act_start = pd.to_datetime(activity['start_date'])
                act_end = pd.to_datetime(activity['end_date'])

                # Only include if overlaps with chain period
                if act_end >= chain_start and act_start <= chain_end:
                    busy_periods.append({
                        'start': act_start,
                        'end': act_end,
                        'label': _describe(activity, 'vehicle_vin', act_start, act_end,
                                           vehicle_lookup, include_activity_type=True),
                    })

    # Add scheduled assignments
    if not scheduled_assignments_df.empty and 'person_id' in scheduled_assignments_df.columns:
        scheduled_assignments_df = scheduled_assignments_df.copy()
        scheduled_assignments_df['_pid_numeric'] = pd.to_numeric(
            scheduled_assignments_df['person_id'], errors='coerce'
        )
        partner_scheduled = scheduled_assignments_df[
            scheduled_assignments_df['_pid_numeric'] == int(person_id)
        ]
        logger.info(f"Found {len(partner_scheduled)} scheduled assignments for partner {person_id}")

        for _, assignment in partner_scheduled.iterrows():
            # Cancelled/rejected rows must not push the chain around
            if not _is_real_blocker(assignment.get('status')):
                continue

            if pd.notna(assignment.get('start_day')) and pd.notna(assignment.get('end_day')):
                sched_start = pd.to_datetime(assignment['start_day'])
                sched_end = pd.to_datetime(assignment['end_day'])

                # Only include if overlaps with chain period
                if sched_end >= chain_start and sched_start <= chain_end:
                    busy_periods.append({
                        'start': sched_start,
                        'end': sched_end,
                        'label': _describe(assignment, 'vin', sched_start, sched_end,
                                           vehicle_lookup),
                    })

    # Sort by start date
    busy_periods.sort(key=lambda p: p['start'])

    logger.info(f"Partner {person_id} has {len(busy_periods)} busy periods in chain window")

    return busy_periods


def _next_weekday(date: datetime) -> datetime:
    while date.weekday() >= 5:  # 5=Sat, 6=Sun
        date += timedelta(days=1)
    return date


def _slot_end(start: datetime, days_per_slot: int) -> datetime:
    """A 7-day loan runs Thursday to Thursday: 7 nights, 8 calendar days,
    with same-day handoff to the next slot. Dropoff always lands on a weekday."""
    return _next_weekday(start + timedelta(days=days_per_slot))


def find_available_slots(
    busy_periods: List[Dict[str, Any]],
    chain_start: datetime,
    chain_end: datetime,
    num_slots: int,
    days_per_slot: int = 7,
    allow_double_booking: bool = False
) -> List[Dict[str, Any]]:
    """
    Build the chain's slot dates.

    Two modes:
      - allow_double_booking=False (default): thread the chain through the gaps
        in the partner's schedule, pushing past anything in the way.
      - allow_double_booking=True: run straight from the requested start date and
        report the overlaps rather than moving around them. This is what lets a
        partner hold a long-term loan (or a Car and Driver style multi-car week)
        and still take more vehicles.

    Args:
        busy_periods: [{'start': datetime, 'end': datetime, 'label': str}]
        chain_start: Desired chain start date
        chain_end: End of chain search period
        num_slots: Number of slots to find
        days_per_slot: Days per vehicle loan
        allow_double_booking: Keep requested dates and flag overlaps

    Returns:
        List of slot dicts with slot, start_date, end_date, and conflicts
        (a list of human-readable labels — empty when the slot is clear)
    """
    if allow_double_booking:
        return _build_slots_from_requested_date(
            busy_periods, chain_start, num_slots, days_per_slot
        )

    slots = []
    current_date = _next_weekday(chain_start)

    while len(slots) < num_slots and current_date <= chain_end:
        current_date = _next_weekday(current_date)

        if current_date > chain_end:
            logger.warning(
                f"Reached end of search window at {current_date.strftime('%Y-%m-%d')}, "
                f"found {len(slots)}/{num_slots} slots"
            )
            break

        slot_end = _slot_end(current_date, days_per_slot)

        # Push past the first busy period this slot runs into
        conflict = next(
            (p for p in busy_periods if _overlaps(current_date, slot_end, p['start'], p['end'])),
            None
        )

        if conflict:
            current_date = _next_weekday(conflict['end'])
            continue

        slots.append({
            'slot': len(slots) + 1,
            'start_date': current_date.strftime('%Y-%m-%d'),
            'end_date': slot_end.strftime('%Y-%m-%d'),
            'conflicts': []
        })

        # Start the NEXT vehicle the day this one ends — a true chain, with
        # pickup and dropoff on the same day.
        current_date = _next_weekday(slot_end)

    logger.info(f"Found {len(slots)} available slots (requested {num_slots})")

    return slots


def _build_slots_from_requested_date(
    busy_periods: List[Dict[str, Any]],
    chain_start: datetime,
    num_slots: int,
    days_per_slot: int
) -> List[Dict[str, Any]]:
    """Lay the chain out back-to-back from the requested date, recording overlaps.

    Never skips or moves a slot: the scheduler asked for these dates and gets
    them, with a warning attached to whichever slots double-book the partner.
    """
    slots = []
    current_date = _next_weekday(chain_start)

    for index in range(num_slots):
        slot_end = _slot_end(current_date, days_per_slot)

        conflicts = [
            p['label'] for p in busy_periods
            if _overlaps(current_date, slot_end, p['start'], p['end'])
        ]

        slots.append({
            'slot': index + 1,
            'start_date': current_date.strftime('%Y-%m-%d'),
            'end_date': slot_end.strftime('%Y-%m-%d'),
            'conflicts': conflicts
        })

        current_date = _next_weekday(slot_end)

    double_booked = sum(1 for s in slots if s['conflicts'])
    logger.info(
        f"Built {len(slots)} slots from requested start date "
        f"({double_booked} double-booked)"
    )

    return slots


def adjust_chain_for_existing_commitments(
    person_id: int,
    start_date: str,
    num_vehicles: int,
    days_per_loan: int,
    current_activity_df: pd.DataFrame,
    scheduled_assignments_df: pd.DataFrame,
    allow_double_booking: bool = False,
    vehicles_df: pd.DataFrame = None
) -> List[Dict[str, Any]]:
    """
    Smart chain building that works around existing commitments.

    By default this finds gaps and threads the chain through them. With
    allow_double_booking=True it honours the requested start date instead and
    tags any slot that overlaps an existing commitment.

    Args:
        person_id: Partner ID
        start_date: Desired chain start date
        num_vehicles: Number of vehicles in chain
        days_per_loan: Days per vehicle
        current_activity_df: Current active loans
        scheduled_assignments_df: Scheduled assignments
        allow_double_booking: Keep the requested dates and report overlaps

    Returns:
        List of slots with start_date, end_date and a 'conflicts' list
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
        end_date=chain_end.strftime('%Y-%m-%d'),
        vehicles_df=vehicles_df
    )

    return find_available_slots(
        busy_periods=busy_periods,
        chain_start=chain_start,
        chain_end=chain_end,
        num_slots=num_vehicles,
        days_per_slot=days_per_loan,
        allow_double_booking=allow_double_booking
    )


def summarize_schedule_adjustment(
    requested_start: str,
    slots: List[Dict[str, Any]],
    num_requested: int
) -> Dict[str, Any]:
    """Explain what the scheduler did with the requested dates, for the UI.

    Chains used to silently come back on completely different dates with no
    indication why. This gives the frontend everything it needs to say so.
    """
    actual_start = slots[0]['start_date'] if slots else None
    double_booked = [
        {'slot': s['slot'], 'start_date': s['start_date'],
         'end_date': s['end_date'], 'conflicts': s['conflicts']}
        for s in slots if s.get('conflicts')
    ]

    # Grouped the other way round: one row per existing loan, listing the slots
    # it blocks. A partner on two year-long loans collides with every slot, so
    # the per-slot list repeats the same two loans N times — the useful question
    # is "what am I double-booking against", and that has only two answers here.
    by_conflict: Dict[str, List[int]] = {}
    for slot in slots:
        for label in slot.get('conflicts', []):
            by_conflict.setdefault(label, []).append(slot['slot'])

    conflict_summary = [
        {'label': label, 'slots': slot_numbers}
        for label, slot_numbers in by_conflict.items()
    ]

    return {
        'requested_start_date': requested_start,
        'actual_start_date': actual_start,
        'start_date_moved': bool(actual_start) and actual_start != requested_start,
        'slots_requested': num_requested,
        'slots_returned': len(slots),
        'double_booked_slots': double_booked,
        'conflict_summary': conflict_summary,
        'has_double_booking': bool(double_booked),
    }
