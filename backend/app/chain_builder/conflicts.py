"""
Conflict Detection Module for Media Scheduler

Detects and flags potential conflicts in vehicle/partner assignments:
- Adjacent activities (vehicle or partner busy before/after)
- Distance warnings (tiered: yellow/orange/red)
- Capacity warnings (start day utilization)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd


def get_distance_warning_level(distance_miles: float) -> str:
    """
    Determine warning level based on distance.

    Args:
        distance_miles: Distance in miles

    Returns:
        'none', 'yellow', 'orange', or 'red'
    """
    if distance_miles >= 100:
        return 'red'
    elif distance_miles >= 75:
        return 'orange'
    elif distance_miles >= 30:
        return 'yellow'
    else:
        return 'none'


def detect_adjacent_activities(
    entity_id: int,
    entity_type: str,  # 'vehicle' or 'partner'
    start_date: str,  # YYYY-MM-DD format
    end_date: str,    # YYYY-MM-DD format
    current_activity_df: pd.DataFrame,
    scheduled_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Detect if entity (vehicle or partner) has activities adjacent to the proposed period.

    Args:
        entity_id: VIN (if vehicle) or person_id (if partner)
        entity_type: 'vehicle' or 'partner'
        start_date: Assignment start date
        end_date: Assignment end date
        current_activity_df: DataFrame of current active loans
        scheduled_df: DataFrame of scheduled assignments

    Returns:
        {
            'has_adjacent': bool,
            'before': {...} or None,
            'after': {...} or None
        }
    """
    result = {
        'has_adjacent': False,
        'before': None,
        'after': None
    }

    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return result

    # Combine current and scheduled activities
    all_activities = []

    # Process current activities
    if current_activity_df is not None and not current_activity_df.empty:
        if entity_type == 'vehicle':
            entity_activities = current_activity_df[
                current_activity_df['vehicle_vin'] == entity_id
            ].copy()
        else:  # partner
            entity_activities = current_activity_df[
                current_activity_df['person_id'] == entity_id
            ].copy()

        for _, activity in entity_activities.iterrows():
            all_activities.append({
                'type': 'active',
                'start': pd.to_datetime(activity.get('start_date')),
                'end': pd.to_datetime(activity.get('end_date')),
                'partner_name': activity.get('partner_name', 'Unknown'),
                'vin': activity.get('vehicle_vin', entity_id if entity_type == 'vehicle' else None),
                'person_id': activity.get('person_id', entity_id if entity_type == 'partner' else None)
            })

    # Process scheduled activities
    if scheduled_df is not None and not scheduled_df.empty:
        if entity_type == 'vehicle':
            entity_activities = scheduled_df[
                scheduled_df['vin'] == entity_id
            ].copy()
        else:  # partner
            entity_activities = scheduled_df[
                scheduled_df['person_id'] == entity_id
            ].copy()

        for _, activity in entity_activities.iterrows():
            all_activities.append({
                'type': 'scheduled',
                'status': activity.get('status', 'planned'),
                'start': pd.to_datetime(activity.get('start_day')),
                'end': pd.to_datetime(activity.get('end_day')),
                'partner_name': activity.get('partner_name', 'Unknown'),
                'vin': activity.get('vin', entity_id if entity_type == 'vehicle' else None),
                'person_id': activity.get('person_id', entity_id if entity_type == 'partner' else None),
                'make': activity.get('make'),
                'model': activity.get('model')
            })

    # Check for adjacent activities
    for activity in all_activities:
        act_start = activity['start']
        act_end = activity['end']

        if pd.isna(act_start) or pd.isna(act_end):
            continue

        # Calculate gaps
        gap_before = (start - act_end).days
        gap_after = (act_start - end).days

        # Check if activity is before (ends before or on assignment start)
        if gap_before >= 0:
            # Store the closest activity before
            if result['before'] is None or gap_before < result['before']['gap_days']:
                result['before'] = {
                    'gap_days': gap_before,
                    'type': activity['type'],
                    'status': activity.get('status'),
                    'start_date': act_start.strftime('%Y-%m-%d'),
                    'end_date': act_end.strftime('%Y-%m-%d'),
                    'partner_name': activity.get('partner_name'),
                    'vin': activity.get('vin'),
                    'person_id': activity.get('person_id'),
                    'make': activity.get('make'),
                    'model': activity.get('model')
                }

        # Check if activity is after (starts after or on assignment end)
        if gap_after >= 0:
            # Store the closest activity after
            if result['after'] is None or gap_after < result['after']['gap_days']:
                result['after'] = {
                    'gap_days': gap_after,
                    'type': activity['type'],
                    'status': activity.get('status'),
                    'start_date': act_start.strftime('%Y-%m-%d'),
                    'end_date': act_end.strftime('%Y-%m-%d'),
                    'partner_name': activity.get('partner_name'),
                    'vin': activity.get('vin'),
                    'person_id': activity.get('person_id'),
                    'make': activity.get('make'),
                    'model': activity.get('model')
                }

    result['has_adjacent'] = bool(result['before'] or result['after'])

    return result


def calculate_distance_to_adjacent(
    assignment: Dict[str, Any],
    adjacent_info: Dict[str, Any],
    distance_matrix: Dict[Tuple[int, int], float],
    entity_type: str  # 'vehicle' or 'partner'
) -> Dict[str, Any]:
    """
    Calculate distance from assignment to adjacent activities.

    Args:
        assignment: Assignment dict with person_id or vin
        adjacent_info: Result from detect_adjacent_activities
        distance_matrix: {(person_id_1, person_id_2): miles}
        entity_type: 'vehicle' or 'partner'

    Returns:
        {
            'distance_to_prev': float or None,
            'distance_to_next': float or None,
            'prev_warning_level': 'none'|'yellow'|'orange'|'red',
            'next_warning_level': 'none'|'yellow'|'orange'|'red',
            'max_distance': float,
            'max_warning_level': 'none'|'yellow'|'orange'|'red'
        }
    """
    result = {
        'distance_to_prev': None,
        'distance_to_next': None,
        'prev_warning_level': 'none',
        'next_warning_level': 'none',
        'max_distance': 0,
        'max_warning_level': 'none'
    }

    if entity_type != 'partner':
        # Distance only matters for vehicle chains (partner locations)
        # For partner chains, we don't calculate inter-vehicle distances
        return result

    current_person_id = assignment.get('person_id')
    if current_person_id is None:
        return result

    # Distance to previous assignment
    if adjacent_info.get('before'):
        prev_person_id = adjacent_info['before'].get('person_id')
        if prev_person_id and prev_person_id != current_person_id:
            distance = distance_matrix.get((prev_person_id, current_person_id)) or \
                      distance_matrix.get((current_person_id, prev_person_id)) or 0
            result['distance_to_prev'] = round(distance, 2)
            result['prev_warning_level'] = get_distance_warning_level(distance)

    # Distance to next assignment
    if adjacent_info.get('after'):
        next_person_id = adjacent_info['after'].get('person_id')
        if next_person_id and next_person_id != current_person_id:
            distance = distance_matrix.get((current_person_id, next_person_id)) or \
                      distance_matrix.get((next_person_id, current_person_id)) or 0
            result['distance_to_next'] = round(distance, 2)
            result['next_warning_level'] = get_distance_warning_level(distance)

    # Calculate max distance
    distances = [d for d in [result['distance_to_prev'], result['distance_to_next']] if d is not None]
    if distances:
        result['max_distance'] = max(distances)
        result['max_warning_level'] = get_distance_warning_level(result['max_distance'])

    return result


def check_capacity_pressure(
    start_date: str,
    office: str,
    capacity_map: Dict[Any, int],
    scheduled_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Check if start date is near/at capacity limit.

    Args:
        start_date: Assignment start date (YYYY-MM-DD)
        office: Office name
        capacity_map: {date: capacity} from dynamic_capacity
        scheduled_df: DataFrame of scheduled assignments

    Returns:
        {
            'has_warning': bool,
            'utilization': float (0-1),
            'starts_on_day': int,
            'capacity': int
        }
    """
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return {
            'has_warning': False,
            'utilization': 0.0,
            'starts_on_day': 0,
            'capacity': 0
        }

    # Get capacity for this day (default weekday: 15, weekend: 0)
    capacity = capacity_map.get(start, 15 if start.weekday() < 5 else 0)

    if capacity == 0:
        # Blackout day
        return {
            'has_warning': True,
            'utilization': 1.0,
            'starts_on_day': 0,
            'capacity': 0,
            'is_blackout': True
        }

    # Count capacity events on this day (dropoffs, pickups, and swaps)
    capacity_used = 0
    if scheduled_df is not None and not scheduled_df.empty:
        office_scheduled = scheduled_df[scheduled_df['office'] == office].copy()
        office_scheduled['start_day'] = pd.to_datetime(office_scheduled['start_day']).dt.date
        office_scheduled['end_day'] = pd.to_datetime(office_scheduled['end_day']).dt.date

        # Build events by partner for swap detection
        from collections import defaultdict
        events_by_partner = defaultdict(lambda: {'dropoffs': [], 'pickups': []})

        for _, assignment in office_scheduled.iterrows():
            person_id = assignment.get('person_id')
            start_day = assignment.get('start_day')
            end_day = assignment.get('end_day')

            # Dropoff (loan starts)
            if start_day == start:
                events_by_partner[person_id]['dropoffs'].append(assignment.get('vin'))

            # Pickup (loan ends)
            if end_day == start:
                events_by_partner[person_id]['pickups'].append(assignment.get('vin'))

        # Count capacity with swap detection
        for partner_id, events in events_by_partner.items():
            num_dropoffs = len(events['dropoffs'])
            num_pickups = len(events['pickups'])

            swaps = min(num_dropoffs, num_pickups)
            standalone_dropoffs = num_dropoffs - swaps
            standalone_pickups = num_pickups - swaps

            capacity_used += swaps + standalone_dropoffs + standalone_pickups

    utilization = capacity_used / capacity if capacity > 0 else 0

    return {
        'has_warning': utilization > 0.8,  # 80% threshold
        'utilization': round(utilization, 2),
        'starts_on_day': capacity_used,
        'capacity': capacity,
        'is_blackout': False
    }


def detect_conflicts(
    assignment: Dict[str, Any],
    entity_type: str,  # 'vehicle' or 'partner'
    current_activity_df: pd.DataFrame,
    scheduled_df: pd.DataFrame,
    capacity_map: Dict[Any, int],
    distance_matrix: Dict[Tuple[int, int], float]
) -> Dict[str, Any]:
    """
    Main conflict detection function.

    Args:
        assignment: Assignment dict with keys:
            - person_id (if partner chain) or vin (if vehicle chain)
            - start_day, end_day
            - office
        entity_type: 'vehicle' or 'partner'
        current_activity_df: Active loans
        scheduled_df: Scheduled assignments
        capacity_map: Date -> capacity from dynamic_capacity
        distance_matrix: (person_id, person_id) -> miles

    Returns:
        Complete conflict object with all flags and details
    """
    # Determine entity ID based on type
    if entity_type == 'vehicle':
        entity_id = assignment.get('vin')
    else:  # partner
        entity_id = assignment.get('person_id')

    # Detect adjacent activities
    adjacent_info = detect_adjacent_activities(
        entity_id=entity_id,
        entity_type=entity_type,
        start_date=assignment.get('start_day'),
        end_date=assignment.get('end_day'),
        current_activity_df=current_activity_df,
        scheduled_df=scheduled_df
    )

    # Calculate distances to adjacent activities
    distance_info = calculate_distance_to_adjacent(
        assignment=assignment,
        adjacent_info=adjacent_info,
        distance_matrix=distance_matrix,
        entity_type=entity_type
    )

    # Check capacity pressure
    capacity_info = check_capacity_pressure(
        start_date=assignment.get('start_day'),
        office=assignment.get('office', 'Unknown'),
        capacity_map=capacity_map,
        scheduled_df=scheduled_df
    )

    # Combine all conflict information
    return {
        # Adjacent activity flags
        'adjacent_activity': adjacent_info['has_adjacent'],
        'adjacent_before': adjacent_info['before'],
        'adjacent_after': adjacent_info['after'],

        # Distance warnings
        'distance_to_prev': distance_info['distance_to_prev'],
        'distance_to_next': distance_info['distance_to_next'],
        'prev_warning_level': distance_info['prev_warning_level'],
        'next_warning_level': distance_info['next_warning_level'],
        'max_distance': distance_info['max_distance'],
        'distance_warning_level': distance_info['max_warning_level'],

        # Capacity warnings
        'capacity_warning': capacity_info['has_warning'],
        'capacity_utilization': capacity_info['utilization'],
        'capacity_starts_on_day': capacity_info['starts_on_day'],
        'capacity_limit': capacity_info['capacity'],
        'is_blackout_day': capacity_info.get('is_blackout', False),

        # Overall conflict flag
        'has_any_conflict': (
            adjacent_info['has_adjacent'] or
            distance_info['max_warning_level'] != 'none' or
            capacity_info['has_warning']
        )
    }
