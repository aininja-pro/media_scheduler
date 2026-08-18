"""
Exclusion logic for Chain Builder

Filters out vehicles that:
- Partner has already reviewed (from loan_history)
- Partner already has in FMS now or later (from current_activity)
- Partner already has planned in this scheduler (from scheduled_assignments)
- Would violate model-specific cooldown rules
"""

import pandas as pd
from typing import Set, Dict, Any, Optional, Iterable
from datetime import datetime
import logging

from .smart_scheduling import _is_real_blocker

logger = logging.getLogger(__name__)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame()


def _partner_rows(df: pd.DataFrame, person_id: int) -> pd.DataFrame:
    """Rows that belong to this partner. person_id may be stored as text or a number."""
    if df is None or df.empty or 'person_id' not in df.columns:
        return _empty_frame()

    rows = df.copy()
    rows = rows.dropna(subset=['person_id'])
    rows['_person_id'] = pd.to_numeric(rows['person_id'], errors='coerce')
    rows = rows.dropna(subset=['_person_id'])
    return rows[rows['_person_id'].astype(int) == int(person_id)]


def _vins_from_column(df: pd.DataFrame, columns: Iterable[str]) -> Set[str]:
    """Collect VIN values from the first column that exists (vin vs vehicle_vin)."""
    if df is None or df.empty:
        return set()

    for column in columns:
        if column in df.columns:
            return set(df[column].dropna().astype(str).unique())
    return set()


def _scheduled_vins_for_partner(df: pd.DataFrame, person_id: int) -> Set[str]:
    """VINs this partner already has on a real (not cancelled) assignment."""
    partner_rows = _partner_rows(df, person_id)
    if partner_rows.empty:
        return set()

    if 'status' in partner_rows.columns:
        partner_rows = partner_rows[partner_rows['status'].apply(_is_real_blocker)]

    return _vins_from_column(partner_rows, ('vin',))


def _activity_vins_for_partner(df: pd.DataFrame, person_id: int) -> Set[str]:
    """VINs this partner has in FMS activity, including loans that start in the future."""
    partner_rows = _partner_rows(df, person_id)
    return _vins_from_column(partner_rows, ('vin', 'vehicle_vin'))


def _history_vins_for_partner(df: pd.DataFrame, person_id: int) -> Set[str]:
    partner_rows = _partner_rows(df, person_id)
    return _vins_from_column(partner_rows, ('vin',))


def _vehicle_make_model(office_vehicles: pd.DataFrame, vin: str) -> tuple:
    vehicle_info = office_vehicles[office_vehicles['vin'].astype(str) == str(vin)]
    if vehicle_info.empty:
        return 'Unknown', 'Unknown'
    make = vehicle_info.iloc[0]['make'] if 'make' in vehicle_info.columns else 'Unknown'
    model = vehicle_info.iloc[0]['model'] if 'model' in vehicle_info.columns else 'Unknown'
    return make, model


def get_vehicles_not_reviewed(
    person_id: int,
    office: str,
    loan_history_df: pd.DataFrame,
    vehicles_df: pd.DataFrame,
    months_back: int = 12,  # unused; kept so existing callers do not break
    current_activity_df: Optional[pd.DataFrame] = None,
    scheduled_assignments_df: Optional[pd.DataFrame] = None,
    keep_vins: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Get vehicles from office that this partner should not be offered.

    A VIN is hidden if the partner already had it, currently has it, or is
    already scheduled to get it later. Dates do not matter: a loan later this
    month still hides the car from a chain being built for an earlier week.

    keep_vins: VINs to leave in the list even if they would be excluded.
    Used when a scheduler reopens a slot that already has a car selected.

    months_back is unused (we exclude every matching VIN, not a time window).
    """

    try:
        # Filter vehicles to target office
        office_vehicles = vehicles_df[vehicles_df['office'] == office].copy()
        all_office_vins = set(office_vehicles['vin'].dropna().astype(str).unique())

        if current_activity_df is None:
            current_activity_df = _empty_frame()
        if scheduled_assignments_df is None:
            scheduled_assignments_df = _empty_frame()
        if keep_vins is None:
            keep_vins = set()
        else:
            keep_vins = {str(v) for v in keep_vins}

        # Past reviews, current/future FMS loans, and our own planned assignments
        reviewed_vins = _history_vins_for_partner(loan_history_df, person_id)
        activity_vins = _activity_vins_for_partner(current_activity_df, person_id)
        scheduled_vins = _scheduled_vins_for_partner(scheduled_assignments_df, person_id)

        already_theirs = reviewed_vins | activity_vins | scheduled_vins
        excluded_vins = (already_theirs & all_office_vins) - keep_vins
        available_vins = all_office_vins - excluded_vins

        exclusion_details = []
        partner_history = _partner_rows(loan_history_df, person_id)
        if not partner_history.empty and 'end_date' in partner_history.columns:
            partner_history = partner_history.copy()
            partner_history['end_date_dt'] = pd.to_datetime(partner_history['end_date'], errors='coerce')

        for vin in excluded_vins:
            make, model = _vehicle_make_model(office_vehicles, vin)

            if vin in reviewed_vins:
                last_reviewed = 'Unknown'
                if not partner_history.empty and 'end_date_dt' in partner_history.columns:
                    vin_history = partner_history[partner_history['vin'].astype(str) == str(vin)]
                    if not vin_history.empty:
                        latest = vin_history.sort_values('end_date_dt', ascending=False).iloc[0]
                        if pd.notna(latest['end_date_dt']):
                            last_reviewed = latest['end_date_dt'].strftime('%Y-%m-%d')
                exclusion_details.append({
                    'vin': vin,
                    'make': make,
                    'model': model,
                    'last_reviewed_date': last_reviewed,
                    'reason': 'Already reviewed by partner'
                })
            elif vin in activity_vins:
                exclusion_details.append({
                    'vin': vin,
                    'make': make,
                    'model': model,
                    'last_reviewed_date': None,
                    'reason': 'Already on an FMS loan (including future)'
                })
            else:
                exclusion_details.append({
                    'vin': vin,
                    'make': make,
                    'model': model,
                    'last_reviewed_date': None,
                    'reason': 'Already scheduled for this partner'
                })

        logger.info(
            f"Partner {person_id} exclusion: {len(excluded_vins)} VINs excluded, "
            f"{len(available_vins)} available "
            f"(history={len(reviewed_vins)}, activity={len(activity_vins)}, "
            f"scheduled={len(scheduled_vins)})"
        )

        return {
            'available_vins': available_vins,
            'excluded_vins': excluded_vins,
            'office_vehicle_count': len(all_office_vins),
            'available_vehicle_count': len(available_vins),
            'exclusion_details': exclusion_details
        }

    except Exception as e:
        logger.error(f"Error in get_vehicles_not_reviewed: {str(e)}")
        # On error, return all vehicles as available (fail open)
        return {
            'available_vins': set(vehicles_df[vehicles_df['office'] == office]['vin'].unique()),
            'excluded_vins': set(),
            'office_vehicle_count': len(vehicles_df[vehicles_df['office'] == office]),
            'available_vehicle_count': len(vehicles_df[vehicles_df['office'] == office]),
            'exclusion_details': [],
            'error': str(e)
        }


def get_model_cooldown_status(
    person_id: int,
    loan_history_df: pd.DataFrame,
    vehicles_df: pd.DataFrame,
    cooldown_days: int = 30
) -> Dict[str, Dict[str, Any]]:
    """
    Get cooldown status for each (make, model) combination.

    Args:
        person_id: Media partner ID
        loan_history_df: Historical loan data
        vehicles_df: All vehicles (for make/model lookup)
        cooldown_days: Cooldown period in days (default 30)

    Returns:
        Dictionary keyed by (make, model) tuple with:
        - cooldown_ok: Boolean, True if can assign this model
        - last_loan_date: Date of last loan for this model
        - days_since_last: Days since last loan
    """

    try:
        cooldown_status = {}

        if loan_history_df.empty:
            return cooldown_status

        # Ensure person_id types match
        if 'person_id' in loan_history_df.columns:
            loan_history_df = loan_history_df.copy()
            loan_history_df['person_id'] = loan_history_df['person_id'].astype(int)

        # Filter to this partner
        partner_history = loan_history_df[loan_history_df['person_id'] == int(person_id)].copy()

        if partner_history.empty:
            return cooldown_status

        # Ensure end_date is datetime
        partner_history['end_date_dt'] = pd.to_datetime(partner_history['end_date'], errors='coerce')
        partner_history = partner_history.dropna(subset=['end_date_dt'])

        if partner_history.empty:
            return cooldown_status

        # Group by (make, model) and find most recent loan for each
        if 'make' in partner_history.columns and 'model' in partner_history.columns:
            for (make, model), group in partner_history.groupby(['make', 'model']):
                # Get most recent loan for this make+model
                latest = group.sort_values('end_date_dt', ascending=False).iloc[0]
                last_loan_date = latest['end_date_dt']

                # Calculate days since last loan
                today = datetime.now()
                days_since = (today - last_loan_date).days

                cooldown_ok = days_since >= cooldown_days

                cooldown_status[(make, model)] = {
                    'cooldown_ok': cooldown_ok,
                    'last_loan_date': last_loan_date.strftime('%Y-%m-%d'),
                    'days_since_last': days_since,
                    'cooldown_days_required': cooldown_days
                }

        return cooldown_status

    except Exception as e:
        logger.error(f"Error in get_model_cooldown_status: {str(e)}")
        return {}
