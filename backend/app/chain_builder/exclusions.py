"""
Exclusion logic for Chain Builder

Filters out vehicles that:
- Partner has already reviewed (from loan_history)
- Would violate model-specific cooldown rules
"""

import pandas as pd
from typing import Set, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def get_vehicles_not_reviewed(
    person_id: str,
    office: str,
    loan_history_df: pd.DataFrame,
    vehicles_df: pd.DataFrame,
    months_back: int = 12
) -> Dict[str, Any]:
    """
    Get vehicles from office that partner has NOT reviewed.

    Args:
        person_id: Media partner ID
        office: Office to filter vehicles
        loan_history_df: Historical loan data
        vehicles_df: All vehicles in system
        months_back: How far back to check (default 12 months, but we exclude ALL reviewed VINs)

    Returns:
        Dictionary with:
        - available_vins: Set of VINs partner hasn't reviewed
        - excluded_vins: Set of VINs partner has reviewed
        - office_vehicle_count: Total vehicles in office
        - exclusion_details: Details about excluded vehicles
    """

    try:
        # Filter vehicles to target office
        office_vehicles = vehicles_df[vehicles_df['office'] == office].copy()
        all_office_vins = set(office_vehicles['vin'].unique())

        if loan_history_df.empty:
            logger.info(f"No loan history found. All {len(all_office_vins)} vehicles in {office} are available.")
            return {
                'available_vins': all_office_vins,
                'excluded_vins': set(),
                'office_vehicle_count': len(all_office_vins),
                'available_vehicle_count': len(all_office_vins),
                'exclusion_details': []
            }

        # Get all VINs this partner has EVER reviewed
        # We exclude them permanently (not time-based exclusion)
        partner_history = loan_history_df[loan_history_df['person_id'] == person_id]

        if partner_history.empty:
            logger.info(f"Partner {person_id} has no loan history. All {len(all_office_vins)} vehicles available.")
            return {
                'available_vins': all_office_vins,
                'excluded_vins': set(),
                'office_vehicle_count': len(all_office_vins),
                'available_vehicle_count': len(all_office_vins),
                'exclusion_details': []
            }

        # Get VINs partner has reviewed
        reviewed_vins = set(partner_history['vin'].dropna().unique())

        # Filter to only VINs that are in this office
        excluded_vins = reviewed_vins & all_office_vins  # Intersection
        available_vins = all_office_vins - excluded_vins

        # Build exclusion details for logging/debugging
        exclusion_details = []
        if not partner_history.empty and 'end_date' in partner_history.columns:
            # Convert end_date to datetime for sorting (use .copy() to avoid SettingWithCopyWarning)
            partner_history = partner_history.copy()
            partner_history['end_date_dt'] = pd.to_datetime(partner_history['end_date'], errors='coerce')

            for vin in excluded_vins:
                vin_history = partner_history[partner_history['vin'] == vin]
                if not vin_history.empty:
                    # Get most recent loan for this VIN
                    latest = vin_history.sort_values('end_date_dt', ascending=False).iloc[0]

                    vehicle_info = office_vehicles[office_vehicles['vin'] == vin]
                    make = vehicle_info.iloc[0]['make'] if not vehicle_info.empty and 'make' in vehicle_info.columns else 'Unknown'
                    model = vehicle_info.iloc[0]['model'] if not vehicle_info.empty and 'model' in vehicle_info.columns else 'Unknown'

                    exclusion_details.append({
                        'vin': vin,
                        'make': make,
                        'model': model,
                        'last_reviewed_date': latest['end_date_dt'].strftime('%Y-%m-%d') if pd.notna(latest['end_date_dt']) else 'Unknown',
                        'reason': 'Already reviewed by partner'
                    })

        logger.info(f"Partner {person_id} exclusion: {len(excluded_vins)} VINs excluded, {len(available_vins)} available")

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
    person_id: str,
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

        # Filter to this partner
        partner_history = loan_history_df[loan_history_df['person_id'] == person_id].copy()

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
