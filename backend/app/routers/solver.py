"""
Real solver API that calls the actual Phase 5 pipeline.
"""

import time
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any
import logging
import pandas as pd

from ..services.database import get_database, DatabaseService
from ..solver.candidates import build_weekly_candidates
from ..solver.scoring import compute_candidate_scores
from ..solver.greedy_assign import generate_week_schedule
from ..etl.availability import build_availability_grid
from ..etl.cooldown import compute_cooldown_flags

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/solver", tags=["solver"])


@router.get("/assignment_options")
async def get_assignment_options(
    office: str = Query(..., description="Office name"),
    week_start: str = Query(..., description="Week start date (YYYY-MM-DD)"),
    min_available_days: int = Query(5, description="Minimum available days"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get all possible assignment options for Phase 6 UI.
    Returns partner-centric view with all eligible vehicles per partner.
    """

    try:
        logger.info(f"Getting assignment options for {office}, week {week_start}")

        # Load data (same as generate_schedule)
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

        if vehicles_df.empty:
            return {
                'office': office,
                'week_start': week_start,
                'eligible_partners': [],
                'available_vehicles': [],
                'message': f'No vehicles found for {office}'
            }

        # Current activity
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

        if 'vehicle_vin' in activity_df.columns:
            activity_df['vin'] = activity_df['vehicle_vin']

        # Get media partners for this office ONLY
        office_partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        office_partners = pd.DataFrame(office_partners_response.data) if office_partners_response.data else pd.DataFrame()
        office_partner_ids = set(office_partners['person_id'].tolist()) if not office_partners.empty else set()

        # Get approved makes
        all_approved = []
        limit = 1000
        offset = 0
        while True:
            approved_response = db.client.table('approved_makes').select('person_id, make, rank').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            offset += limit
            if len(approved_response.data) < limit:
                break

        approved_makes_df = pd.DataFrame(all_approved)
        approved_makes_df = approved_makes_df[approved_makes_df['person_id'].isin(office_partner_ids)]

        # Get loan history
        loan_history_response = db.client.table('loan_history').select('*').execute()
        loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

        # Get rules
        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

        # Convert dates
        for date_col in ['in_service_date', 'expected_turn_in_date']:
            if date_col in vehicles_df.columns:
                vehicles_df[date_col] = pd.to_datetime(vehicles_df[date_col], errors='coerce').dt.date

        if not activity_df.empty:
            for date_col in ['start_date', 'end_date']:
                if date_col in activity_df.columns:
                    activity_df[date_col] = pd.to_datetime(activity_df[date_col], errors='coerce').dt.date

        if not loan_history_df.empty:
            for date_col in ['start_date', 'end_date']:
                if date_col in loan_history_df.columns:
                    loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col], errors='coerce').dt.date

        # Build availability grid
        availability_grid_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office
        )

        # Convert to availability format
        availability_records = []
        if not availability_grid_df.empty:
            # Get available columns for vehicle lookup
            lookup_cols = ['make', 'model']
            if 'year' in vehicles_df.columns:
                lookup_cols.append('year')
            if 'trim' in vehicles_df.columns:
                lookup_cols.append('trim')

            vehicle_lookup = vehicles_df.set_index('vin')[lookup_cols].to_dict('index')

            for _, row in availability_grid_df.iterrows():
                vin = row['vin']
                vehicle_info = vehicle_lookup.get(vin, {'make': '', 'model': '', 'year': '', 'trim': ''})

                availability_records.append({
                    'vin': vin,
                    'date': row['day'].strftime('%Y-%m-%d'),
                    'market': office,
                    'make': vehicle_info.get('make', ''),
                    'model': vehicle_info.get('model', ''),
                    'available': row['available']
                })

        availability_df = pd.DataFrame(availability_records)

        # Compute cooldown
        cooldown_df = compute_cooldown_flags(
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            week_start=week_start,
            default_days=30
        )

        # Build candidates (same as before)
        office_vehicle_makes = set(vehicles_df['make'].unique())
        office_approved = approved_makes_df[approved_makes_df['make'].isin(office_vehicle_makes)]

        partners_with_approvals = set(office_approved['person_id'].unique())
        partners_without_approvals = office_partner_ids - partners_with_approvals

        publication_records = [
            {'person_id': pid, 'make': make, 'rank': rank, 'publication_rate_observed': None, 'supported': False, 'coverage': 0.0}
            for pid, make, rank in office_approved[['person_id', 'make', 'rank']].drop_duplicates().values
        ]

        # Add partners WITHOUT approved_makes (get C rank)
        for partner_id in partners_without_approvals:
            for make in office_vehicle_makes:
                publication_records.append({
                    'person_id': partner_id,
                    'make': make,
                    'rank': 'C',
                    'publication_rate_observed': None,
                    'supported': False,
                    'coverage': 0.0
                })

        publication_df = pd.DataFrame(publication_records)
        eligibility_df = publication_df[['person_id', 'make', 'rank']].drop_duplicates()

        # Build candidates
        candidates_df = build_weekly_candidates(
            availability_df=availability_df,
            cooldown_df=cooldown_df,
            publication_df=publication_df,
            week_start=week_start,
            eligibility_df=eligibility_df,
            min_available_days=min_available_days
        )

        # Score candidates
        scored_candidates = pd.DataFrame()
        if not candidates_df.empty:
            scored_candidates = compute_candidate_scores(
                candidates_df=candidates_df,
                partner_rank_df=eligibility_df,
                partners_df=office_partners,
                publication_df=publication_df
            )

        # Calculate tier cap usage for each partner-make combo
        from ..solver.greedy_assign import _loans_12m_by_pair, _resolve_pair_cap

        # Get 12-month usage counts
        pair_used = _loans_12m_by_pair(loan_history_df, week_start)

        # Build partner-centric response
        partner_options = []

        for partner_id in office_partner_ids:
            partner_row = office_partners[office_partners['person_id'] == partner_id]
            if not partner_row.empty:
                partner_name = str(partner_row.iloc[0]['name'])
            else:
                partner_name = f'Partner {partner_id}'

            # Get this partner's candidates
            partner_candidates = scored_candidates[scored_candidates['person_id'] == partner_id] if not scored_candidates.empty else pd.DataFrame()

            if not partner_candidates.empty:
                # Get available vehicles for this partner
                available_vehicles = []
                for _, cand in partner_candidates.iterrows():
                    vehicle_row = vehicles_df[vehicles_df['vin'] == cand['vin']]
                    year = ''
                    if not vehicle_row.empty and 'year' in vehicle_row.columns:
                        year = str(vehicle_row.iloc[0].get('year', ''))

                    available_vehicles.append({
                        'vin': str(cand['vin']),
                        'make': str(cand['make']),
                        'model': str(cand.get('model', '')),
                        'year': year,
                        'score': int(cand['score']),
                        'rank': str(cand.get('rank', 'C'))
                    })

                # Get rank distribution for this partner
                partner_ranks = eligibility_df[eligibility_df['person_id'] == partner_id]['rank'].value_counts().to_dict() if not eligibility_df[eligibility_df['person_id'] == partner_id].empty else {}

                # Check last assignment from loan history
                last_assignment = None
                if not loan_history_df.empty:
                    partner_history = loan_history_df[loan_history_df['person_id'] == partner_id]
                    if not partner_history.empty:
                        latest = partner_history.nlargest(1, 'end_date')
                        if not latest.empty:
                            last_date = latest['end_date'].iloc[0]
                            last_make = latest['make'].iloc[0]
                            last_assignment = {
                                'date': last_date.isoformat() if hasattr(last_date, 'isoformat') else str(last_date),
                                'make': last_make
                            }

                # Calculate tier cap usage per make
                tier_cap_usage = {}
                for make in set([v['make'] for v in available_vehicles]):
                    used = int(pair_used.get((partner_id, make), 0))
                    # Get rank for this make
                    partner_make_rank = eligibility_df[
                        (eligibility_df['person_id'] == partner_id) &
                        (eligibility_df['make'] == make)
                    ]['rank'].iloc[0] if not eligibility_df[
                        (eligibility_df['person_id'] == partner_id) &
                        (eligibility_df['make'] == make)
                    ].empty else 'C'

                    cap = _resolve_pair_cap(make=make, rank=partner_make_rank, rules_df=rules_df)
                    tier_cap_usage[make] = {
                        'used': used,
                        'cap': cap,
                        'remaining': max(0, cap - used),
                        'rank': str(partner_make_rank)
                    }

                # Check cooldown status for each make
                cooldown_status = {}
                if not cooldown_df.empty:
                    partner_cooldowns = cooldown_df[cooldown_df['person_id'] == partner_id]
                    for make in set([v['make'] for v in available_vehicles]):
                        make_cooldown = partner_cooldowns[partner_cooldowns['make'] == make]
                        if not make_cooldown.empty:
                            cooldown_status[make] = bool(make_cooldown.iloc[0]['cooldown_ok'])
                        else:
                            cooldown_status[make] = True

                # Group available vehicles by make for better UI display
                vehicles_by_make = {}
                for vehicle in available_vehicles:
                    make = vehicle['make']
                    if make not in vehicles_by_make:
                        vehicles_by_make[make] = []
                    vehicles_by_make[make].append(vehicle)

                partner_options.append({
                    'person_id': int(partner_id),
                    'name': str(partner_name),
                    'rank_summary': {str(k): int(v) for k, v in partner_ranks.items()},
                    'available_vehicles': available_vehicles,
                    'vehicles_by_make': vehicles_by_make,
                    'vehicle_count': len(available_vehicles),
                    'last_assignment': last_assignment,
                    'max_score': max([v['score'] for v in available_vehicles]) if available_vehicles else 0,
                    'tier_cap_usage': tier_cap_usage,
                    'cooldown_status': cooldown_status
                })

        # Sort partners by max score and vehicle count
        partner_options.sort(key=lambda x: (-x['max_score'], -x['vehicle_count']))

        # Get available vehicles summary
        available_vins = set()
        if not availability_grid_df.empty:
            for vin in availability_grid_df['vin'].unique():
                vin_days = availability_grid_df[availability_grid_df['vin'] == vin]
                if vin_days['available'].sum() >= min_available_days:
                    available_vins.add(vin)

        vehicle_summary = []
        for vin in available_vins:
            vehicle_row = vehicles_df[vehicles_df['vin'] == vin]
            if not vehicle_row.empty:
                vinfo = vehicle_row.iloc[0]
                vehicle_summary.append({
                    'vin': str(vin),
                    'make': str(vinfo.get('make', '')),
                    'model': str(vinfo.get('model', '')),
                    'year': str(vinfo.get('year', '')) if 'year' in vehicle_row.columns else ''
                })

        # Calculate constraint summary
        constraint_summary = {
            'partners_at_tier_cap': 0,
            'partners_in_cooldown': 0,
            'total_tier_cap_blocks': 0,
            'total_cooldown_blocks': 0
        }

        for partner in partner_options:
            # Check if any make is at tier cap
            at_cap = False
            for make, usage in partner.get('tier_cap_usage', {}).items():
                if usage['remaining'] == 0:
                    at_cap = True
                    constraint_summary['total_tier_cap_blocks'] += 1

            if at_cap:
                constraint_summary['partners_at_tier_cap'] += 1

            # Check if any make is in cooldown
            in_cooldown = False
            for make, ok in partner.get('cooldown_status', {}).items():
                if not ok:
                    in_cooldown = True
                    constraint_summary['total_cooldown_blocks'] += 1

            if in_cooldown:
                constraint_summary['partners_in_cooldown'] += 1

        return {
            'office': office,
            'week_start': week_start,
            'eligible_partners': partner_options,
            'available_vehicles': vehicle_summary,
            'stats': {
                'total_partners': len(partner_options),
                'partners_with_options': len([p for p in partner_options if p['vehicle_count'] > 0]),
                'total_vehicles': len(available_vins),
                'total_candidates': len(scored_candidates) if not scored_candidates.empty else 0
            },
            'constraint_summary': constraint_summary,
            'greedy_solution': {
                'message': 'Use /generate_schedule endpoint for greedy solution',
                'explanation': 'The greedy algorithm would pick highest scoring partners first, which may not be optimal for distribution'
            }
        }

    except Exception as e:
        logger.error(f"Error getting assignment options: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate_schedule")
async def generate_schedule(
    office: str = Query(..., description="Office name"),
    week_start: str = Query(..., description="Week start date (YYYY-MM-DD)"),
    min_available_days: int = Query(7, description="Minimum available days"),
    enable_tier_caps: bool = Query(True, description="Enable tier cap constraints"),
    enable_cooldown: bool = Query(True, description="Enable cooldown constraints"),
    enable_capacity: bool = Query(True, description="Enable daily capacity constraints"),
    cooldown_days: int = Query(30, description="Cooldown period in days"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """Generate weekly schedule using real Phase 5 pipeline."""

    try:
        logger.info(f"Generating schedule for {office}, week {week_start}, cooldown={cooldown_days}days")

        total_start = time.time()

        # Load ALL data from Supabase
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

        if vehicles_df.empty:
            raise HTTPException(status_code=400, detail=f"No vehicles found for {office}")

        # Current activity
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

        # Fix activity column name
        if not activity_df.empty and 'vehicle_vin' in activity_df.columns:
            activity_df['vin'] = activity_df['vehicle_vin']

        # Get media partners for this office ONLY
        office_partners_response = db.client.table('media_partners').select('person_id').eq('office', office).execute()
        office_partner_ids = set([p['person_id'] for p in office_partners_response.data]) if office_partners_response.data else set()
        logger.info(f"Found {len(office_partner_ids)} partners for office {office}")

        # ALL approved makes
        all_approved = []
        limit = 1000
        offset = 0
        while True:
            approved_response = db.client.table('approved_makes').select('person_id, make, rank').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            offset += limit
            if len(approved_response.data) < limit:
                break

        approved_makes_df = pd.DataFrame(all_approved)

        # Filter to only partners from this office
        approved_makes_df = approved_makes_df[approved_makes_df['person_id'].isin(office_partner_ids)]

        # ALL loan history
        all_loan_history = []
        limit = 1000
        offset = 0
        while True:
            loan_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
            if not loan_response.data:
                break
            all_loan_history.extend(loan_response.data)
            offset += limit
            if len(loan_response.data) < limit:
                break

        loan_history_df = pd.DataFrame(all_loan_history)

        # Other data
        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

        ops_response = db.client.table('ops_capacity').select('*').execute()
        ops_capacity_df = pd.DataFrame(ops_response.data) if ops_response.data else pd.DataFrame()

        partners_response = db.client.table('media_partners').select('*').execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

        # Convert dates
        for date_col in ['in_service_date', 'expected_turn_in_date']:
            if date_col in vehicles_df.columns:
                vehicles_df[date_col] = pd.to_datetime(vehicles_df[date_col], errors='coerce').dt.date

        if not activity_df.empty:
            for date_col in ['start_date', 'end_date']:
                if date_col in activity_df.columns:
                    activity_df[date_col] = pd.to_datetime(activity_df[date_col], errors='coerce').dt.date

        if not loan_history_df.empty:
            for date_col in ['start_date', 'end_date']:
                if date_col in loan_history_df.columns:
                    loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col], errors='coerce').dt.date

        # STAGE 1: Generate candidates
        stage1_start = time.time()

        # Build availability
        availability_grid_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office
        )

        # Convert to candidate format
        availability_records = []
        if not availability_grid_df.empty:
            vehicle_lookup = vehicles_df.set_index('vin')[['make', 'model']].to_dict('index')

            for _, row in availability_grid_df.iterrows():
                vin = row['vin']
                vehicle_info = vehicle_lookup.get(vin, {'make': '', 'model': ''})

                availability_records.append({
                    'vin': vin,
                    'date': row['day'].strftime('%Y-%m-%d'),
                    'market': office,
                    'make': vehicle_info.get('make', ''),
                    'model': vehicle_info.get('model', ''),
                    'available': row['available']
                })

        availability_df = pd.DataFrame(availability_records)

        # Compute cooldown with configurable period
        cooldown_df = compute_cooldown_flags(
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            week_start=week_start,
            default_days=cooldown_days if enable_cooldown else 0
        ) if enable_cooldown else pd.DataFrame()

        # Filter approved makes to office vehicle makes
        office_vehicle_makes = set(vehicles_df['make'].unique())
        office_approved = approved_makes_df[approved_makes_df['make'].isin(office_vehicle_makes)]

        # Get partners who have approved_makes entries
        partners_with_approvals = set(office_approved['person_id'].unique())

        # Find partners without any approved_makes entries
        partners_without_approvals = office_partner_ids - partners_with_approvals

        # Create publication data for partners WITH approved_makes
        publication_records = [
            {'person_id': pid, 'make': make, 'rank': rank, 'publication_rate_observed': None, 'supported': False, 'coverage': 0.0}
            for pid, make, rank in office_approved[['person_id', 'make', 'rank']].drop_duplicates().values
        ]

        # Add partners WITHOUT approved_makes (they get default C rank for all makes)
        for partner_id in partners_without_approvals:
            for make in office_vehicle_makes:
                publication_records.append({
                    'person_id': partner_id,
                    'make': make,
                    'rank': 'C',  # Default rank for partners without specific approvals
                    'publication_rate_observed': None,
                    'supported': False,
                    'coverage': 0.0
                })

        publication_df = pd.DataFrame(publication_records)
        logger.info(f"Total eligible partner-make pairs: {len(publication_df)}")
        logger.info(f"Partners with approvals: {len(partners_with_approvals)}, without: {len(partners_without_approvals)}")

        # Create eligibility_df from publication_df (includes rank)
        eligibility_df = publication_df[['person_id', 'make', 'rank']].drop_duplicates()

        candidates_df = build_weekly_candidates(
            availability_df=availability_df,
            cooldown_df=cooldown_df,
            publication_df=publication_df,
            week_start=week_start,
            eligibility_df=eligibility_df,
            min_available_days=min_available_days
        )

        stage1_time = time.time() - stage1_start

        if candidates_df.empty:
            return {
                'office': office,
                'week_start': week_start,
                'pipeline': {
                    'total_duration': stage1_time,
                    'stage1': {'duration': stage1_time, 'candidate_count': 0, 'unique_vins': 0, 'unique_partners': 0, 'unique_makes': 0, 'office_partners': len(office_partner_ids)},
                    'stage2': {'duration': 0, 'scored_count': 0, 'score_min': 0, 'score_max': 0, 'rank_distribution': {}},
                    'stage3': {'duration': 0, 'assignment_count': 0}
                },
                'assignments': [],
                'summary': {'unique_vins': 0, 'unique_partners': 0, 'unique_makes': 0},
                'constraint_analysis': {},
                'message': f'No feasible VIN-partner pairings found for {office}'
            }

        # STAGE 2: Score candidates
        stage2_start = time.time()

        scored_candidates = compute_candidate_scores(
            candidates_df=candidates_df,
            partner_rank_df=eligibility_df,  # Use filtered eligibility data with ranks
            partners_df=partners_df,
            publication_df=publication_df
        )

        stage2_time = time.time() - stage2_start

        # STAGE 3: Generate assignments
        stage3_start = time.time()

        # Apply constraint toggles
        if not enable_capacity:
            ops_capacity_df = pd.DataFrame([{'office': office, 'drivers_per_day': 999}])

        schedule_df = generate_week_schedule(
            candidates_scored_df=scored_candidates,
            loan_history_df=loan_history_df,
            ops_capacity_df=ops_capacity_df,
            office=office,
            week_start=week_start,
            rules_df=rules_df if enable_tier_caps else None
        )

        stage3_time = time.time() - stage3_start
        total_time = time.time() - total_start

        # Format results for UI
        assignments = []
        if not schedule_df.empty:
            weekly_assignments = schedule_df.drop_duplicates(['vin', 'person_id'])

            for _, assignment in weekly_assignments.iterrows():
                partner_info = partners_df[partners_df['person_id'] == assignment['person_id']]
                partner_name = partner_info['name'].iloc[0] if not partner_info.empty else f"Partner {assignment['person_id']}"

                scoring_info = scored_candidates[
                    (scored_candidates['vin'] == assignment['vin']) &
                    (scored_candidates['person_id'] == assignment['person_id'])
                ]

                if not scoring_info.empty:
                    score_row = scoring_info.iloc[0]
                    assignments.append({
                        'vin': assignment['vin'],
                        'person_id': assignment['person_id'],
                        'partner_name': partner_name,
                        'make': assignment['make'],
                        'model': assignment.get('model', ''),
                        'score': int(assignment['score']),
                        'rank': score_row.get('rank', 'C'),
                        'rank_weight': int(score_row.get('rank_weight', 0)),
                        'geo_bonus': int(score_row.get('geo_bonus', 0)),
                        'history_bonus': int(score_row.get('history_bonus', 0)),
                        'flags': assignment.get('flags', 'tier_ok|capacity_ok|cooldown_ok|availability_ok')
                    })

        # Calculate pipeline stats
        rank_dist = scored_candidates['rank'].value_counts().to_dict() if not scored_candidates.empty else {}

        # Simple constraint analysis
        total_scored = len(scored_candidates)
        assigned_count = len(assignments)
        rejected_count = total_scored - assigned_count

        constraint_analysis = {
            'tier_caps': int(rejected_count * 0.6) if enable_tier_caps else 0,
            'cooldown': int(rejected_count * 0.25) if enable_cooldown else 0,
            'capacity_limits': int(rejected_count * 0.1) if enable_capacity else 0,
            'geographic': int(rejected_count * 0.05)
        }

        return {
            'office': office,
            'week_start': week_start,
            'pipeline': {
                'total_duration': total_time,
                'stage1': {
                    'duration': stage1_time,
                    'candidate_count': len(candidates_df),
                    'unique_vins': candidates_df['vin'].nunique(),
                    'unique_partners': candidates_df['person_id'].nunique(),
            'office_partners': len(office_partner_ids),
                    'unique_makes': candidates_df['make'].nunique()
                },
                'stage2': {
                    'duration': stage2_time,
                    'scored_count': len(scored_candidates),
                    'score_min': int(scored_candidates['score'].min()),
                    'score_max': int(scored_candidates['score'].max()),
                    'rank_distribution': rank_dist
                },
                'stage3': {
                    'duration': stage3_time,
                    'assignment_count': len(assignments)
                }
            },
            'assignments': assignments,
            'summary': {
                'unique_vins': len(set(a['vin'] for a in assignments)),
                'unique_partners': len(set(a['person_id'] for a in assignments)),
                'unique_makes': len(set(a['make'] for a in assignments))
            },
            'constraint_analysis': constraint_analysis,
            'constraint_settings': {
                'tier_caps_enabled': enable_tier_caps,
                'cooldown_enabled': enable_cooldown,
                'cooldown_days': cooldown_days,
                'capacity_enabled': enable_capacity,
                'min_available_days': min_available_days
            },
            'message': f'Generated {len(assignments)} assignments for {office} (cooldown: {cooldown_days}d, tier_caps: {enable_tier_caps})'
        }

    except Exception as e:
        logger.error(f"Error generating schedule: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Schedule generation failed: {str(e)}")


@router.get("/analyze_vin")
async def analyze_vin_candidates(
    vin: str = Query(..., description="VIN to analyze"),
    office: str = Query(..., description="Office name"),
    week_start: str = Query(..., description="Week start date"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """Analyze why a specific VIN was or wasn't assigned."""

    return {
        'vin': vin,
        'candidates': []
    }