"""
Sequential availability checking for Chain Builder

Checks vehicle availability across multi-week chain periods
"""

import pandas as pd
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import date, datetime, timedelta
import logging

from .smart_scheduling import BLOCKING_STATUSES

logger = logging.getLogger(__name__)


def _norm_vin(value) -> str:
    """VINs must match even when one side is padded or a different type."""
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _as_date(value) -> Optional[date]:
    """Accept YYYY-MM-DD, ISO timestamps, date, or datetime."""
    parsed = pd.to_datetime(value, errors='coerce')
    if pd.isna(parsed):
        return None
    return parsed.date()


def _is_blocking_status(status) -> bool:
    if status is None:
        return True
    try:
        if pd.isna(status):
            return True
    except (TypeError, ValueError):
        pass
    return str(status).strip().lower() in BLOCKING_STATUSES


def _date_is_held(check_date: date, start: date, end: date) -> bool:
    """True when this calendar day is taken.

    Exclusive on the end so a same-day handoff is allowed: a loan ending
    Monday does not hide the car from a loan starting Monday.
    """
    return start <= check_date < end


def _index_vehicle_holds(
    df: Optional[pd.DataFrame],
    vin_columns: Tuple[str, ...],
    start_col: str,
    end_col: str,
    person_col: str = 'person_id',
    status_col: Optional[str] = None,
) -> Dict[str, List[Tuple[date, date, Optional[int]]]]:
    """Group holds by VIN so each vehicle/day check is a short list lookup."""
    holds: Dict[str, List[Tuple[date, date, Optional[int]]]] = {}
    if df is None or df.empty:
        return holds

    vin_col = next((col for col in vin_columns if col in df.columns), None)
    if not vin_col or start_col not in df.columns or end_col not in df.columns:
        return holds

    for _, row in df.iterrows():
        if status_col and status_col in df.columns and not _is_blocking_status(row.get(status_col)):
            continue
        vin = _norm_vin(row.get(vin_col))
        start = _as_date(row.get(start_col))
        end = _as_date(row.get(end_col))
        if not vin or not start or not end:
            continue
        person_id = None
        if person_col in df.columns:
            pid = pd.to_numeric(row.get(person_col), errors='coerce')
            if pd.notna(pid):
                person_id = int(pid)
        holds.setdefault(vin, []).append((start, end, person_id))
    return holds


def build_chain_availability_grid(
    vehicles_df: pd.DataFrame,
    activity_df: pd.DataFrame,
    start_date: str,
    num_slots: int,
    days_per_slot: int = 7,
    office: str = None,
    end_date: str = None,  # NEW: explicit end date if provided
    scheduled_assignments_df: pd.DataFrame = None,  # NEW: scheduled assignments to check conflicts
    current_person_id: int = None  # NEW: exclude this partner's assignments from conflict checking
) -> pd.DataFrame:
    """
    Build availability grid covering entire chain period.

    Args:
        vehicles_df: All vehicles (will be filtered to office)
        activity_df: Current activity data (active loans - BLUE)
        start_date: Chain start date (YYYY-MM-DD)
        num_slots: Number of vehicles in chain
        days_per_slot: Days per vehicle loan (default 7)
        office: Office to filter vehicles (optional)
        end_date: Explicit end date (YYYY-MM-DD) - overrides calculation
        scheduled_assignments_df: Scheduled assignments (planned/manual/requested - GREEN/MAGENTA)
        current_person_id: Partner ID building the chain (exclude their assignments from conflicts)

    Returns:
        DataFrame with columns: vin, date, available (boolean)
        Covers full chain duration

    Note:
        Green (saved), magenta (requested), and blue (active) assignments for
        OTHER partners hold the vehicle on overlapping dates. The dropoff day
        stays free so a same-day handoff still works. Cancelled/completed rows
        do not hold the car.
    """

    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')

        # Use explicit end_date if provided, otherwise calculate
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            chain_duration_days = (end_dt - start_dt).days + 1
        else:
            # Calculate chain duration
            chain_duration_days = num_slots * days_per_slot
            end_dt = start_dt + timedelta(days=chain_duration_days - 1)

        logger.info(f"Building availability grid: {start_date} to {end_dt.strftime('%Y-%m-%d')} ({chain_duration_days} days)")

        # Filter vehicles to office
        if office:
            vehicles_df = vehicles_df[vehicles_df['office'] == office].copy()

        # Index holds once. Looking them up per vehicle-day used to miss rows
        # when VIN types didn't match, and re-scanned the full table every day.
        activity_holds = _index_vehicle_holds(
            activity_df, ('vin', 'vehicle_vin'), 'start_date', 'end_date'
        )
        scheduled_holds = _index_vehicle_holds(
            scheduled_assignments_df, ('vin',), 'start_day', 'end_day',
            status_col='status',
        )
        current_pid = int(current_person_id) if current_person_id is not None else None

        availability_records = []

        for _, vehicle in vehicles_df.iterrows():
            vin = _norm_vin(vehicle['vin'])

            # expected_turn_in_date is deliberately NOT used here: FMS treats it
            # as an estimate and keeps booking vehicles past it, so it must never
            # block availability. Endpoints surface it as a warning instead.
            in_service_date = _as_date(vehicle.get('in_service_date'))

            current_date = start_dt.date()
            for day_offset in range(chain_duration_days):
                check_date = current_date + timedelta(days=day_offset)

                lifecycle_available = not (in_service_date and check_date < in_service_date)

                activity_conflict = any(
                    _date_is_held(check_date, start, end)
                    for start, end, _pid in activity_holds.get(vin, [])
                )

                # Green/magenta/blue holds from OTHER partners. This partner's
                # own rows stay visible so they can reopen a slot they already
                # filled. Same-day handoff (exclusive end) stays allowed.
                scheduled_conflict = False
                for start, end, holder_id in scheduled_holds.get(vin, []):
                    if current_pid is not None and holder_id == current_pid:
                        continue
                    if _date_is_held(check_date, start, end):
                        scheduled_conflict = True
                        break

                available = lifecycle_available and not activity_conflict and not scheduled_conflict

                reason = 'available'
                if not available:
                    if not lifecycle_available:
                        reason = 'lifecycle'
                    elif activity_conflict:
                        reason = 'activity_conflict'
                    elif scheduled_conflict:
                        reason = 'scheduled_conflict'

                availability_records.append({
                    'vin': vin,
                    'date': check_date,
                    'available': available,
                    'reason': reason
                })

        availability_df = pd.DataFrame(availability_records)
        logger.info(f"Built availability grid: {len(availability_df)} records for {len(vehicles_df)} vehicles")

        return availability_df

    except Exception as e:
        logger.error(f"Error building chain availability grid: {str(e)}")
        return pd.DataFrame()


def check_slot_availability(
    vin: str,
    slot_start: str,
    slot_end: str,
    availability_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Check if a specific vehicle is available for a specific slot.

    Args:
        vin: Vehicle VIN
        slot_start: Slot start date (YYYY-MM-DD)
        slot_end: Slot end date (YYYY-MM-DD)
        availability_df: Availability grid from build_chain_availability_grid()

    Returns:
        Dictionary with:
        - available: Boolean
        - days_available: Number of days available in slot
        - days_required: Number of days in slot
        - unavailable_dates: List of dates where vehicle is not available
    """

    try:
        # Convert dates
        start_dt = datetime.strptime(slot_start, '%Y-%m-%d').date()
        end_dt = datetime.strptime(slot_end, '%Y-%m-%d').date()

        # Get all dates in slot range
        slot_dates = []
        current = start_dt
        while current <= end_dt:
            slot_dates.append(current)
            current += timedelta(days=1)

        days_required = len(slot_dates)

        vehicle_availability = availability_df[
            (availability_df['vin'].astype(str).str.strip() == _norm_vin(vin)) &
            (availability_df['date'] >= start_dt) &
            (availability_df['date'] <= end_dt)
        ]

        if vehicle_availability.empty:
            return {
                'available': False,
                'days_available': 0,
                'days_required': days_required,
                'unavailable_dates': [d.strftime('%Y-%m-%d') for d in slot_dates],
                'reason': 'No availability data'
            }

        # Check if available for ALL days in slot
        available_dates = set(vehicle_availability[vehicle_availability['available'] == True]['date'].tolist())
        unavailable_dates = [d for d in slot_dates if d not in available_dates]

        is_available = len(unavailable_dates) == 0

        return {
            'available': is_available,
            'days_available': len(available_dates),
            'days_required': days_required,
            'unavailable_dates': [d.strftime('%Y-%m-%d') for d in unavailable_dates],
            'reason': 'Available for all days' if is_available else f'Unavailable on {len(unavailable_dates)} days'
        }

    except Exception as e:
        logger.error(f"Error checking slot availability for {vin}: {str(e)}")
        return {
            'available': False,
            'days_available': 0,
            'days_required': 0,
            'unavailable_dates': [],
            'reason': f'Error: {str(e)}'
        }


def get_available_vehicles_for_slot(
    slot_index: int,
    slot_start: str,
    slot_end: str,
    candidate_vins: Set[str],
    availability_df: pd.DataFrame,
    exclude_vins: Set[str] = None
) -> List[str]:
    """
    Get list of vehicles available for a specific chain slot.

    Args:
        slot_index: Slot number (0-based)
        slot_start: Slot start date (YYYY-MM-DD)
        slot_end: Slot end date (YYYY-MM-DD)
        candidate_vins: Set of candidate VINs to check
        availability_df: Availability grid
        exclude_vins: VINs to exclude (already used in earlier slots)

    Returns:
        List of VINs available for this slot
    """

    if exclude_vins is None:
        exclude_vins = set()

    available_vins = []

    exclude_normalized = {_norm_vin(v) for v in exclude_vins}

    for vin in candidate_vins:
        if _norm_vin(vin) in exclude_normalized:
            continue

        # Check availability for this slot
        slot_check = check_slot_availability(vin, slot_start, slot_end, availability_df)

        if slot_check['available']:
            available_vins.append(vin)

    logger.info(f"Slot {slot_index}: {len(available_vins)} vehicles available (from {len(candidate_vins)} candidates, {len(exclude_vins)} excluded)")

    return available_vins


def validate_chain_sequence(
    chain_vins: List[str],
    start_date: str,
    days_per_slot: int,
    availability_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Validate that a chain of VINs is sequentially available.

    Args:
        chain_vins: List of VINs in chain order
        start_date: Chain start date
        days_per_slot: Days per vehicle
        availability_df: Availability grid

    Returns:
        Dictionary with validation results
    """

    try:
        issues = []
        warnings = []

        # Check for duplicate VINs
        if len(chain_vins) != len(set(chain_vins)):
            issues.append("Chain contains duplicate VINs")

        # Check each slot
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')

        for i, vin in enumerate(chain_vins):
            slot_start_dt = start_dt + timedelta(days=i * days_per_slot)
            slot_end_dt = slot_start_dt + timedelta(days=days_per_slot - 1)

            slot_start = slot_start_dt.strftime('%Y-%m-%d')
            slot_end = slot_end_dt.strftime('%Y-%m-%d')

            slot_check = check_slot_availability(vin, slot_start, slot_end, availability_df)

            if not slot_check['available']:
                issues.append(f"Slot {i+1} ({vin}): {slot_check['reason']}")

        is_valid = len(issues) == 0

        return {
            'valid': is_valid,
            'issues': issues,
            'warnings': warnings,
            'message': 'Chain is valid' if is_valid else f'{len(issues)} issue(s) found'
        }

    except Exception as e:
        logger.error(f"Error validating chain: {str(e)}")
        return {
            'valid': False,
            'issues': [f'Validation error: {str(e)}'],
            'warnings': [],
            'message': 'Validation failed'
        }


def build_partner_availability_grid(
    partners_df: pd.DataFrame,
    current_activity_df: pd.DataFrame,
    scheduled_assignments_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    office: str
) -> pd.DataFrame:
    """
    Build availability grid for partners during vehicle chain period.

    Similar to build_chain_availability_grid but for partners instead of vehicles.
    Checks if partners have active loans or scheduled assignments during each day.

    Args:
        partners_df: All media partners (filtered to office)
        current_activity_df: Current active loans (partner's busy periods)
        scheduled_assignments_df: Scheduled assignments (partner's upcoming busy periods)
        start_date: Chain start date (YYYY-MM-DD)
        end_date: Chain end date (YYYY-MM-DD)
        office: Office to filter partners

    Returns:
        DataFrame with columns: person_id, date, available (boolean), reason
        One row per partner per day in the date range
    """

    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        chain_duration_days = (end_dt - start_dt).days + 1

        logger.info(f"Building partner availability grid from {start_date} to {end_date} ({chain_duration_days} days)")

        # Filter partners to office
        if office:
            office_partners = partners_df[partners_df['office'] == office].copy()
        else:
            office_partners = partners_df.copy()

        if office_partners.empty:
            logger.warning(f"No partners found for office: {office}")
            return pd.DataFrame(columns=['person_id', 'date', 'available', 'reason'])

        # Ensure person_id is integer
        office_partners['person_id'] = office_partners['person_id'].astype(int)
        partner_ids = office_partners['person_id'].unique()

        logger.info(f"Checking availability for {len(partner_ids)} partners")

        # Build list of all dates
        date_range = pd.date_range(start=start_dt, end=end_dt, freq='D')

        # Initialize availability grid
        availability_records = []

        for partner_id in partner_ids:
            for date in date_range:
                date_str = date.strftime('%Y-%m-%d')

                # Default: available
                is_available = True
                reason = 'Available'

                # Check current active loans
                if not current_activity_df.empty and 'person_id' in current_activity_df.columns:
                    partner_activity = current_activity_df[
                        current_activity_df['person_id'].astype(int) == partner_id
                    ]

                    for _, activity in partner_activity.iterrows():
                        if 'start_date' in activity and 'end_date' in activity:
                            activity_start = pd.to_datetime(activity['start_date']).date()
                            activity_end = pd.to_datetime(activity['end_date']).date()

                            if activity_start <= date.date() <= activity_end:
                                is_available = False
                                reason = f"Active loan ({activity_start} to {activity_end})"
                                break

                # Check scheduled assignments (if still available)
                if is_available and not scheduled_assignments_df.empty and 'person_id' in scheduled_assignments_df.columns:
                    partner_scheduled = scheduled_assignments_df[
                        scheduled_assignments_df['person_id'].astype(int) == partner_id
                    ]

                    for _, assignment in partner_scheduled.iterrows():
                        if 'start_day' in assignment and 'end_day' in assignment:
                            assign_start = pd.to_datetime(assignment['start_day']).date()
                            assign_end = pd.to_datetime(assignment['end_day']).date()

                            if assign_start <= date.date() <= assign_end:
                                is_available = False
                                status = assignment.get('status', 'scheduled')
                                reason = f"Scheduled assignment ({assign_start} to {assign_end}, status: {status})"
                                break

                availability_records.append({
                    'person_id': partner_id,
                    'date': date_str,
                    'available': is_available,
                    'reason': reason
                })

        availability_df = pd.DataFrame(availability_records)

        # Log summary
        if not availability_df.empty:
            total_slots = len(availability_df)
            available_slots = availability_df['available'].sum()
            logger.info(f"Availability grid: {available_slots}/{total_slots} partner-days available ({available_slots/total_slots*100:.1f}%)")

        return availability_df

    except Exception as e:
        logger.error(f"Error building partner availability grid: {str(e)}")
        return pd.DataFrame(columns=['person_id', 'date', 'available', 'reason'])


def check_partner_slot_availability(
    person_id: int,
    slot_start: str,
    slot_end: str,
    availability_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Check if a specific partner is available for a specific slot.

    Args:
        person_id: Partner ID to check
        slot_start: Slot start date (YYYY-MM-DD)
        slot_end: Slot end date (YYYY-MM-DD)
        availability_df: Pre-built availability grid

    Returns:
        Dict with:
        - available: Boolean - is partner available for entire slot?
        - days_available: Number of available days
        - days_required: Number of days in slot
        - unavailable_dates: List of dates partner is busy
        - reason: Explanation if unavailable
    """
    if availability_df.empty:
        return {
            'available': False,
            'days_available': 0,
            'days_required': 0,
            'unavailable_dates': [],
            'reason': 'No availability data'
        }

    # Filter to this partner and date range
    start_dt = datetime.strptime(slot_start, '%Y-%m-%d')
    end_dt = datetime.strptime(slot_end, '%Y-%m-%d')

    partner_avail = availability_df[
        (availability_df['person_id'] == person_id) &
        (pd.to_datetime(availability_df['date']).dt.date >= start_dt.date()) &
        (pd.to_datetime(availability_df['date']).dt.date <= end_dt.date())
    ]

    if partner_avail.empty:
        return {
            'available': False,
            'days_available': 0,
            'days_required': (end_dt - start_dt).days + 1,
            'unavailable_dates': [],
            'reason': 'Partner not in availability grid'
        }

    days_required = len(partner_avail)
    days_available = partner_avail['available'].sum()
    unavailable_dates = partner_avail[~partner_avail['available']]['date'].tolist()

    is_available = days_available == days_required

    reason = 'Available for entire slot' if is_available else f'Busy on {len(unavailable_dates)} day(s)'

    return {
        'available': is_available,
        'days_available': int(days_available),
        'days_required': days_required,
        'unavailable_dates': unavailable_dates,
        'reason': reason
    }
