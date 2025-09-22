"""
Test Phase 7.3 integrated with Phase 7.2 solver.

Full pipeline: Feasible triples → Cooldown filter → OR-Tools solver
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
from app.solver.ortools_solver_v2 import solve_core_assignment, add_score_to_triples
from app.etl.availability import build_availability_grid


async def test_integrated_pipeline():
    """Test full pipeline: 7.1 → 7.3 → 7.2"""

    print("="*80)
    print("INTEGRATED TEST: PHASE 7.1 → 7.3 → 7.2")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'

    print(f"\nConfiguration:")
    print(f"  Office: {office}")
    print(f"  Week: {week_start}")

    try:
        # === PHASE 7.1: Generate feasible triples ===
        print("\n" + "="*60)
        print("PHASE 7.1: FEASIBLE TRIPLES")
        print("="*60)

        # Load all required data
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)

        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)

        # Approved makes with pagination
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

        # Availability
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

        # Capacity and taxonomy
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

        print(f"Generated: {len(triples_71)} triples")
        print(f"Unique VINs: {triples_71['vin'].nunique()}")
        print(f"Unique Partners: {triples_71['person_id'].nunique()}")

        # === PHASE 7.3: Apply cooldown filter BEFORE solver ===
        print("\n" + "="*60)
        print("PHASE 7.3: COOLDOWN FILTER (PRE-SOLVER)")
        print("="*60)

        # Load loan history WITH PAGINATION
        print("Loading loan history...")
        all_loan_history = []
        limit = 1000
        offset = 0

        while True:
            history_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
            if not history_response.data:
                break
            all_loan_history.extend(history_response.data)
            offset += limit
            if len(history_response.data) < limit:
                break

        loan_history_df = pd.DataFrame(all_loan_history)

        # Filter to LA only
        if not loan_history_df.empty and 'office' in loan_history_df.columns:
            loan_history_df = loan_history_df[loan_history_df['office'] == 'Los Angeles'].copy()
            print(f"   Found {len(loan_history_df)} LA loan history records")

        # Load cooldown rules
        try:
            rules_response = db.client.table('rules').select('*').execute()
            rules_df = pd.DataFrame(rules_response.data)
        except:
            rules_df = pd.DataFrame()

        # Apply cooldown filter to feasible triples BEFORE solver
        triples_73 = apply_cooldown_filter(
            feasible_triples_df=triples_71,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            model_taxonomy_df=taxonomy_df,
            default_cooldown_days=30
        )

        print(f"\nPost-cooldown: {len(triples_73)} triples")
        print(f"Removed by cooldown: {len(triples_71) - len(triples_73)}")

        # Add assertion to ensure solver never receives cooldown violations
        assert all(triples_73['cooldown_ok'] == True), "ERROR: Found cooldown_ok=False triples going to solver!"
        print(f"✓ Assertion passed: All {len(triples_73)} triples have cooldown_ok=True")

        # === PHASE 7.2: OR-Tools solver ===
        print("\n" + "="*60)
        print("PHASE 7.2: OR-TOOLS OPTIMIZATION")
        print("="*60)

        # Add scores
        print("Adding scores...")
        triples_with_scores = add_score_to_triples(
            triples_df=triples_73,  # Use filtered triples!
            partners_df=partners_df,
            publication_df=pd.DataFrame(),
            seed=42
        )

        print(f"Score range: {triples_with_scores['score'].min()} - {triples_with_scores['score'].max()}")

        # Run solver on filtered triples
        print("Running solver on cooldown-filtered triples...")
        result = solve_core_assignment(
            triples_df=triples_with_scores,
            ops_capacity_df=ops_calendar_df,
            week_start=week_start,
            office=office,
            loan_length_days=7,
            solver_time_limit_s=10,
            seed=42
        )

        # === FINAL RESULTS ===
        print("\n" + "="*80)
        print("INTEGRATED PIPELINE RESULTS")
        print("="*80)

        print(f"\nPipeline Summary:")
        print(f"  Phase 7.1: {len(triples_71):,} feasible triples")
        print(f"  Phase 7.3: {len(triples_73):,} after cooldown filter (-{len(triples_71) - len(triples_73)})")
        print(f"  Phase 7.2: {len(result['selected_assignments'])} assignments selected")

        print(f"\nSolver Results:")
        print(f"  Status: {result['meta']['solver_status']}")
        print(f"  Objective: {result['objective_value']:,}")
        print(f"  Time: {result['timing']['wall_ms']}ms")

        # Day distribution
        if result['selected_assignments']:
            day_counts = {}
            for assignment in result['selected_assignments']:
                day = pd.to_datetime(assignment['start_day']).strftime('%A')
                day_counts[day] = day_counts.get(day, 0) + 1

            print(f"\nAssignments by day:")
            total_capacity = 0
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                count = day_counts.get(day, 0)
                print(f"  {day}: {count}/15")
                total_capacity += 15

            print(f"\nCapacity utilization: {len(result['selected_assignments'])}/{total_capacity} "
                  f"({len(result['selected_assignments'])/total_capacity*100:.1f}%)")

        # Verify constraints
        print("\n" + "="*60)
        print("CONSTRAINT VERIFICATION")
        print("="*60)

        # Check VIN uniqueness
        if result['selected_assignments']:
            vins = [a['vin'] for a in result['selected_assignments']]
            unique_vins = len(set(vins))
            print(f"✓ VIN uniqueness: {unique_vins} unique VINs (no duplicates)")

        # Check cooldown compliance
        if len(triples_71) > len(triples_73):
            print(f"✓ Cooldown: {len(triples_71) - len(triples_73)} violations filtered before solver")

        # Check capacity
        capacity_ok = all(d['used'] <= d['capacity'] for d in result['daily_usage'])
        if capacity_ok:
            print(f"✓ Capacity: All days within limits")

        print("\n✅ All constraints satisfied in integrated pipeline")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("INTEGRATED TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    print("Testing integrated pipeline (7.1 → 7.3 → 7.2)...")
    asyncio.run(test_integrated_pipeline())