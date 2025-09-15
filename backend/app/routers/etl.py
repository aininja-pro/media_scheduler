"""
ETL API endpoints for availability and scheduling data.
"""
import pandas as pd
from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List
import logging

from ..services.database import get_database, DatabaseService
from ..etl.availability import build_availability_grid
from ..etl.cooldown import compute_cooldown_flags
from ..etl.publication import compute_publication_rate_24m

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/etl", tags=["etl"])


def get_current_monday() -> str:
    """Get the current Monday as YYYY-MM-DD string."""
    today = date.today()
    days_since_monday = today.weekday()  # 0 = Monday
    current_monday = today - timedelta(days=days_since_monday)
    return current_monday.strftime('%Y-%m-%d')


def compute_partner_eligibility(
    vehicles_df: pd.DataFrame,
    partners_df: pd.DataFrame,
    approved_makes_df: pd.DataFrame,
    cooldown_flags_df: pd.DataFrame,
    week_start: str
) -> Dict[str, Dict[str, int]]:
    """
    Compute eligible partner counts for each VIN and day.

    Returns:
        Dict[vin][day] = eligible_partner_count
    """
    week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
    days = [(week_start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

    result = {}

    for _, vehicle in vehicles_df.iterrows():
        vin = vehicle['vin']
        make = vehicle['make']
        office = vehicle['office']

        result[vin] = {}

        # Find partners eligible for this make and office
        # First get partners approved for this make
        make_partners = approved_makes_df[approved_makes_df['make'] == make]['person_id'].unique()

        # Then filter to partners in this office
        office_partners = partners_df[
            (partners_df['person_id'].isin(make_partners)) &
            (partners_df['office'] == office)
        ]

        for day in days:
            eligible_count = 0

            for _, partner in office_partners.iterrows():
                person_id = str(partner['person_id'])

                # Check if partner is in cooldown for this make (any model)
                partner_cooldown = cooldown_flags_df[
                    (cooldown_flags_df['person_id'] == person_id) &
                    (cooldown_flags_df['make'] == make)
                ]

                # If no cooldown record, assume eligible
                if partner_cooldown.empty:
                    eligible_count += 1
                else:
                    # Check if any of the cooldown records allow this partner
                    if partner_cooldown['cooldown_ok'].any():
                        eligible_count += 1

            result[vin][day] = eligible_count

    return result


@router.get("/availability")
async def get_availability_grid(
    office: str = Query(..., description="Office name (e.g., 'Los Angeles')"),
    week_start: str = Query(None, description="Week start date in YYYY-MM-DD format (defaults to current Monday)"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get vehicle availability grid for a specific office and week.

    Returns a 7-day grid showing which vehicles are available each day,
    considering lifecycle dates and current activities.

    Args:
        office: Office name to filter vehicles by
        week_start: Monday date in YYYY-MM-DD format (optional, defaults to current Monday)

    Returns:
        JSON object with office, week_start, days, rows, and summary
    """

    # Default to current Monday if week_start not provided
    if not week_start:
        week_start = get_current_monday()

    # Validate week_start format
    try:
        week_date = datetime.strptime(week_start, '%Y-%m-%d').date()
        if week_date.weekday() != 0:  # 0 = Monday
            raise HTTPException(
                status_code=400,
                detail=f"week_start must be a Monday. {week_start} is a {week_date.strftime('%A')}"
            )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="week_start must be in YYYY-MM-DD format"
        )

    if not office or not office.strip():
        raise HTTPException(
            status_code=400,
            detail="office parameter is required"
        )

    office = office.strip()

    try:
        logger.info(f"Fetching availability for office: {office}, week: {week_start}")

        # Fetch vehicles data from database
        vehicles_response = db.client.table('vehicles').select('*').execute()
        if not vehicles_response.data:
            raise HTTPException(
                status_code=404,
                detail="No vehicles found in database"
            )

        vehicles_df = pd.DataFrame(vehicles_response.data)

        # Check if office exists
        office_vehicles = vehicles_df[vehicles_df['office'].str.strip().str.lower() == office.lower()]
        if office_vehicles.empty:
            available_offices = sorted(vehicles_df['office'].str.strip().unique().tolist())
            raise HTTPException(
                status_code=404,
                detail=f"No vehicles found for office '{office}'. Available offices: {available_offices}"
            )

        # Fetch current activities
        activity_response = db.client.table('current_activity').select('*').execute()
        if activity_response.data:
            activity_df = pd.DataFrame(activity_response.data)
            # Map vehicle_vin to vin for compatibility with availability function
            if 'vehicle_vin' in activity_df.columns:
                activity_df['vin'] = activity_df['vehicle_vin']
        else:
            activity_df = pd.DataFrame()

        # Fetch partner data for eligibility calculations (get ALL records)
        all_partners = []
        partners_response = db.client.table('media_partners').select('*').limit(1000).execute()
        if partners_response.data:
            all_partners.extend(partners_response.data)

            # Fetch remaining records if there are more
            while len(partners_response.data) == 1000:
                offset = len(all_partners)
                partners_response = db.client.table('media_partners').select('*').range(offset, offset + 999).execute()
                if partners_response.data:
                    all_partners.extend(partners_response.data)
                else:
                    break

        partners_df = pd.DataFrame(all_partners) if all_partners else pd.DataFrame()

        # Fetch approved makes (get ALL records)
        all_approved = []
        approved_response = db.client.table('approved_makes').select('*').limit(1000).execute()
        if approved_response.data:
            all_approved.extend(approved_response.data)

            # Fetch remaining records if there are more
            while len(approved_response.data) == 1000:
                offset = len(all_approved)
                approved_response = db.client.table('approved_makes').select('*').range(offset, offset + 999).execute()
                if approved_response.data:
                    all_approved.extend(approved_response.data)
                else:
                    break

        approved_makes_df = pd.DataFrame(all_approved) if all_approved else pd.DataFrame()

        # Fetch loan history for cooldown calculation (limit to recent records for performance)
        loan_history_response = db.client.table('loan_history').select('*').limit(2000).execute()
        loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

        # Fetch rules for cooldown calculation
        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

        logger.info(f"Fetched {len(partners_df)} partners, {len(approved_makes_df)} approved makes, {len(loan_history_df)} loan history records")

        # Convert date columns
        for date_col in ['in_service_date', 'expected_turn_in_date']:
            if date_col in vehicles_df.columns:
                vehicles_df[date_col] = pd.to_datetime(vehicles_df[date_col], errors='coerce').dt.date

        if not activity_df.empty:
            for date_col in ['start_date', 'end_date']:
                if date_col in activity_df.columns:
                    activity_df[date_col] = pd.to_datetime(activity_df[date_col], errors='coerce').dt.date

        # Build availability grid using existing ETL function
        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office
        )

        # Compute cooldown flags for partner eligibility
        cooldown_flags_df = pd.DataFrame()
        if not loan_history_df.empty:
            try:
                cooldown_flags_df = compute_cooldown_flags(
                    loan_history_df=loan_history_df,
                    rules_df=rules_df,
                    week_start=week_start,
                    default_days=60
                )
            except Exception as e:
                logger.warning(f"Failed to compute cooldown flags: {e}")

        # Compute partner eligibility counts
        partner_eligibility = {}
        if not vehicles_df.empty and not partners_df.empty and not approved_makes_df.empty:
            try:
                partner_eligibility = compute_partner_eligibility(
                    vehicles_df=vehicles_df[vehicles_df['office'] == office],
                    partners_df=partners_df,
                    approved_makes_df=approved_makes_df,
                    cooldown_flags_df=cooldown_flags_df,
                    week_start=week_start
                )
            except Exception as e:
                logger.warning(f"Failed to compute partner eligibility: {e}")

        if availability_df.empty:
            return {
                "office": office,
                "week_start": week_start,
                "days": [],
                "rows": [],
                "summary": {
                    "vehicle_count": 0,
                    "available_today": 0,
                    "availability_rate_today": 0.0,
                    "available_by_day": []
                }
            }

        # Generate 7 days array
        week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
        days = [(week_start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        # Convert availability data to the required format
        # Group by VIN and create availability arrays
        rows = []
        for vin in sorted(availability_df['vin'].unique()):
            vin_data = availability_df[availability_df['vin'] == vin].sort_values('day')
            availability_array = vin_data['available'].tolist()

            # Ensure we have exactly 7 days
            if len(availability_array) != 7:
                logger.warning(f"VIN {vin} has {len(availability_array)} days instead of 7")
                continue

            # Get partner eligibility counts for each day
            partner_counts = []
            if vin in partner_eligibility:
                for day_str in days:
                    partner_counts.append(partner_eligibility[vin].get(day_str, 0))
            else:
                partner_counts = [0] * 7

            # Get vehicle make and model info
            vehicle_info = vehicles_df[vehicles_df['vin'] == vin].iloc[0]

            rows.append({
                "vin": vin,
                "make": vehicle_info['make'],
                "model": vehicle_info.get('model', ''),
                "office": office,
                "availability": availability_array,
                "eligible_partner_counts": partner_counts
            })

        # Calculate summary statistics
        # Use Monday (first day) of the selected week for "available today" calculation
        monday_str = days[0]  # First day is always Monday
        available_today = sum(1 for row in rows if row['availability'][0])  # Monday availability
        total_vehicles = len(rows)
        availability_rate_today = available_today / total_vehicles if total_vehicles > 0 else 0.0

        # Calculate available by day
        available_by_day = []
        for day_index in range(7):
            available_count = sum(1 for row in rows if row['availability'][day_index])
            available_by_day.append(available_count)

        summary = {
            "vehicle_count": len(rows),
            "available_today": available_today,
            "availability_rate_today": round(availability_rate_today, 3),
            "available_by_day": available_by_day
        }

        logger.info(f"Generated availability grid: {len(rows)} vehicles, {sum(available_by_day)} total available slots")

        return {
            "office": office,
            "week_start": week_start,
            "days": days,
            "rows": rows,
            "summary": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating availability grid: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating availability grid: {str(e)}"
        )


@router.get("/offices")
async def get_offices(
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get list of available offices from the vehicles table.

    Returns:
        List of office names
    """
    try:
        # Fetch distinct offices from vehicles table
        vehicles_response = db.client.table('vehicles').select('office').execute()
        if not vehicles_response.data:
            return {"offices": []}

        vehicles_df = pd.DataFrame(vehicles_response.data)
        offices = sorted(vehicles_df['office'].str.strip().unique().tolist())

        return {"offices": offices}

    except Exception as e:
        logger.error(f"Error fetching offices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching offices: {str(e)}"
        )


@router.get("/eligible_partners")
async def get_eligible_partners(
    vin: str = Query(..., description="Vehicle VIN"),
    day: str = Query(..., description="Target date in YYYY-MM-DD format"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get detailed information about eligible and blocked partners for a specific VIN on a specific day.

    Args:
        vin: Vehicle VIN
        day: Target date in YYYY-MM-DD format

    Returns:
        JSON object with eligible and blocked partner details
    """

    # Validate day format
    try:
        target_date = datetime.strptime(day, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="day must be in YYYY-MM-DD format"
        )

    # Calculate week_start (find the Monday of this week)
    days_since_monday = target_date.weekday()
    week_start_date = target_date - timedelta(days=days_since_monday)
    week_start = week_start_date.strftime('%Y-%m-%d')

    try:
        # Fetch vehicle info
        vehicle_response = db.client.table('vehicles').select('*').eq('vin', vin).execute()
        if not vehicle_response.data:
            raise HTTPException(status_code=404, detail=f"Vehicle with VIN {vin} not found")

        vehicle = vehicle_response.data[0]
        make = vehicle['make']
        model = vehicle.get('model', '')
        office = vehicle['office']

        # Fetch all required data (get ALL records for accurate eligibility)
        # Partners - get all
        all_partners = []
        partners_response = db.client.table('media_partners').select('*').limit(1000).execute()
        if partners_response.data:
            all_partners.extend(partners_response.data)
            while len(partners_response.data) == 1000:
                offset = len(all_partners)
                partners_response = db.client.table('media_partners').select('*').range(offset, offset + 999).execute()
                if partners_response.data:
                    all_partners.extend(partners_response.data)
                else:
                    break
        partners_df = pd.DataFrame(all_partners) if all_partners else pd.DataFrame()

        # Approved makes - get all
        all_approved = []
        approved_response = db.client.table('approved_makes').select('*').limit(1000).execute()
        if approved_response.data:
            all_approved.extend(approved_response.data)
            while len(approved_response.data) == 1000:
                offset = len(all_approved)
                approved_response = db.client.table('approved_makes').select('*').range(offset, offset + 999).execute()
                if approved_response.data:
                    all_approved.extend(approved_response.data)
                else:
                    break
        approved_makes_df = pd.DataFrame(all_approved) if all_approved else pd.DataFrame()

        # Loan history - limit for performance
        loan_history_response = db.client.table('loan_history').select('*').limit(2000).execute()
        loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

        # Rules
        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

        # Compute cooldown flags
        cooldown_flags_df = pd.DataFrame()
        if not loan_history_df.empty:
            try:
                cooldown_flags_df = compute_cooldown_flags(
                    loan_history_df=loan_history_df,
                    rules_df=rules_df,
                    week_start=week_start,
                    default_days=60
                )
            except Exception as e:
                logger.warning(f"Failed to compute cooldown flags: {e}")

        # Find partners eligible for this make and office
        eligible_partners = []
        blocked_partners = []

        if not approved_makes_df.empty and not partners_df.empty:
            # Get partners approved for this make
            make_partners = approved_makes_df[approved_makes_df['make'] == make]['person_id'].unique()

            # Filter to partners in this office
            office_partners = partners_df[
                (partners_df['person_id'].isin(make_partners)) &
                (partners_df['office'] == office)
            ]

            for _, partner in office_partners.iterrows():
                person_id = str(partner['person_id'])

                # Get the partner's rank for this make from approved_makes
                partner_approvals = approved_makes_df[
                    (approved_makes_df['person_id'].astype(str) == person_id) &
                    (approved_makes_df['make'] == make)
                ]

                # Get the rank (there might be multiple, take the first one)
                rank = partner_approvals['rank'].iloc[0] if not partner_approvals.empty else "A"

                partner_info = {
                    "partner_id": person_id,
                    "name": partner.get('name', f"Partner {person_id}"),
                    "rank": rank,
                    "why": ["eligible"]  # Base eligibility
                }

                # Check cooldown status
                partner_cooldown = cooldown_flags_df[
                    (cooldown_flags_df['person_id'] == person_id) &
                    (cooldown_flags_df['make'] == make)
                ]

                if partner_cooldown.empty:
                    # No cooldown record, assume eligible
                    partner_info["why"].append("cooldown_ok")
                    eligible_partners.append(partner_info)
                else:
                    # Check if any cooldown records allow this partner
                    if partner_cooldown['cooldown_ok'].any():
                        partner_info["why"].append("cooldown_ok")
                        eligible_partners.append(partner_info)
                    else:
                        # Partner is blocked by cooldown
                        blocked_until = partner_cooldown['cooldown_until'].max()
                        partner_info["why"] = [f"cooldown_until={blocked_until}"]
                        blocked_partners.append(partner_info)

        return {
            "vin": vin,
            "day": day,
            "make": make,
            "model": model,
            "office": office,
            "eligible": eligible_partners,
            "blocked": blocked_partners
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting eligible partners for VIN {vin}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting eligible partners: {str(e)}"
        )


@router.get("/publication_rates")
async def get_publication_rates(
    as_of_date: str = Query(None, description="As-of date in YYYY-MM-DD format (defaults to today)"),
    window_months: int = Query(24, description="Rolling window in months (default: 24)"),
    min_observed: int = Query(3, description="Minimum observed loans for supported flag (default: 3)"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get 24-month rolling publication rates for all partner-make combinations.

    Shows which partners have good publication rates (clips received) for each vehicle make
    based on their loan history. Includes coverage and support flags for data quality.

    Args:
        as_of_date: End date for analysis window (optional, defaults to today)
        window_months: Length of rolling window in months (default: 24)
        min_observed: Minimum observed loans required for supported=True (default: 3)

    Returns:
        JSON object with publication rate analysis and summary statistics
    """

    try:
        logger.info(f"Computing publication rates as of {as_of_date or 'today'}")

        # Fetch ALL loan history records
        all_loans = []
        loan_response = db.client.table('loan_history').select('*').limit(1000).execute()
        if loan_response.data:
            all_loans.extend(loan_response.data)

            while len(loan_response.data) == 1000:
                offset = len(all_loans)
                loan_response = db.client.table('loan_history').select('*').range(offset, offset + 999).execute()
                if loan_response.data:
                    all_loans.extend(loan_response.data)
                else:
                    break

        loan_history_df = pd.DataFrame(all_loans) if all_loans else pd.DataFrame()

        # Fetch partner names for display
        all_partners = []
        partners_response = db.client.table('media_partners').select('person_id', 'name').limit(1000).execute()
        if partners_response.data:
            all_partners.extend(partners_response.data)
            while len(partners_response.data) == 1000:
                offset = len(all_partners)
                partners_response = db.client.table('media_partners').select('person_id', 'name').range(offset, offset + 999).execute()
                if partners_response.data:
                    all_partners.extend(partners_response.data)
                else:
                    break

        partners_lookup = pd.DataFrame(all_partners) if all_partners else pd.DataFrame()
        if not partners_lookup.empty:
            partners_lookup['person_id'] = partners_lookup['person_id'].astype(str)
            partners_dict = dict(zip(partners_lookup['person_id'], partners_lookup['name']))
        else:
            partners_dict = {}

        if loan_history_df.empty:
            raise HTTPException(
                status_code=404,
                detail="No loan history data found"
            )

        logger.info(f"Fetched {len(loan_history_df)} loan history records")

        # Compute publication rates
        result = compute_publication_rate_24m(
            loan_history_df=loan_history_df,
            as_of_date=as_of_date,
            window_months=window_months,
            min_observed=min_observed
        )

        if result.empty:
            return {
                "as_of_date": as_of_date,
                "window_months": window_months,
                "grains": [],
                "summary": {
                    "total_grains": 0,
                    "unique_partners": 0,
                    "unique_makes": 0,
                    "total_loans": 0,
                    "supported_grains": 0,
                    "coverage_average": 0.0
                }
            }

        # Convert result to JSON-friendly format
        grains = []
        for _, row in result.iterrows():
            person_id_str = str(int(float(row['person_id'])))  # Remove decimal from partner ID
            partner_name = partners_dict.get(person_id_str, f"Partner {person_id_str}")

            grains.append({
                "person_id": person_id_str,
                "partner_name": partner_name,
                "make": row['make'],
                "loans_total_24m": int(row['loans_total_24m']),
                "publications_24m": int(row['publications_24m']),
                "publication_rate": row['publication_rate'],
                "has_clip_data": bool(row['has_clip_data']),
                "window_start": row['window_start'].strftime('%Y-%m-%d'),
                "window_end": row['window_end'].strftime('%Y-%m-%d')
            })

        # Calculate summary statistics
        summary = {
            "total_grains": len(result),
            "unique_partners": result['person_id'].nunique(),
            "unique_makes": result['make'].nunique(),
            "total_loans": int(result['loans_total_24m'].sum()),
            "total_published": int(result['publications_24m'].sum()),
            "grains_with_data": int(result['has_clip_data'].sum()),
            "window_start": result['window_start'].iloc[0].strftime('%Y-%m-%d'),
            "window_end": result['window_end'].iloc[0].strftime('%Y-%m-%d')
        }

        # Add make-level statistics
        make_stats = result.groupby('make').agg({
            'loans_total_24m': 'sum',
            'publications_24m': 'sum',
            'person_id': 'nunique'
        }).reset_index()

        make_stats['overall_rate'] = make_stats.apply(
            lambda r: r['publications_24m'] / r['loans_total_24m']
                     if r['loans_total_24m'] > 0 else None, axis=1
        )

        summary["by_make"] = []
        for _, make_row in make_stats.iterrows():
            summary["by_make"].append({
                "make": make_row['make'],
                "total_loans": int(make_row['loans_total_24m']),
                "published_loans": int(make_row['publications_24m']),
                "partner_count": int(make_row['person_id']),
                "overall_rate": round(make_row['overall_rate'], 3) if pd.notna(make_row['overall_rate']) else None
            })

        logger.info(f"Generated publication rates: {len(grains)} grains, {summary['grains_with_data']} with data")

        return {
            "as_of_date": as_of_date,
            "window_months": window_months,
            "grains": grains,
            "summary": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing publication rates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error computing publication rates: {str(e)}"
        )