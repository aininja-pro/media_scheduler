"""
Guardrail test for Phase 7.3: Ensures cooldown is enforced.

This test MUST fail if the solver ever produces an assignment that
violates cooldown constraints. This prevents regressions where we
accidentally allow cooldown violations through.
"""

import asyncio
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples
from app.solver.cooldown_filter import apply_cooldown_filter, check_cooldown, build_cooldown_ledger, get_cooldown_days
from app.solver.ortools_solver_v2 import solve_core_assignment, add_score_to_triples
from app.etl.availability import build_availability_grid


async def test_guardrail():
    """Guardrail test: Verify no cooldown violations can slip through."""

    print("="*80)
    print("PHASE 7.3 GUARDRAIL TEST")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'

    try:
        # Load all data
        print("\n1. Loading data...")
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)

        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)

        # Approved makes
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

        # Load loan history
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
        if not loan_history_df.empty and 'office' in loan_history_df.columns:
            loan_history_df = loan_history_df[loan_history_df['office'] == 'Los Angeles'].copy()

        # Load rules
        try:
            rules_response = db.client.table('rules').select('*').execute()
            rules_df = pd.DataFrame(rules_response.data)
        except:
            rules_df = pd.DataFrame()

        # Load taxonomy
        taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
        taxonomy_df = pd.DataFrame(taxonomy_response.data)

        ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
        ops_calendar_df = pd.DataFrame(ops_cal_response.data)

        # === TEST 1: Verify pipeline order ===
        print("\n2. Testing correct pipeline order (7.1 → 7.3 → 7.2)...")

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
        print(f"   Phase 7.1: {len(triples_71)} triples")

        # Apply cooldown filter
        triples_73 = apply_cooldown_filter(
            feasible_triples_df=triples_71,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            model_taxonomy_df=taxonomy_df,
            default_cooldown_days=30
        )
        print(f"   Phase 7.3: {len(triples_73)} triples ({len(triples_71) - len(triples_73)} removed)")

        # Verify all triples have cooldown_ok=True
        assert all(triples_73['cooldown_ok'] == True), "FAIL: Found cooldown_ok=False!"
        print("   ✓ All triples have cooldown_ok=True")

        # Run solver
        triples_with_scores = add_score_to_triples(
            triples_df=triples_73,
            partners_df=partners_df,
            publication_df=pd.DataFrame(),
            seed=42
        )

        result = solve_core_assignment(
            triples_df=triples_with_scores,
            ops_capacity_df=ops_calendar_df,
            week_start=week_start,
            office=office,
            loan_length_days=7,
            solver_time_limit_s=10,
            seed=42
        )
        print(f"   Phase 7.2: {len(result['selected_assignments'])} assignments")

        # === TEST 2: Double-check selected assignments ===
        print("\n3. Verifying selected assignments against cooldown...")

        # Build cooldown ledger
        ledger = build_cooldown_ledger(loan_history_df, taxonomy_df)

        violations = []
        for assignment in result['selected_assignments']:
            make = assignment['make']
            cooldown_days = get_cooldown_days(make, rules_df, 30)

            # Check cooldown
            ok, basis, until = check_cooldown(
                pd.Series(assignment),
                ledger,
                cooldown_days
            )

            if not ok:
                violations.append({
                    'person_id': assignment['person_id'],
                    'make': make,
                    'model': assignment.get('model'),
                    'start_day': assignment['start_day'],
                    'basis': basis,
                    'cooldown_until': until
                })

        if violations:
            print(f"\n❌ GUARDRAIL FAILED: Found {len(violations)} cooldown violations!")
            print("\nViolations:")
            for v in violations[:5]:  # Show first 5
                print(f"  {v['person_id']}: {v['make']} {v['model']} on {v['start_day']}")
                print(f"    Cooldown until {v['cooldown_until']} (basis: {v['basis']})")

            raise AssertionError(f"Guardrail failed: {len(violations)} assignments violate cooldown!")
        else:
            print("   ✓ All selected assignments pass cooldown check")

        # === TEST 3: Verify cooldown fields present ===
        print("\n4. Verifying cooldown metadata...")

        required_fields = ['cooldown_ok', 'cooldown_basis', 'cooldown_until']
        missing = [f for f in required_fields if f not in triples_73.columns]

        if missing:
            print(f"   ❌ Missing fields: {missing}")
            raise AssertionError(f"Missing cooldown fields: {missing}")
        else:
            print(f"   ✓ All cooldown fields present")

        # === SUMMARY ===
        print("\n" + "="*80)
        print("GUARDRAIL TEST RESULTS")
        print("="*80)
        print("\n✅ ALL GUARDRAILS PASSED:")
        print("  1. Pipeline order correct (7.1 → 7.3 → 7.2)")
        print("  2. Solver only receives cooldown_ok=True triples")
        print("  3. No assignments violate cooldown")
        print("  4. Cooldown metadata attached")
        print("\n🛡️ System is protected against cooldown violations")

    except AssertionError as e:
        print(f"\n🚨 {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        await db.close()

    print("\n" + "="*80)
    print("GUARDRAIL TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    print("Running Phase 7.3 guardrail test...")
    asyncio.run(test_guardrail())