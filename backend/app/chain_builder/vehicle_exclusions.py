"""
Vehicle Chain Builder - Partner Exclusion Logic

This module handles exclusions for vehicle-centric chains.
Identifies partners who have previously reviewed a specific vehicle.

Key principle: If a partner has EVER reviewed a vehicle, they should NEVER
be suggested for that vehicle again (permanent exclusion).
"""

import logging
from typing import Dict, List, Set
import pandas as pd

logger = logging.getLogger(__name__)


def get_partners_not_reviewed(
    vin: str,
    office: str,
    loan_history_df: pd.DataFrame,
    partners_df: pd.DataFrame
) -> Dict:
    """
    Returns partners who have NOT previously reviewed this vehicle.

    Permanent exclusion: If a partner has reviewed this vehicle in loan history,
    they are permanently excluded (not time-based like model cooldown).

    Args:
        vin: Target vehicle VIN
        office: Office to filter partners by
        loan_history_df: Historical loan data with columns: person_id, vin, start_date, end_date
        partners_df: Media partners with columns: person_id, name, office

    Returns:
        Dict with:
        - eligible_partners: List of partner IDs who haven't reviewed this vehicle
        - excluded_partners: List of partner IDs who have reviewed this vehicle
        - exclusion_details: Dict mapping partner_id to exclusion info
        - office_totals: Stats about office partners
    """

    logger.info(f"Getting partners who haven't reviewed vehicle {vin} in {office}")

    # Filter partners to this office
    office_partners = partners_df[partners_df['office'] == office].copy()

    if office_partners.empty:
        logger.warning(f"No partners found for office: {office}")
        return {
            'eligible_partners': [],
            'excluded_partners': [],
            'exclusion_details': {},
            'office_totals': {
                'total_partners': 0,
                'eligible': 0,
                'excluded': 0
            }
        }

    all_partner_ids = set(office_partners['person_id'].astype(int).unique())
    logger.info(f"Found {len(all_partner_ids)} total partners in {office}")

    # Find partners who have reviewed this specific vehicle
    reviewed_partners: Set[int] = set()
    exclusion_details = {}

    if not loan_history_df.empty and 'vin' in loan_history_df.columns:
        # Filter loan history to this specific VIN
        vehicle_history = loan_history_df[loan_history_df['vin'] == vin].copy()

        if not vehicle_history.empty:
            # Ensure person_id is integer
            vehicle_history['person_id'] = vehicle_history['person_id'].astype(int)

            # Get unique partners who reviewed this vehicle
            reviewed_partners = set(vehicle_history['person_id'].unique())

            logger.info(f"Found {len(reviewed_partners)} partners who have reviewed vehicle {vin}")

            # Build exclusion details
            for partner_id in reviewed_partners:
                partner_loans = vehicle_history[vehicle_history['person_id'] == partner_id]

                # Get most recent loan
                if 'start_date' in partner_loans.columns:
                    partner_loans_sorted = partner_loans.sort_values('start_date', ascending=False)
                    last_loan = partner_loans_sorted.iloc[0]
                    last_loan_date = last_loan.get('start_date', 'Unknown')
                else:
                    last_loan_date = 'Unknown'

                # Get partner name
                partner_info = office_partners[office_partners['person_id'] == partner_id]
                partner_name = partner_info.iloc[0]['name'] if not partner_info.empty else f"Partner {partner_id}"

                exclusion_details[partner_id] = {
                    'name': partner_name,
                    'last_loan_date': str(last_loan_date),
                    'total_loans_this_vehicle': len(partner_loans),
                    'reason': 'Previously reviewed this vehicle'
                }
    else:
        logger.info("No loan history available or no VIN column in loan history")

    # Calculate eligible partners (never reviewed this vehicle)
    eligible_partners = list(all_partner_ids - reviewed_partners)

    logger.info(f"Exclusions: {len(eligible_partners)} eligible, {len(reviewed_partners)} excluded")

    return {
        'eligible_partners': sorted(eligible_partners),
        'excluded_partners': sorted(list(reviewed_partners)),
        'exclusion_details': exclusion_details,
        'office_totals': {
            'total_partners': len(all_partner_ids),
            'eligible': len(eligible_partners),
            'excluded': len(reviewed_partners)
        }
    }


def get_partner_vehicle_history(
    partner_id: int,
    vin: str,
    loan_history_df: pd.DataFrame
) -> Dict:
    """
    Get a specific partner's history with a specific vehicle.

    Args:
        partner_id: Partner ID
        vin: Vehicle VIN
        loan_history_df: Historical loan data

    Returns:
        Dict with:
        - has_reviewed: Boolean - has this partner reviewed this vehicle?
        - loan_count: Number of times partner has reviewed this vehicle
        - last_loan_date: Most recent loan start date (if any)
        - loans: List of loan records
    """

    if loan_history_df.empty:
        return {
            'has_reviewed': False,
            'loan_count': 0,
            'last_loan_date': None,
            'loans': []
        }

    # Filter to this partner and vehicle
    partner_vehicle_loans = loan_history_df[
        (loan_history_df['person_id'] == partner_id) &
        (loan_history_df['vin'] == vin)
    ].copy()

    if partner_vehicle_loans.empty:
        return {
            'has_reviewed': False,
            'loan_count': 0,
            'last_loan_date': None,
            'loans': []
        }

    # Sort by start_date descending
    if 'start_date' in partner_vehicle_loans.columns:
        partner_vehicle_loans = partner_vehicle_loans.sort_values('start_date', ascending=False)
        last_loan_date = str(partner_vehicle_loans.iloc[0]['start_date'])
    else:
        last_loan_date = None

    # Convert to list of dicts
    loans = partner_vehicle_loans.to_dict('records')

    return {
        'has_reviewed': True,
        'loan_count': len(partner_vehicle_loans),
        'last_loan_date': last_loan_date,
        'loans': loans
    }
