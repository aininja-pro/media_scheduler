"""
Diagnose why only 2 assignments are being made regardless of week.
This script traces through the entire pipeline to find the bottleneck.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from app.services.database import db_service
from app.etl.availability import build_availability_grid
from app.etl.cooldown import compute_cooldown_flags
from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores
from app.solver.greedy_assign import generate_week_schedule
import time


async def diagnose_two_assignments():
    """Trace through the entire pipeline to find why only 2 assignments."""

    await db_service.initialize()

    office = 'Los Angeles'
    test_weeks = [
        '2024-09-16',  # September
        '2024-10-14',  # October
        '2024-11-11',  # November
    ]

    print(f"\n{'='*80}")
    print(f"DIAGNOSING WHY ONLY 2 ASSIGNMENTS ARE MADE")
    print(f"{'='*80}\n")

    for week_start in test_weeks:
        print(f"\n{'='*60}")
        print(f"ANALYZING WEEK: {week_start}")
        print(f"{'='*60}\n")

        # Load data
        vehicles_response = db_service.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

        activity_response = db_service.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data) if activity_response.data else pd.DataFrame()

        if 'vehicle_vin' in activity_df.columns:
            activity_df['vin'] = activity_df['vehicle_vin']

        # Get office partners
        office_partners_response = db_service.client.table('media_partners').select('person_id').eq('office', office).execute()
        office_partner_ids = set([p['person_id'] for p in office_partners_response.data])

        # Get approved makes for office partners
        all_approved = []
        limit = 1000
        offset = 0
        while True:
            approved_response = db_service.client.table('approved_makes').select('person_id, make, rank').range(offset, offset + limit - 1).execute()
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

        print(f"1. DATA LOADED:")
        print(f"   - Total vehicles in {office}: {len(vehicles_df)}")
        print(f"   - Total partners in {office}: {len(office_partner_ids)}")
        print(f"   - Current activities: {len(activity_df)}")
        print(f"   - Loan history records: {len(loan_history_df)}")

        # Step 1: Build availability
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

        # Count available vehicles
        vins_available = set()
        for vin in availability_df['vin'].unique():
            vin_data = availability_df[availability_df['vin'] == vin]
            days_available = vin_data[vin_data['available'] == True]['date'].nunique()
            if days_available >= 5:
                vins_available.add(vin)

        print(f"\n2. AVAILABILITY ANALYSIS:")
        print(f"   - Vehicles available ≥5 days: {len(vins_available)}")
        if len(vins_available) > 0:
            sample_vins = list(vins_available)[:3]
            for vin in sample_vins:
                make = vehicles_df[vehicles_df['vin'] == vin]['make'].iloc[0] if not vehicles_df[vehicles_df['vin'] == vin].empty else 'Unknown'
                print(f"     • {vin[-8:]} ({make})")

        # Step 2: Compute cooldown
        cooldown_df = compute_cooldown_flags(
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            week_start=week_start,
            default_days=30
        )

        print(f"\n3. COOLDOWN ANALYSIS:")
        print(f"   - Total cooldown records: {len(cooldown_df)}")
        cooldown_blocked = cooldown_df[cooldown_df['cooldown_ok'] == False]
        print(f"   - Partner-make combos in cooldown: {len(cooldown_blocked)}")

        # Step 3: Build candidates
        office_vehicle_makes = set(vehicles_df['make'].unique())
        office_approved = approved_makes_df[approved_makes_df['make'].isin(office_vehicle_makes)]

        # Include partners without approvals
        partners_with_approvals = set(office_approved['person_id'].unique())
        partners_without_approvals = office_partner_ids - partners_with_approvals

        publication_records = [
            {'person_id': pid, 'make': make, 'rank': rank, 'publication_rate_observed': None, 'supported': False, 'coverage': 0.0}
            for pid, make, rank in office_approved[['person_id', 'make', 'rank']].drop_duplicates().values
        ]

        # Add partners WITHOUT approved_makes
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

        print(f"\n4. CANDIDATE GENERATION:")
        print(f"   - Feasible candidates: {len(candidates_df)}")
        if not candidates_df.empty:
            print(f"   - Unique VINs: {candidates_df['vin'].nunique()}")
            print(f"   - Unique partners: {candidates_df['person_id'].nunique()}")
            print(f"   - Unique makes: {candidates_df['make'].nunique()}")

            # Show sample candidates
            print(f"\n   Sample candidates:")
            for _, row in candidates_df.head(5).iterrows():
                print(f"     • VIN {row['vin'][-8:]} + Partner {row['person_id']} ({row['make']})")

        # Step 4: Score candidates
        if not candidates_df.empty:
            scored_candidates = compute_candidate_scores(
                candidates_df=candidates_df,
                partner_rank_df=eligibility_df,
                partners_df=partners_df,
                publication_df=publication_df
            )

            print(f"\n5. SCORING:")
            print(f"   - Scored candidates: {len(scored_candidates)}")
            if not scored_candidates.empty:
                print(f"   - Score range: {scored_candidates['score'].min()} to {scored_candidates['score'].max()}")

                # Show score distribution
                score_counts = scored_candidates['score'].value_counts().sort_index()
                print(f"\n   Score distribution:")
                for score, count in score_counts.head(5).items():
                    print(f"     Score {score}: {count} candidates")

        # Step 5: Greedy assignment
        if not candidates_df.empty and not scored_candidates.empty:
            # Load ops capacity
            ops_capacity_response = db_service.client.table('ops_capacity').select('*').execute()
            ops_capacity_df = pd.DataFrame(ops_capacity_response.data) if ops_capacity_response.data else pd.DataFrame()

            assignments = generate_week_schedule(
                candidates_scored_df=scored_candidates,
                loan_history_df=loan_history_df,
                ops_capacity_df=ops_capacity_df,
                office=office,
                week_start=week_start,
                rank_caps=None,
                rules_df=rules_df
            )

            print(f"\n6. FINAL ASSIGNMENTS:")
            print(f"   - Total assignments: {len(assignments)}")

            if not assignments.empty:
                print(f"\n   Assignments made:")
                for _, assignment in assignments.iterrows():
                    print(f"     • VIN {assignment['vin'][-8:]} → Partner {assignment['person_id']} ({assignment['make']}) Score: {assignment['score']}")

                # Analyze why more assignments weren't made
                print(f"\n7. CONSTRAINT BOTTLENECKS:")

                # Check tier caps
                used_tier_caps = {}
                for _, assignment in assignments.iterrows():
                    key = (assignment['person_id'], assignment['make'])
                    used_tier_caps[key] = used_tier_caps.get(key, 0) + 1

                # Check daily capacity
                daily_assignments = assignments.groupby('date').size() if 'date' in assignments.columns else pd.Series()

                print(f"   - Tier cap usage: {len(used_tier_caps)} partner-make combos used")
                print(f"   - Daily capacity usage: {daily_assignments.max() if not daily_assignments.empty else 0}/10")

                # Find candidates that weren't assigned
                if not scored_candidates.empty:
                    assigned_vins = set(assignments['vin'])
                    unassigned_candidates = scored_candidates[~scored_candidates['vin'].isin(assigned_vins)]

                    print(f"   - Unassigned candidates: {len(unassigned_candidates)}")

                    # Sample reasons for non-assignment
                    if not unassigned_candidates.empty:
                        print(f"\n   Sample unassigned candidates (top scores):")
                        for _, cand in unassigned_candidates.nlargest(5, 'score').iterrows():
                            print(f"     • VIN {cand['vin'][-8:]} + Partner {cand['person_id']} (Score: {cand['score']})")

    await db_service.close()
    print(f"\n✅ Diagnosis complete")


if __name__ == "__main__":
    asyncio.run(diagnose_two_assignments())