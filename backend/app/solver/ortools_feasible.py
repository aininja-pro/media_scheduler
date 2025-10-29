"""
Phase 7.1: Build feasible triples (vehicle, partner, start_day) for OR-Tools solver.

This module generates the feasible set of assignments that satisfy:
- Vehicle available 7/7 days from start day
- Office match required
- Eligibility verified
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def build_feasible_triples(
    vehicles_df: pd.DataFrame,
    partners_df: pd.DataFrame,
    availability_df: pd.DataFrame,
    week_start: str,
    office: str,
    approved_makes_df: Optional[pd.DataFrame] = None,
    min_available_days: int = 7
) -> List[Tuple[str, str, int, Dict[str, Any]]]:
    """
    Build feasible (vehicle, partner, start_day) triples for OR-Tools.

    Args:
        vehicles_df: Vehicle data with columns [vin, make, model, office]
        partners_df: Partner data with columns [person_id, name, office]
        availability_df: Availability grid with columns [vin, date, available]
        week_start: Week start date (Monday) in YYYY-MM-DD format
        office: Office to schedule for
        approved_makes_df: Optional approved makes data [person_id, make, rank]
        min_available_days: Minimum days vehicle must be available (default: 7)

    Returns:
        List of tuples: (vin, person_id, start_day_offset, metadata)
        where start_day_offset is 0 for Monday, 1 for Tuesday, etc.
        metadata contains make, model, office, rank for scoring
    """

    triples = []
    week_start_date = pd.to_datetime(week_start).date()

    # Filter to office vehicles only
    office_vehicles = vehicles_df[vehicles_df['office'] == office].copy()
    if office_vehicles.empty:
        logger.warning(f"No vehicles found for office {office}")
        return triples

    # Filter to office partners only
    office_partners = partners_df[partners_df['office'] == office].copy()
    if office_partners.empty:
        logger.warning(f"No partners found for office {office}")
        return triples

    logger.info(f"Building triples for {len(office_vehicles)} vehicles and {len(office_partners)} partners")

    # Convert availability dates for efficiency
    availability_df = availability_df.copy()
    availability_df['date'] = pd.to_datetime(availability_df['date']).dt.date

    # For each vehicle
    for _, vehicle in office_vehicles.iterrows():
        vin = vehicle['vin']
        make = vehicle['make']
        model = vehicle.get('model', '')

        # Get vehicle availability for the week
        week_end_date = week_start_date + timedelta(days=6)
        vehicle_avail = availability_df[
            (availability_df['vin'] == vin) &
            (availability_df['date'] >= week_start_date) &
            (availability_df['date'] <= week_end_date) &
            (availability_df['available'] == True)
        ]

        # Count consecutive available days starting from each day
        available_days_from = {}
        for start_offset in range(5):  # Monday through Friday starts only
            start_date = week_start_date + timedelta(days=start_offset)
            consecutive_days = 0

            for day_offset in range(7):  # Check 7 days from start
                check_date = start_date + timedelta(days=day_offset)
                if check_date > week_end_date:
                    break

                if any(vehicle_avail['date'] == check_date):
                    consecutive_days += 1
                else:
                    break  # Not available, stop counting

            available_days_from[start_offset] = consecutive_days

        # Skip vehicle if not available enough days from any start day
        if all(days < min_available_days for days in available_days_from.values()):
            continue

        # Find eligible partners for this vehicle
        eligible_partners = []

        if approved_makes_df is not None and not approved_makes_df.empty:
            # Use approved makes to determine eligibility
            make_partners = approved_makes_df[approved_makes_df['make'] == make]
            for _, approval in make_partners.iterrows():
                partner_id = approval['person_id']
                if partner_id in office_partners['person_id'].values:
                    partner = office_partners[office_partners['person_id'] == partner_id].iloc[0]
                    eligible_partners.append({
                        'person_id': partner_id,
                        'name': partner.get('name', ''),
                        'rank': approval.get('rank', 'UNRANKED')
                    })
        else:
            # Fallback: all office partners are eligible
            for _, partner in office_partners.iterrows():
                eligible_partners.append({
                    'person_id': partner['person_id'],
                    'name': partner.get('name', ''),
                    'rank': 'UNRANKED'
                })

        # Create triples for each eligible partner and feasible start day
        for partner in eligible_partners:
            for start_offset, days_available in available_days_from.items():
                if days_available >= min_available_days:
                    # This is a feasible triple
                    metadata = {
                        'vin': vin,
                        'person_id': partner['person_id'],
                        'person_name': partner['name'],
                        'make': make,
                        'model': model,
                        'office': office,
                        'rank': partner['rank'],
                        'start_day': start_offset,
                        'available_days': days_available
                    }

                    triples.append((
                        vin,
                        partner['person_id'],
                        start_offset,
                        metadata
                    ))

    logger.info(f"Generated {len(triples)} feasible triples")

    # Validation: count unique combinations
    unique_vins = len(set(t[0] for t in triples))
    unique_partners = len(set(t[1] for t in triples))
    unique_starts = len(set(t[2] for t in triples))

    logger.info(f"Unique vehicles: {unique_vins}, partners: {unique_partners}, start days: {unique_starts}")

    return triples


def filter_triples_by_cooldown(
    triples: List[Tuple[str, str, int, Dict[str, Any]]],
    cooldown_df: pd.DataFrame
) -> List[Tuple[str, str, int, Dict[str, Any]]]:
    """
    Filter triples to remove cooldown violations.

    Args:
        triples: List of feasible triples
        cooldown_df: Cooldown data [person_id, make, model, cooldown_ok]

    Returns:
        Filtered list of triples without cooldown violations
    """

    if cooldown_df.empty:
        return triples

    filtered = []

    for vin, person_id, start_day, metadata in triples:
        make = metadata['make']
        model = metadata['model']

        # Check cooldown - try model-level first
        cooldown_check = cooldown_df[
            (cooldown_df['person_id'] == person_id) &
            (cooldown_df['make'] == make) &
            (cooldown_df['model'] == model)
        ]

        if cooldown_check.empty:
            # Fallback to make-level
            cooldown_check = cooldown_df[
                (cooldown_df['person_id'] == person_id) &
                (cooldown_df['make'] == make) &
                (cooldown_df['model'].isna())
            ]

        # If we have cooldown data, check if OK
        if not cooldown_check.empty:
            cooldown_ok = cooldown_check['cooldown_ok'].iloc[0]
            if not cooldown_ok:
                continue  # Skip this triple due to cooldown

        # No cooldown violation, keep the triple
        filtered.append((vin, person_id, start_day, metadata))

    logger.info(f"Filtered {len(triples)} triples to {len(filtered)} after cooldown check")
    return filtered


def filter_triples_by_current_activity(
    triples: List[Tuple[str, str, int, Dict[str, Any]]],
    current_activity_df: pd.DataFrame,
    week_start: str
) -> List[Tuple[str, str, int, Dict[str, Any]]]:
    """
    Filter triples to remove partners with overlapping activities.

    Args:
        triples: List of feasible triples
        current_activity_df: Current activity [person_id, start_date, end_date]
        week_start: Week start date

    Returns:
        Filtered list of triples with only available partners
    """

    if current_activity_df.empty or 'person_id' not in current_activity_df.columns:
        return triples

    week_start_date = pd.to_datetime(week_start).date()
    week_end_date = week_start_date + timedelta(days=6)

    # Find partners with overlapping activities
    activity = current_activity_df.copy()
    activity['start_date'] = pd.to_datetime(activity['start_date']).dt.date
    activity['end_date'] = pd.to_datetime(activity['end_date']).dt.date

    overlapping = activity[
        (activity['start_date'] <= week_end_date) &
        (activity['end_date'] >= week_start_date)
    ]

    unavailable_partners = set(overlapping['person_id'].dropna().unique())

    # Filter triples
    filtered = []
    for vin, person_id, start_day, metadata in triples:
        if person_id not in unavailable_partners:
            filtered.append((vin, person_id, start_day, metadata))

    logger.info(f"Filtered {len(triples)} triples to {len(filtered)} after activity check")
    return filtered


def validate_triple_counts(
    triples: List[Tuple[str, str, int, Dict[str, Any]]],
    expected_greedy_count: int
) -> bool:
    """
    Validate that triple counts match expected values from greedy algorithm.

    Args:
        triples: Generated triples
        expected_greedy_count: Expected count from greedy algorithm

    Returns:
        True if counts match reasonably (within 10%)
    """

    actual_count = len(triples)
    if expected_greedy_count == 0:
        return actual_count == 0

    # Allow 10% tolerance for differences in filtering logic
    tolerance = 0.1
    min_expected = int(expected_greedy_count * (1 - tolerance))
    max_expected = int(expected_greedy_count * (1 + tolerance))

    is_valid = min_expected <= actual_count <= max_expected

    if not is_valid:
        logger.warning(
            f"Triple count mismatch: got {actual_count}, "
            f"expected ~{expected_greedy_count} (±{int(expected_greedy_count * tolerance)})"
        )

    return is_valid