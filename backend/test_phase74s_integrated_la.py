"""
Full Integration Test for LA - September 22, 2025

Complete pipeline test with soft tier caps:
7.1 (Feasible) → 7.3 (Cooldown) → 7.2+7.4s (OR-Tools with soft caps)

Tests with real LA data for the week of Sept 22-26, 2025.
"""

import asyncio
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.solver.cooldown_filter import apply_cooldown_filter
from app.solver.ortools_solver_v2 import add_score_to_triples
from app.solver.ortools_solver_v4 import solve_with_soft_caps
from app.etl.availability import build_availability_grid


async def test_la_september_22():
    """Full integration test for LA week of Sept 22, 2025."""

    print("="*80)
    print("FULL INTEGRATION TEST: LA SEPTEMBER 22-26, 2025")
    print("Pipeline: 7.1 → 7.3 → 7.2+7.4s (with SOFT tier caps)")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'
    lambda_cap = 800  # Default penalty weight

    print(f"\n📍 Office: {office}")
    print(f"📅 Week: {week_start} (Monday)")
    print(f"⚖️ Lambda (cap penalty): {lambda_cap}")

    try:
        # =============================
        # PHASE 7.1: FEASIBLE TRIPLES
        # =============================
        print("\n" + "="*60)
        print("PHASE 7.1: GENERATING FEASIBLE TRIPLES")
        print("="*60)

        # Load vehicles
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"✓ {len(vehicles_df)} vehicles in {office}")

        # Load partners
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)
        print(f"✓ {len(partners_df)} media partners in {office}")

        # Load approved makes with pagination
        print("Loading approved makes...")
        all_approved = []
        limit = 1000
        offset = 0
        while True:
            approved_response = db.client.table('approved_makes').select('*').range(offset, offset + limit - 1).execute()
            if not approved_response.data:
                break
            all_approved.extend(approved_response.data)
            offset += limit
            if len(approved_response.data) < limit:
                break

        approved_df = pd.DataFrame(all_approved)
        la_partner_ids = set(partners_df['person_id'].tolist())
        approved_la = approved_df[approved_df['person_id'].isin(la_partner_ids)]
        print(f"✓ {len(approved_la)} approved make-partner pairs for LA")

        # Build availability
        activity_response = db.client.table('current_activity').select('*').execute()
        activity_df = pd.DataFrame(activity_response.data)
        if 'vehicle_vin' in activity_df.columns:
            activity_df = activity_df.rename(columns={'vehicle_vin': 'vin'})

        availability_df = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=office,
            availability_horizon_days=14
        )
        availability_df = availability_df.rename(columns={'day': 'date'})

        # Load capacity and taxonomy
        ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_calendar_df = pd.DataFrame(ops_cal_response.data)

        taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
        taxonomy_df = pd.DataFrame(taxonomy_response.data)

        # Generate feasible triples
        triples_71 = build_feasible_start_day_triples(
            vehicles_df=vehicles_df,
            partners_df=partners_df,
            availability_df=availability_df,
            approved_makes_df=approved_la,
            week_start=week_start,
            office=office,
            ops_capacity_df=ops_calendar_df,
            model_taxonomy_df=taxonomy_df,
            start_days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            min_available_days=7,
            default_slots_per_day=15
        )

        print(f"\n📊 Phase 7.1 Results:")
        print(f"   Feasible triples: {len(triples_71):,}")
        print(f"   Unique VINs: {triples_71['vin'].nunique()}")
        print(f"   Unique partners: {triples_71['person_id'].nunique()}")
        print(f"   Unique makes: {triples_71['make'].nunique()}")

        # =============================
        # PHASE 7.3: COOLDOWN FILTER
        # =============================
        print("\n" + "="*60)
        print("PHASE 7.3: COOLDOWN FILTER (HARD CONSTRAINT)")
        print("="*60)

        # Load loan history with pagination
        print("Loading loan history...")
        all_loan_history = []
        limit = 1000
        offset = 0

        while True:
            history_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
            if not history_response.data:
                break
            all_loan_history.extend(history_response.data)
            if len(all_loan_history) % 5000 == 0:
                print(f"   Loaded {len(all_loan_history)} records...")
            offset += limit
            if len(history_response.data) < limit:
                break

        loan_history_df = pd.DataFrame(all_loan_history)
        print(f"✓ Loaded {len(loan_history_df)} total loan history records")

        # Filter to LA only
        if not loan_history_df.empty and 'office' in loan_history_df.columns:
            loan_history_df = loan_history_df[loan_history_df['office'] == 'Los Angeles'].copy()
            print(f"✓ Filtered to {len(loan_history_df)} LA loans")

            # Analyze recent loans
            if 'end_date' in loan_history_df.columns:
                loan_history_df['end_date'] = pd.to_datetime(loan_history_df['end_date'])
                cooldown_cutoff = pd.Timestamp('2025-08-23')  # 30 days before Sept 22
                recent_loans = loan_history_df[loan_history_df['end_date'] > cooldown_cutoff]
                print(f"✓ {len(recent_loans)} loans within 30-day cooldown window")
                print(f"✓ {recent_loans['person_id'].nunique()} partners with recent loans")

        # Load cooldown rules
        try:
            rules_response = db.client.table('rules').select('*').execute()
            rules_df = pd.DataFrame(rules_response.data)
            print(f"✓ Loaded {len(rules_df)} cooldown/cap rules")
        except:
            rules_df = pd.DataFrame()
            print("⚠️ No rules table found")

        # Apply cooldown filter
        triples_73 = apply_cooldown_filter(
            feasible_triples_df=triples_71,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            model_taxonomy_df=taxonomy_df,
            default_cooldown_days=30
        )

        print(f"\n📊 Phase 7.3 Results:")
        print(f"   Post-cooldown triples: {len(triples_73):,}")
        print(f"   Removed by cooldown: {len(triples_71) - len(triples_73):,}")
        print(f"   Reduction: {(1 - len(triples_73)/len(triples_71))*100:.1f}%")

        # Add scores
        print("\nAdding scores to triples...")
        triples_with_scores = add_score_to_triples(
            triples_df=triples_73,
            partners_df=partners_df,
            publication_df=pd.DataFrame(),
            seed=42
        )
        print(f"✓ Score range: {triples_with_scores['score'].min()} - {triples_with_scores['score'].max()}")

        # ========================================
        # PHASE 7.2 + 7.4s: OR-TOOLS WITH SOFT CAPS
        # ========================================
        print("\n" + "="*60)
        print("PHASE 7.2 + 7.4s: OR-TOOLS WITH SOFT TIER CAPS")
        print("="*60)

        result = solve_with_soft_caps(
            triples_df=triples_with_scores,
            ops_capacity_df=ops_calendar_df,
            approved_makes_df=approved_la,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            week_start=week_start,
            office=office,
            loan_length_days=7,
            solver_time_limit_s=10,
            lambda_cap=lambda_cap,
            rolling_window_months=12,
            seed=42
        )

        # =============================
        # FINAL RESULTS
        # =============================
        print("\n" + "="*80)
        print("🎯 FINAL RESULTS: LA WEEK OF SEPT 22-26, 2025")
        print("="*80)

        print(f"\n📈 Pipeline Summary:")
        print(f"   Phase 7.1: {len(triples_71):,} feasible triples")
        print(f"   Phase 7.3: {len(triples_73):,} after cooldown (-{len(triples_71) - len(triples_73):,})")
        print(f"   Phase 7.2+7.4s: {len(result['selected_assignments'])} assignments selected")

        print(f"\n🧮 Optimization Results:")
        print(f"   Solver status: {result['meta']['solver_status']}")
        print(f"   Total score: {result.get('total_score', 0):,}")
        print(f"   Cap penalties: {result.get('total_cap_penalty', 0):,}")
        print(f"   Net objective: {result.get('net_objective', 0):,}")
        print(f"   Solve time: {result['timing']['wall_ms']}ms")

        # Daily distribution
        if result['selected_assignments']:
            print(f"\n📅 Daily Distribution:")
            day_counts = {}
            for assignment in result['selected_assignments']:
                day = pd.to_datetime(assignment['start_day']).strftime('%A')
                day_counts[day] = day_counts.get(day, 0) + 1

            total_capacity = 0
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                count = day_counts.get(day, 0)
                print(f"   {day}: {count}/15")
                total_capacity += 15

            utilization = len(result['selected_assignments'])/total_capacity*100
            print(f"\n   Capacity utilization: {len(result['selected_assignments'])}/{total_capacity} ({utilization:.1f}%)")

        # Cap summary
        cap_summary = result.get('cap_summary', pd.DataFrame())
        if not cap_summary.empty:
            print(f"\n🎯 Tier Cap Analysis:")

            # Partners exceeding caps
            with_penalty = cap_summary[cap_summary['penalty'] > 0]
            if not with_penalty.empty:
                print(f"   Partners exceeding caps: {len(with_penalty)}")
                print(f"\n   Top cap violations:")
                for _, row in with_penalty.head(5).iterrows():
                    print(f"     {row['person_id']} + {row['make']}: "
                          f"+{row['delta_overage']} over (penalty={row['penalty']})")
            else:
                print(f"   ✓ All assignments within caps (no penalties)")

            # Cap distribution
            print(f"\n   Cap utilization by tier:")
            if 'cap' in cap_summary.columns:
                cap_groups = cap_summary.groupby('cap').agg({
                    'person_id': 'count',
                    'assigned_this_week': 'sum',
                    'penalty': 'sum'
                }).rename(columns={'person_id': 'pairs'})

                for cap, data in cap_groups.iterrows():
                    cap_str = str(cap) if cap != 'Unlimited' else 'Unlimited'
                    print(f"     Cap {cap_str}: {int(data['pairs'])} pairs, "
                          f"{int(data['assigned_this_week'])} assigned, "
                          f"penalty={int(data['penalty'])}")

        # Make distribution
        print(f"\n🚗 Top Makes Assigned:")
        make_counts = {}
        for assignment in result['selected_assignments']:
            make = assignment['make']
            make_counts[make] = make_counts.get(make, 0) + 1

        for make, count in sorted(make_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   {make}: {count}")

        # Rank distribution
        print(f"\n⭐ Assignments by Rank:")
        rank_counts = {}
        for assignment in result['selected_assignments']:
            # Get rank from approved makes
            person_id = assignment['person_id']
            make = assignment['make']
            rank_match = approved_la[
                (approved_la['person_id'] == person_id) &
                (approved_la['make'] == make)
            ]
            if not rank_match.empty:
                rank = rank_match.iloc[0].get('rank', 'Unknown')
                rank_counts[rank] = rank_counts.get(rank, 0) + 1

        for rank in ['A+', 'A', 'B', 'C']:
            count = rank_counts.get(rank, 0)
            print(f"   Rank {rank}: {count}")

        # =============================
        # VALIDATION CHECKS
        # =============================
        print("\n" + "="*60)
        print("✅ VALIDATION CHECKS")
        print("="*60)

        # VIN uniqueness
        if result['selected_assignments']:
            vins = [a['vin'] for a in result['selected_assignments']]
            unique_vins = len(set(vins))
            if unique_vins == len(vins):
                print("✓ VIN uniqueness: PASS (no duplicates)")
            else:
                print(f"❌ VIN uniqueness: FAIL ({len(vins) - unique_vins} duplicates)")

        # Capacity compliance
        capacity_ok = all(d['used'] <= d['capacity'] for d in result['daily_usage'])
        if capacity_ok:
            print("✓ Daily capacity: PASS (all within limits)")
        else:
            print("❌ Daily capacity: FAIL (some days over capacity)")

        # Soft cap behavior
        if result.get('total_cap_penalty', 0) > 0:
            print(f"✓ Soft caps: Working ({result['total_cap_penalty']} total penalty)")
        else:
            print("✓ Soft caps: No penalties (all within caps or unlimited)")

        print("\n🎉 Integration test complete!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("END OF INTEGRATION TEST")
    print("="*80)


if __name__ == "__main__":
    print("Running full integration test for LA - Sept 22, 2025...")
    asyncio.run(test_la_september_22())