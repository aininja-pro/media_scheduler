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
    partners_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame = None,
    vehicle_make: str = None
) -> Dict:
    """
    Returns partners who have NOT previously reviewed this vehicle AND are approved for this make.

    Permanent exclusion: If a partner has reviewed this vehicle in loan history,
    they are permanently excluded (not time-based like model cooldown).

    Also filters by approved_makes: Only returns partners who are approved to review this vehicle's make.

    Args:
        vin: Target vehicle VIN
        office: Office to filter partners by
        loan_history_df: Historical loan data with columns: person_id, vin, start_date, end_date
        partners_df: Media partners with columns: person_id, name, office
        approved_makes_df: Optional - Approved makes with columns: person_id, make, rank
        vehicle_make: Optional - Vehicle make (e.g., 'Audi') for approved_makes filtering

    Returns:
        Dict with:
        - eligible_partners: List of partner IDs who haven't reviewed this vehicle AND are approved for the make
        - excluded_partners: List of partner IDs who have reviewed this vehicle (only from same office)
        - ineligible_make: List of partner IDs not approved for this make
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

    # Find partners who have reviewed this specific vehicle (ONLY from this office)
    reviewed_partners: Set[int] = set()
    exclusion_details = {}

    if not loan_history_df.empty and 'vin' in loan_history_df.columns:
        # Filter loan history to this specific VIN
        vehicle_history = loan_history_df[loan_history_df['vin'] == vin].copy()

        if not vehicle_history.empty:
            # Ensure person_id is integer
            vehicle_history['person_id'] = vehicle_history['person_id'].astype(int)

            # Get unique partners who reviewed this vehicle (filter to only partners in this office)
            all_reviewed = set(vehicle_history['person_id'].unique())
            reviewed_partners = all_reviewed & all_partner_ids  # Only partners in this office

            logger.info(f"Found {len(reviewed_partners)} partners from {office} who have reviewed vehicle {vin}")

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
    eligible_before_make_filter = all_partner_ids - reviewed_partners

    # Filter by approved makes if provided
    ineligible_make = []
    if approved_makes_df is not None and not approved_makes_df.empty and vehicle_make:
        # IMPORTANT: approved_makes.person_id is stored as STRING in database, convert to int
        approved_makes_copy = approved_makes_df.copy()
        approved_makes_copy['person_id'] = pd.to_numeric(approved_makes_copy['person_id'], errors='coerce').astype('Int64')

        # Get partners approved for this make
        approved_for_make = approved_makes_copy[
            approved_makes_copy['make'].str.lower() == vehicle_make.lower()
        ]

        if not approved_for_make.empty:
            approved_partner_ids = set(approved_for_make['person_id'].dropna().astype(int).unique())

            # Filter eligible to only those approved for this make
            ineligible_make = list(eligible_before_make_filter - approved_partner_ids)
            eligible_partners = list(eligible_before_make_filter & approved_partner_ids)

            logger.info(f"Make filtering ({vehicle_make}): {len(eligible_partners)} approved, {len(ineligible_make)} not approved")
        else:
            # No one approved for this make
            logger.warning(f"No partners approved for make: {vehicle_make}")
            ineligible_make = list(eligible_before_make_filter)
            eligible_partners = []
    else:
        # No make filtering
        eligible_partners = list(eligible_before_make_filter)
        logger.info(f"No make filtering applied")

    logger.info(f"Final: {len(eligible_partners)} eligible, {len(reviewed_partners)} excluded, {len(ineligible_make)} ineligible for make")

    return {
        'eligible_partners': sorted(eligible_partners),
        'excluded_partners': sorted(list(reviewed_partners)),
        'ineligible_make': sorted(ineligible_make),
        'exclusion_details': exclusion_details,
        'office_totals': {
            'total_partners': len(all_partner_ids),
            'eligible': len(eligible_partners),
            'excluded': len(reviewed_partners),
            'ineligible_make': len(ineligible_make)
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
