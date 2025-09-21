"""
Phase 7.1: Build feasible start-day triples (VIN, partner, start_day) - SPEC COMPLIANT VERSION

This module generates the canonical set of feasible triples that will be the only
input the solver considers. No optimization, just clean deterministic data with flags.
"""

import pandas as pd
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def build_feasible_start_day_triples(
    vehicles_df: pd.DataFrame,
    partners_df: pd.DataFrame,
    availability_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    week_start: str,
    office: str,
    ops_capacity_df: Optional[pd.DataFrame] = None,
    model_taxonomy_df: Optional[pd.DataFrame] = None,
    start_days: List[str] = None,
    min_available_days: int = 7,
    default_slots_per_day: int = 15,
    brand_filter: Optional[str] = None,
    fleet_filter: Optional[str] = None,
    seed: int = 42
) -> pd.DataFrame:
    """
    Build feasible (VIN, partner, start_day) triples per SPEC 7.1.

    Args:
        vehicles_df: Vehicle data [vin, make, model, office, brand*, fleet*]
        partners_df: Partner data [person_id, office, allowed_start_dows*]
        availability_df: Daily availability [vin, date, available]
        approved_makes_df: Strict eligibility [person_id, make, rank]
        week_start: Monday date in YYYY-MM-DD format
        office: Target office (normalized)
        ops_capacity_df: Optional [office, date, slots]
        model_taxonomy_df: Optional [make, model, short_model_class, powertrain]
        start_days: List of DOWs, default ["Mon","Tue","Wed","Thu","Fri"]
        min_available_days: Required consecutive days (default: 7)
        default_slots_per_day: Default slots when ops_capacity missing
        brand_filter: Optional brand filter
        fleet_filter: Optional fleet filter
        seed: Random seed for deterministic tie-breaking

    Returns:
        DataFrame with columns per spec:
        - vin, person_id, start_day (ISO date)
        - office, make, model, rank
        - eligibility_ok, availability_ok, start_day_ok, geo_office_match
        - short_model_class, powertrain
        - tie_key (for deterministic ordering)
    """

    if start_days is None:
        start_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    # Parse week start
    week_start_date = pd.to_datetime(week_start).date()
    if week_start_date.weekday() != 0:  # Must be Monday
        raise ValueError(f"week_start must be Monday, got {week_start_date.strftime('%A')}")

    # Map DOW names to offsets
    dow_to_offset = {
        "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4,
        "Sat": 5, "Sun": 6
    }
    start_offsets = [dow_to_offset[d] for d in start_days if d in dow_to_offset]

    logger.info(f"Building triples for {office}, week {week_start}, start days: {start_days}")

    # Step 1: Filter vehicles to office (and optional brand/fleet)
    office_vehicles = vehicles_df[vehicles_df['office'] == office].copy()

    if brand_filter and 'brand' in office_vehicles.columns:
        office_vehicles = office_vehicles[office_vehicles['brand'] == brand_filter]

    if fleet_filter and 'fleet' in office_vehicles.columns:
        office_vehicles = office_vehicles[office_vehicles['fleet'] == fleet_filter]

    if office_vehicles.empty:
        logger.warning(f"No vehicles found for office {office}")
        return _empty_triples_df()

    # Step 2: Filter partners to office
    office_partners = partners_df[partners_df['office'] == office].copy()

    if office_partners.empty:
        logger.warning(f"No partners found for office {office}")
        return _empty_triples_df()

    # Step 3: Prepare availability data
    availability_df = availability_df.copy()
    availability_df['date'] = pd.to_datetime(availability_df['date']).dt.date

    # Step 4: Prepare ops capacity lookup
    capacity_lookup = {}
    if ops_capacity_df is not None and not ops_capacity_df.empty:
        ops_capacity_df = ops_capacity_df.copy()
        ops_capacity_df['date'] = pd.to_datetime(ops_capacity_df['date']).dt.date

        for _, row in ops_capacity_df.iterrows():
            if row['office'] == office:
                capacity_lookup[row['date']] = row.get('slots', default_slots_per_day)

    # Step 5: Prepare model taxonomy lookup
    taxonomy_lookup = {}
    if model_taxonomy_df is not None and not model_taxonomy_df.empty:
        for _, row in model_taxonomy_df.iterrows():
            key = (row['make'], row['model'])
            taxonomy_lookup[key] = {
                'short_model_class': row.get('short_model_class'),
                'powertrain': row.get('powertrain')
            }

    # Step 6: Build triples
    triples = []

    logger.debug(f"Processing {len(start_offsets)} start days: {start_offsets}")
    logger.debug(f"Capacity lookup: {capacity_lookup}")

    for start_offset in start_offsets:
        start_date = week_start_date + timedelta(days=start_offset)
        start_dow = start_days[start_offsets.index(start_offset)]

        # Check capacity for this start day
        slots_available = capacity_lookup.get(start_date, default_slots_per_day)
        start_day_has_capacity = slots_available > 0

        logger.debug(f"Checking {start_dow} {start_date}: {slots_available} slots, has_capacity={start_day_has_capacity}")

        if not start_day_has_capacity:
            logger.debug(f"Skipping {start_date} - no slots available")
            continue

        # For each vehicle, check 7-day availability from this start
        for _, vehicle in office_vehicles.iterrows():
            vin = vehicle['vin']
            make = vehicle['make']
            model = vehicle.get('model', '')

            # Check availability for 7 consecutive days from start
            window_dates = [start_date + timedelta(days=i) for i in range(min_available_days)]

            vehicle_avail = availability_df[
                (availability_df['vin'] == vin) &
                (availability_df['date'].isin(window_dates))
            ]

            # Must be available all 7 days
            days_available = vehicle_avail[vehicle_avail['available'] == True]['date'].nunique()
            availability_ok = days_available >= min_available_days

            logger.debug(f"  Vehicle {vin} on {start_date}: {days_available}/{min_available_days} days available, ok={availability_ok}")

            if not availability_ok:
                continue  # Skip this vehicle for this start day

            # Find eligible partners (STRICT: must have approved_makes entry)
            eligible_partners = approved_makes_df[
                approved_makes_df['make'] == make
            ]

            if eligible_partners.empty:
                continue  # No partners approved for this make

            # Join with office partners to get additional info
            eligible_office_partners = eligible_partners.merge(
                office_partners,
                on='person_id',
                how='inner'
            )

            # Get taxonomy info
            taxonomy = taxonomy_lookup.get((make, model), {})
            short_model_class = taxonomy.get('short_model_class')
            powertrain = taxonomy.get('powertrain')

            # Create triple for each eligible partner
            for _, partner in eligible_office_partners.iterrows():
                person_id = partner['person_id']
                rank = partner.get('rank', 'UNRANKED')

                # Check partner's allowed start DOWs
                allowed_dows = partner.get('allowed_start_dows')
                if allowed_dows and pd.notna(allowed_dows):
                    # Parse allowed DOWs (might be comma-separated string or list)
                    if isinstance(allowed_dows, str):
                        allowed_dows = [d.strip() for d in allowed_dows.split(',')]
                    elif not isinstance(allowed_dows, list):
                        allowed_dows = []

                    if allowed_dows and start_dow not in allowed_dows:
                        continue  # Partner doesn't allow this start day

                # Check geo match
                partner_office = partner.get('office_y') or partner.get('office')  # Handle merge column naming
                geo_office_match = (vehicle['office'] == partner_office)

                # Generate deterministic tie-breaker key
                tie_key = _generate_tie_key(vin, person_id, start_date, seed)

                # Create the triple
                triple = {
                    'vin': vin,
                    'person_id': person_id,
                    'start_day': start_date.isoformat(),
                    'office': office,
                    'make': make,
                    'model': model,
                    'rank': rank,
                    'eligibility_ok': True,  # Always true if we got here
                    'availability_ok': True,  # Always true if we got here
                    'start_day_ok': start_day_has_capacity,
                    'geo_office_match': geo_office_match,
                    'short_model_class': short_model_class,
                    'powertrain': powertrain,
                    'tie_key': tie_key
                }

                triples.append(triple)

    if not triples:
        logger.warning(f"No feasible triples generated for {office}, week {week_start}")
        return _empty_triples_df()

    # Convert to DataFrame
    result_df = pd.DataFrame(triples)

    # Sort deterministically by (start_day, vin, person_id) with tie_key for stability
    result_df = result_df.sort_values(
        by=['start_day', 'vin', 'person_id', 'tie_key'],
        ignore_index=True
    )

    # Drop tie_key from output (it was just for sorting)
    result_df = result_df.drop(columns=['tie_key'])

    logger.info(f"Generated {len(result_df)} feasible triples")

    # Log summary statistics
    unique_vins = result_df['vin'].nunique()
    unique_partners = result_df['person_id'].nunique()
    unique_starts = result_df['start_day'].nunique()

    logger.info(f"Unique vehicles: {unique_vins}, partners: {unique_partners}, start days: {unique_starts}")

    return result_df


def _empty_triples_df() -> pd.DataFrame:
    """Return empty DataFrame with correct schema."""
    return pd.DataFrame(columns=[
        'vin', 'person_id', 'start_day', 'office', 'make', 'model', 'rank',
        'eligibility_ok', 'availability_ok', 'start_day_ok', 'geo_office_match',
        'short_model_class', 'powertrain'
    ])


def _generate_tie_key(vin: str, person_id: str, start_date, seed: int) -> str:
    """Generate deterministic tie-breaker key for sorting stability."""
    content = f"{vin}|{person_id}|{start_date}|{seed}"
    return hashlib.md5(content.encode()).hexdigest()[:8]


def validate_triples_output(triples_df: pd.DataFrame) -> bool:
    """
    Validate that triples DataFrame meets spec requirements.

    Returns:
        True if valid, raises ValueError if not
    """

    required_columns = [
        'vin', 'person_id', 'start_day', 'office', 'make', 'model', 'rank',
        'eligibility_ok', 'availability_ok', 'start_day_ok', 'geo_office_match',
        'short_model_class', 'powertrain'
    ]

    # Check all required columns exist
    missing_cols = set(required_columns) - set(triples_df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Check that all eligibility_ok and availability_ok are True
    if not triples_df.empty:
        if not triples_df['eligibility_ok'].all():
            raise ValueError("All eligibility_ok values must be True")

        if not triples_df['availability_ok'].all():
            raise ValueError("All availability_ok values must be True")

    # Check start_day format
    try:
        pd.to_datetime(triples_df['start_day'])
    except Exception as e:
        raise ValueError(f"Invalid start_day format: {e}")

    return True