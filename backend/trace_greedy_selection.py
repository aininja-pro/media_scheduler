"""
Trace the greedy selection process to see why only 2 partners get chosen.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from app.services.database import db_service
from app.etl.availability import build_availability_grid
from app.etl.cooldown import compute_cooldown_flags
from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores


async def trace_greedy_selection():
    """Trace exactly how the greedy algorithm picks assignments."""

    await db_service.initialize()

    office = 'Los Angeles'
    week_start = '2024-09-16'

    print(f"\n{'='*80}")
    print(f"TRACING GREEDY SELECTION PROCESS")
    print(f"{'='*80}\n")

    # Load all data (same as before)
    vehicles_response = db_service.client.table('vehicles').select('*').eq('office', office).execute()
    vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

    activity_response = db_service.client.table('current_activity').select('*').execute()
    activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

    if 'vehicle_vin' in activity_df.columns:
        activity_df['vin'] = activity_df['vehicle_vin']

    office_partners_response = db_service.client.table('media_partners').select('person_id').eq('office', office).execute()
    office_partner_ids = set([p['person_id'] for p in office_partners_response.data])

    all_approved = []
    limit = 1000
    offset = 0
    while True:
        approved_response = db_service.client.table('approved_makes').select('*').range(offset, offset + limit - 1).execute()
        if not approved_response.data:
            break
        all_approved.extend(approved_response.data)
        offset += limit
        if len(approved_response.data) < limit:
            break

    approved_makes_df = pd.DataFrame(all_approved)
    approved_makes_df = approved_makes_df[approved_makes_df['person_id'].isin(office_partner_ids)]

    loan_history_response = db_service.client.table('loan_history').select('*').execute()
    loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    partners_response = db_service.client.table('media_partners').select('*').execute()
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

    # Build availability
    availability_grid = build_availability_grid(
        vehicles_df=vehicles_df,
        activity_df=activity_df,
        week_start=week_start,
        office=office
    )

    # Convert to candidate format
    availability_records = []
    if not availability_grid.empty:
        vehicle_lookup = vehicles_df.set_index('vin')[['make', 'model']].to_dict('index')

        for _, row in availability_grid.iterrows():
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

    # Compute cooldown
    cooldown_df = compute_cooldown_flags(
        loan_history_df=loan_history_df,
        rules_df=rules_df,
        week_start=week_start,
        default_days=30
    )

    # Build candidates
    office_vehicle_makes = set(vehicles_df['make'].unique())
    office_approved = approved_makes_df[approved_makes_df['make'].isin(office_vehicle_makes)]

    partners_with_approvals = set(office_approved['person_id'].unique())
    partners_without_approvals = office_partner_ids - partners_with_approvals

    publication_records = [
        {'person_id': pid, 'make': make, 'rank': rank, 'publication_rate_observed': None, 'supported': False, 'coverage': 0.0}
        for pid, make, rank in office_approved[['person_id', 'make', 'rank']].drop_duplicates().values
    ]

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

    candidates_df = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start=week_start,
        eligibility_df=eligibility_df,
        min_available_days=5
    )

    # Score candidates
    scored_candidates = compute_candidate_scores(
        candidates_df=candidates_df,
        partner_rank_df=eligibility_df,
        partners_df=partners_df,
        publication_df=publication_df
    )

    print("1. SCORED CANDIDATES ANALYSIS:")
    print(f"   Total scored candidates: {len(scored_candidates)}")

    # Group by score and show top partners for each score level
    score_groups = scored_candidates.groupby('score')
    for score in sorted(score_groups.groups.keys(), reverse=True)[:3]:
        group = score_groups.get_group(score)
        partner_counts = group.groupby('person_id').size().sort_values(ascending=False)

        print(f"\n   Score {score}: {len(group)} candidates")
        print(f"   Partners at this score level:")
        for partner_id, count in partner_counts.head(10).items():
            partner_name = partners_df[partners_df['person_id'] == partner_id]['name'].iloc[0] if not partners_df[partners_df['person_id'] == partner_id].empty else f"Partner {partner_id}"
            makes = group[group['person_id'] == partner_id]['make'].unique()
            print(f"     - {partner_name} (ID: {partner_id}): {count} candidates for {', '.join(makes)}")

    # Analyze why certain partners dominate
    print(f"\n2. ANALYZING TOP-SCORING CANDIDATES:")

    top_candidates = scored_candidates[scored_candidates['score'] == scored_candidates['score'].max()]
    print(f"   Candidates with maximum score ({scored_candidates['score'].max()}): {len(top_candidates)}")

    # Check unique partners at max score
    top_partners = top_candidates['person_id'].unique()
    print(f"   Unique partners at max score: {len(top_partners)}")
    print(f"   Partner IDs: {list(top_partners)[:10]}...")

    # Check if these partners are in cooldown
    print(f"\n3. COOLDOWN ANALYSIS FOR TOP PARTNERS:")
    for partner_id in top_partners[:5]:
        partner_name = partners_df[partners_df['person_id'] == partner_id]['name'].iloc[0] if not partners_df[partners_df['person_id'] == partner_id].empty else f"Partner {partner_id}"

        # Check cooldown
        partner_cooldowns = cooldown_df[cooldown_df['person_id'] == partner_id]
        blocked_makes = partner_cooldowns[partner_cooldowns['cooldown_ok'] == False]['make'].unique() if not partner_cooldowns.empty else []

        print(f"\n   {partner_name} (ID: {partner_id}):")
        if len(blocked_makes) > 0:
            print(f"     Blocked for makes: {', '.join(blocked_makes)}")
        else:
            print(f"     No cooldown restrictions")

        # Check their candidates
        partner_candidates = top_candidates[top_candidates['person_id'] == partner_id]
        makes_available = partner_candidates['make'].unique()
        print(f"     Can be assigned: {', '.join(makes_available)}")

    # Simulate greedy selection
    print(f"\n4. SIMULATING GREEDY SELECTION:")
    print("   (Greedy picks highest score first, assigns to first partner in list)")

    # Sort by score descending, then by person_id (this is what causes the bias!)
    sorted_candidates = scored_candidates.sort_values(['score', 'person_id'], ascending=[False, True])

    assigned_vins = set()
    assignments_by_partner = {}

    for _, candidate in sorted_candidates.iterrows():
        if candidate['vin'] not in assigned_vins:
            partner_id = candidate['person_id']
            if partner_id not in assignments_by_partner:
                assignments_by_partner[partner_id] = []
            assignments_by_partner[partner_id].append(candidate['vin'])
            assigned_vins.add(candidate['vin'])

            if len(assigned_vins) >= 10:  # Just show first 10 assignments
                break

    print("\n   First 10 assignments by greedy algorithm:")
    for partner_id, vins in assignments_by_partner.items():
        partner_name = partners_df[partners_df['person_id'] == partner_id]['name'].iloc[0] if not partners_df[partners_df['person_id'] == partner_id].empty else f"Partner {partner_id}"
        print(f"     {partner_name} (ID: {partner_id}): {len(vins)} vehicles")

    # The real issue: Check the ordering
    print(f"\n5. THE ORDERING ISSUE:")
    print("   When multiple partners have score 110, the selection order is:")
    top_110 = scored_candidates[scored_candidates['score'] == 110].sort_values('person_id')
    partner_order = top_110['person_id'].unique()[:10]
    for i, pid in enumerate(partner_order, 1):
        partner_name = partners_df[partners_df['person_id'] == pid]['name'].iloc[0] if not partners_df[partners_df['person_id'] == pid].empty else f"Partner {pid}"
        print(f"     {i}. {partner_name} (ID: {pid})")

    await db_service.close()
    print(f"\n✅ Trace complete")


if __name__ == "__main__":
    asyncio.run(trace_greedy_selection())