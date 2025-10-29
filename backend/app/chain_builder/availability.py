"""
Sequential availability checking for Chain Builder

Checks vehicle availability across multi-week chain periods
"""

import pandas as pd
from typing import Dict, List, Set, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def build_chain_availability_grid(
    vehicles_df: pd.DataFrame,
    activity_df: pd.DataFrame,
    start_date: str,
    num_slots: int,
    days_per_slot: int = 7,
    office: str = None,
    end_date: str = None  # NEW: explicit end date if provided
) -> pd.DataFrame:
    """
    Build availability grid covering entire chain period.

    Args:
        vehicles_df: All vehicles (will be filtered to office)
        activity_df: Current activity data
        start_date: Chain start date (YYYY-MM-DD)
        num_slots: Number of vehicles in chain
        days_per_slot: Days per vehicle loan (default 7)
        office: Office to filter vehicles (optional)
        end_date: Explicit end date (YYYY-MM-DD) - overrides calculation

    Returns:
        DataFrame with columns: vin, date, available (boolean)
        Covers full chain duration
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

        # Build availability grid
        availability_records = []

        for _, vehicle in vehicles_df.iterrows():
            vin = vehicle['vin']

            # Get vehicle lifecycle dates
            in_service_date = vehicle.get('in_service_date')
            turn_in_date = vehicle.get('expected_turn_in_date')

            # Convert to datetime
            if isinstance(in_service_date, str):
                in_service_date = datetime.strptime(in_service_date, '%Y-%m-%d').date()
            if isinstance(turn_in_date, str):
                turn_in_date = datetime.strptime(turn_in_date, '%Y-%m-%d').date()

            # Check each day in chain period
            current_date = start_dt.date()
            for day_offset in range(chain_duration_days):
                check_date = current_date + timedelta(days=day_offset)

                # Check lifecycle availability
                lifecycle_available = True
                if in_service_date and check_date < in_service_date:
                    lifecycle_available = False
                if turn_in_date and check_date > turn_in_date:
                    lifecycle_available = False

                # Check current activity (is it loaned out?)
                activity_conflict = False
                if not activity_df.empty:
                    vehicle_activity = activity_df[
                        (activity_df['vin'] == vin) |
                        (activity_df.get('vehicle_vin') == vin)
                    ]

                    for _, activity in vehicle_activity.iterrows():
                        activity_start = activity.get('start_date')
                        activity_end = activity.get('end_date')

                        # Convert to date objects
                        if isinstance(activity_start, str):
                            activity_start = datetime.strptime(activity_start, '%Y-%m-%d').date()
                        if isinstance(activity_end, str):
                            activity_end = datetime.strptime(activity_end, '%Y-%m-%d').date()

                        # Check if this date falls within activity period
                        if activity_start and activity_end:
                            if activity_start <= check_date <= activity_end:
                                activity_conflict = True
                                break

                available = lifecycle_available and not activity_conflict

                availability_records.append({
                    'vin': vin,
                    'date': check_date,
                    'available': available,
                    'reason': 'available' if available else (
                        'lifecycle' if not lifecycle_available else 'activity_conflict'
                    )
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

        # Filter availability to this VIN and date range
        vehicle_availability = availability_df[
            (availability_df['vin'] == vin) &
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

    for vin in candidate_vins:
        # Skip if already used in earlier slot
        if vin in exclude_vins:
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
