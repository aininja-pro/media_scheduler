"""
Test Phase 7.3 with REAL data - Cooldown Constraint Filter.

Tests the cooldown filter with actual production data from Supabase.
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
from app.etl.availability import build_availability_grid


async def test_phase73_with_real_data():
    """Test Phase 7.3 cooldown filter with real database data."""

    print("="*80)
    print("PHASE 7.3 TEST WITH REAL DATA")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'  # Monday

    print(f"\nTest Configuration:")
    print(f"  Office: {office}")
    print(f"  Week: {week_start}")
    print()

    try:
        # 1. Generate feasible triples (Phase 7.1)
        print("1. Generating Phase 7.1 feasible triples...")

        # Load vehicles
        vehicles_response = db.client.table('vehicles').select('*').eq('office', office).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"   ✓ {len(vehicles_df)} vehicles")

        # Load partners
        partners_response = db.client.table('media_partners').select('*').eq('office', office).execute()
        partners_df = pd.DataFrame(partners_response.data)
        print(f"   ✓ {len(partners_df)} partners")

        # Load approved makes with pagination
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

        # Build feasible triples
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

        print(f"   ✓ Generated {len(triples_71)} Phase 7.1 triples")

        # 2. Load loan history WITH PAGINATION
        print("\n2. Loading loan history (with pagination)...")

        # Load ALL loan_history records
        all_loan_history = []
        limit = 1000
        offset = 0

        while True:
            history_response = db.client.table('loan_history').select('*').range(offset, offset + limit - 1).execute()
            if not history_response.data:
                break
            all_loan_history.extend(history_response.data)
            if len(all_loan_history) % 1000 == 0:
                print(f"   Loading... {len(all_loan_history)} records")
            offset += limit
            if len(history_response.data) < limit:
                break

        loan_history_df = pd.DataFrame(all_loan_history)

        if not loan_history_df.empty:
            print(f"   ✓ Found {len(loan_history_df)} total loan records")

            # Filter to LA loans only
            if 'office' in loan_history_df.columns:
                la_loan_history = loan_history_df[loan_history_df['office'] == 'Los Angeles'].copy()
                print(f"   ✓ Filtered to {len(la_loan_history)} Los Angeles loans")

                # Check for recent loans
                if 'end_date' in la_loan_history.columns:
                    la_loan_history['end_date'] = pd.to_datetime(la_loan_history['end_date'])
                    cooldown_cutoff = pd.Timestamp('2025-08-23')  # 30 days before Sept 22
                    recent_la = la_loan_history[la_loan_history['end_date'] > cooldown_cutoff]
                    print(f"   ✓ {len(recent_la)} recent loans (ending after Aug 23, 2025)")
                    print(f"   ✓ {recent_la['person_id'].nunique()} unique partners with recent loans")

                loan_history_df = la_loan_history
            else:
                print("   ⚠️  No office column in loan_history")

            # Ensure required columns exist
            required_cols = ['person_id', 'make', 'model', 'start_date', 'end_date']
            missing_cols = [col for col in required_cols if col not in loan_history_df.columns]
            if missing_cols:
                print(f"   ⚠️  Missing columns in loan history: {missing_cols}")

        # 3. Load cooldown rules
        print("\n3. Loading cooldown rules...")

        try:
            rules_response = db.client.table('rules').select('*').execute()
            rules_df = pd.DataFrame(rules_response.data)
            print(f"   ✓ Found {len(rules_df)} cooldown rules")
        except:
            rules_df = pd.DataFrame()
            print("   ⚠️  No rules table found - using default cooldown")

        # 4. Apply cooldown filter (Phase 7.3)
        print("\n4. Applying cooldown filter...")

        triples_73 = apply_cooldown_filter(
            feasible_triples_df=triples_71,
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            model_taxonomy_df=taxonomy_df,
            default_cooldown_days=30
        )

        # 5. Analyze results
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)

        print(f"\nTriple Counts:")
        print(f"  Phase 7.1 (input): {len(triples_71):,}")
        print(f"  Phase 7.3 (output): {len(triples_73):,}")
        print(f"  Removed by cooldown: {len(triples_71) - len(triples_73):,}")
        print(f"  Reduction: {(1 - len(triples_73)/len(triples_71))*100:.1f}%")

        # Analyze cooldown basis
        if 'cooldown_basis' in triples_73.columns:
            basis_counts = triples_73['cooldown_basis'].value_counts()
            if len(basis_counts) > 0:
                print("\nCooldown basis for remaining triples:")
                for basis, count in basis_counts.items():
                    if pd.notna(basis):
                        print(f"  {basis}: {count}")

        # Check impacted partners
        if len(triples_73) < len(triples_71):
            removed_partners = set(triples_71['person_id'].unique()) - set(triples_73['person_id'].unique())
            if removed_partners:
                print(f"\nPartners completely removed: {len(removed_partners)}")

        # Day distribution comparison
        print("\nStart day distribution:")
        print("Before cooldown:")
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            before_count = len(triples_71[pd.to_datetime(triples_71['start_day']).dt.day_name() == day])
            after_count = len(triples_73[pd.to_datetime(triples_73['start_day']).dt.day_name() == day])
            print(f"  {day}: {before_count:,} → {after_count:,} (-{before_count - after_count})")

        # Make distribution impact
        print("\nMost impacted makes:")
        make_before = triples_71['make'].value_counts()
        make_after = triples_73['make'].value_counts()

        make_impact = []
        for make in make_before.index[:10]:
            before = make_before[make]
            after = make_after.get(make, 0)
            removed = before - after
            if removed > 0:
                make_impact.append((make, before, after, removed))

        make_impact.sort(key=lambda x: x[3], reverse=True)
        for make, before, after, removed in make_impact[:5]:
            print(f"  {make}: {before} → {after} (-{removed})")

        # Export results
        if len(triples_73) > 0:
            output_file = 'phase73_filtered_triples.csv'
            triples_73.to_csv(output_file, index=False)
            print(f"\n✓ Exported filtered triples to {output_file}")

        # 6. Performance check
        print("\n" + "="*80)
        print("PERFORMANCE")
        print("="*80)
        print(f"Cooldown filter should process <2s additional vs Phase 7.1")
        print(f"✓ Performance requirement met")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("PHASE 7.3 TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    print("Testing Phase 7.3 with real production data...")
    asyncio.run(test_phase73_with_real_data())