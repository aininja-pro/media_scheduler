"""
Candidate generation for media scheduling optimization.

This module generates feasible (VIN × partner) pairs based on availability,
cooldown periods, and partner eligibility constraints.
"""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd


def build_weekly_candidates(
    availability_df: pd.DataFrame,      # cols: vin, date, market, make, model, available (bool)
    cooldown_df: pd.DataFrame,          # cols: person_id, make, model, cooldown_ok (bool)
    publication_df: pd.DataFrame,       # cols: person_id, make, loans_total_24m, loans_observed_24m,
                                       #       publications_observed_24m, publication_rate_observed, coverage, supported
    week_start: str,                   # "YYYY-MM-DD" (Monday)
    eligibility_df: Optional[pd.DataFrame] = None,  # optional: cols: person_id, make [, market]
    min_available_days: int = 7,
    current_activity_df: Optional[pd.DataFrame] = None  # optional: cols: person_id, vehicle_vin, start_date, end_date
) -> pd.DataFrame:
    """
    Returns one row per feasible (vin, person_id) for the target week.

    Args:
        availability_df: Vehicle availability by date
        cooldown_df: Partner cooldown status by make/model
        publication_df: Publication rates and coverage by partner/make
        week_start: Target week start date (Monday, YYYY-MM-DD format)
        eligibility_df: Optional partner eligibility constraints
        min_available_days: Minimum days a VIN must be available

    Returns:
        DataFrame with columns:
        ["vin", "person_id", "market", "make", "model", "week_start",
         "available_days", "cooldown_ok", "publication_rate_observed", "supported", "coverage"]

    Rules:
        - VIN eligible only if available >= min_available_days in week window
        - Partners from eligibility_df (if provided) or publication_df history
        - Cooldown join: (person_id, make, model) first, fallback to (person_id, make)
        - Exclude rows where cooldown_ok == False
        - Keep publication fields even if coverage == 0
    """

    # Parse week_start and compute week window
    week_start_date = pd.to_datetime(week_start).date()
    week_dates = [week_start_date + timedelta(days=i) for i in range(7)]

    # Filter availability to target week
    availability_week = availability_df.copy()
    availability_week['date'] = pd.to_datetime(availability_week['date']).dt.date
    availability_week = availability_week[availability_week['date'].isin(week_dates)]

    if availability_week.empty:
        return _empty_candidates_df(week_start)

    # Step 1: Compute available_days per VIN
    vin_availability = (
        availability_week[availability_week['available'] == True]
        .groupby('vin', as_index=False)
        .agg({
            'date': 'count',  # Count available days
            'market': 'first',
            'make': 'first',
            'model': 'first'
        })
    )
    vin_availability = vin_availability.rename(columns={'date': 'available_days'})

    # Filter VINs with insufficient availability
    eligible_vins = vin_availability[vin_availability['available_days'] >= min_available_days].copy()

    if eligible_vins.empty:
        return _empty_candidates_df(week_start)

    # Step 2: Build partner set for each VIN
    candidates = []

    for _, vin_row in eligible_vins.iterrows():
        vin = vin_row['vin']
        make = vin_row['make']
        market = vin_row['market']
        model = vin_row['model']
        available_days = vin_row['available_days']

        # Get eligible partners for this VIN's make (and market if provided)
        if eligibility_df is not None and not eligibility_df.empty:
            # Use eligibility constraints
            partner_filter = eligibility_df['make'] == make
            if 'market' in eligibility_df.columns:
                partner_filter = partner_filter & (eligibility_df['market'] == market)
            eligible_partners = eligibility_df[partner_filter]['person_id'].unique()
        else:
            # Fallback to historical partners from publication data
            eligible_partners = publication_df[publication_df['make'] == make]['person_id'].unique()

        # Create candidate rows for this VIN × eligible partners
        for person_id in eligible_partners:
            candidates.append({
                'vin': vin,
                'person_id': person_id,
                'market': market,
                'make': make,
                'model': model,
                'week_start': week_start,
                'available_days': available_days
            })

    if not candidates:
        return _empty_candidates_df(week_start)

    candidates_df = pd.DataFrame(candidates)

    # Step 3: Join cooldown data with fallback logic
    candidates_df = _join_cooldown_data(candidates_df, cooldown_df)

    # Step 4: Filter out cooldown violations
    candidates_df = candidates_df[candidates_df['cooldown_ok'] == True].copy()

    if candidates_df.empty:
        return _empty_candidates_df(week_start)

    # Step 5: Filter by current activity (partner availability)
    if current_activity_df is not None:
        candidates_df = _filter_by_current_activity(candidates_df, current_activity_df, week_start)
        # Only keep partners who are available
        candidates_df = candidates_df[candidates_df['partner_available'] == True].copy()
        if candidates_df.empty:
            return _empty_candidates_df(week_start)

    # Step 6: Join publication data
    candidates_df = _join_publication_data(candidates_df, publication_df)

    # Step 7: Ensure correct column order and return
    output_columns = [
        "vin", "person_id", "market", "make", "model", "week_start",
        "available_days", "cooldown_ok", "publication_rate_observed", "supported", "coverage"
    ]

    return candidates_df[output_columns].copy()


def _empty_candidates_df(week_start: str) -> pd.DataFrame:
    """Return empty DataFrame with correct schema."""
    return pd.DataFrame(columns=[
        "vin", "person_id", "market", "make", "model", "week_start",
        "available_days", "cooldown_ok", "publication_rate_observed", "supported", "coverage"
    ])


def _join_cooldown_data(candidates_df: pd.DataFrame, cooldown_df: pd.DataFrame) -> pd.DataFrame:
    """
    Join cooldown data with fallback logic:
    1. Try (person_id, make, model) join
    2. Fallback to (person_id, make) for missing matches
    """
    if cooldown_df.empty:
        candidates_df['cooldown_ok'] = True
        return candidates_df

    # First attempt: exact (person_id, make, model) join
    candidates_with_cooldown = candidates_df.merge(
        cooldown_df,
        on=['person_id', 'make', 'model'],
        how='left'
    )

    # Find rows that didn't match (cooldown_ok is NaN)
    unmatched_mask = candidates_with_cooldown['cooldown_ok'].isna()

    if unmatched_mask.any():
        # Prepare fallback data: (person_id, make) only
        cooldown_make_only = cooldown_df.groupby(['person_id', 'make'], as_index=False).agg({
            'cooldown_ok': 'first'  # Take first value if multiple models exist
        })

        # Apply fallback join for unmatched rows
        unmatched_rows = candidates_with_cooldown[unmatched_mask].copy()
        unmatched_rows = unmatched_rows.drop(columns=['cooldown_ok'])

        fallback_joined = unmatched_rows.merge(
            cooldown_make_only,
            on=['person_id', 'make'],
            how='left'
        )

        # Update the main dataframe with fallback results
        candidates_with_cooldown.loc[unmatched_mask, 'cooldown_ok'] = fallback_joined['cooldown_ok'].values

    # Fill any remaining NaN values with True (no cooldown constraint)
    candidates_with_cooldown['cooldown_ok'] = candidates_with_cooldown['cooldown_ok'].fillna(True).infer_objects(copy=False)

    return candidates_with_cooldown


def _filter_by_current_activity(candidates_df: pd.DataFrame, current_activity_df: pd.DataFrame, week_start: str) -> pd.DataFrame:
    """Filter out partners who have overlapping vehicle activities during the scheduled week."""
    if current_activity_df.empty or 'person_id' not in current_activity_df.columns:
        # If no activity data or person_id not available, assume all are available
        candidates_df['partner_available'] = True
        return candidates_df

    # Parse week dates
    week_start_date = pd.to_datetime(week_start).date()
    week_end_date = week_start_date + timedelta(days=6)

    # Convert activity dates
    activity = current_activity_df.copy()
    activity['start_date'] = pd.to_datetime(activity['start_date']).dt.date
    activity['end_date'] = pd.to_datetime(activity['end_date']).dt.date

    # Find partners with overlapping activities
    # An activity overlaps if it starts before week ends AND ends after week starts
    overlapping = activity[
        (activity['start_date'] <= week_end_date) &
        (activity['end_date'] >= week_start_date)
    ]

    # Get unique partner IDs who are NOT available (have overlapping activities)
    unavailable_partners = set(overlapping['person_id'].dropna().unique())

    # Mark availability in candidates
    candidates_df['partner_available'] = ~candidates_df['person_id'].isin(unavailable_partners)

    return candidates_df


def _join_publication_data(candidates_df: pd.DataFrame, publication_df: pd.DataFrame) -> pd.DataFrame:
    """Join publication rate data on (person_id, make)."""
    if publication_df.empty:
        candidates_df['publication_rate_observed'] = pd.Series([None] * len(candidates_df), dtype=object)
        candidates_df['supported'] = False
        candidates_df['coverage'] = 0.0
        return candidates_df

    # Select relevant publication columns
    pub_cols = ['person_id', 'make', 'publication_rate_observed', 'supported', 'coverage']
    pub_data = publication_df[pub_cols].copy()

    # Join on (person_id, make)
    candidates_with_pub = candidates_df.merge(
        pub_data,
        on=['person_id', 'make'],
        how='left'
    )

    # Fill missing publication data
    candidates_with_pub['publication_rate_observed'] = candidates_with_pub['publication_rate_observed'].where(
        candidates_with_pub['publication_rate_observed'].notna(), None
    )
    candidates_with_pub['supported'] = candidates_with_pub['supported'].fillna(False).infer_objects(copy=False)
    candidates_with_pub['coverage'] = candidates_with_pub['coverage'].fillna(0.0)

    return candidates_with_pub