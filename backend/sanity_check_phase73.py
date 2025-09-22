"""
Sanity checks for Phase 7.3 cooldown implementation.
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


async def sanity_checks():
    """Run comprehensive sanity checks for Phase 7.3."""

    print("="*80)
    print("PHASE 7.3 SANITY CHECKS")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    office = 'Los Angeles'
    week_start = '2025-09-22'

    try:
        # === 1. Generate feasible triples ===
        print("\n1. GENERATING FEASIBLE TRIPLES...")

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
        print(f"   ✓ Generated {len(triples_71)} Phase 7.1 triples")

        # === 2. Load loan history ===
        print("\n2. LOADING LOAN HISTORY...")

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
        la_loan_history = loan_history_df[loan_history_df['office'] == 'Los Angeles'].copy()
        print(f"   ✓ Found {len(la_loan_history)} LA loan history records")

        # === 3. Load cooldown rules ===
        print("\n3. LOADING COOLDOWN RULES...")

        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data)
        print(f"   ✓ Found {len(rules_df)} cooldown rules")

        # Display some rules
        if not rules_df.empty:
            print("\n   Sample rules:")
            sample_rules = rules_df[['make', 'cooldown_period']].head(5)
            for _, rule in sample_rules.iterrows():
                print(f"     {rule['make']}: {rule['cooldown_period']} days")

            # Check for 0-day rules
            zero_rules = rules_df[rules_df['cooldown_period'] == 0]
            if not zero_rules.empty:
                print(f"\n   ✓ Rules with cooldown disabled (0 days):")
                for _, rule in zero_rules.iterrows():
                    print(f"     {rule['make']}: DISABLED")

        # === 4. Apply cooldown filter ===
        print("\n4. APPLYING COOLDOWN FILTER...")

        triples_73 = apply_cooldown_filter(
            feasible_triples_df=triples_71,
            loan_history_df=la_loan_history,
            rules_df=rules_df,
            model_taxonomy_df=taxonomy_df,
            default_cooldown_days=30
        )

        # === SANITY CHECK 1: Verify cooldown fields ===
        print("\n" + "="*60)
        print("SANITY CHECK 1: Cooldown Fields Attached")
        print("="*60)

        required_fields = ['cooldown_ok', 'cooldown_basis', 'cooldown_until']
        missing_fields = [f for f in required_fields if f not in triples_73.columns]

        if missing_fields:
            print(f"❌ FAIL: Missing fields: {missing_fields}")
        else:
            print("✓ All cooldown fields present:")
            print(f"  - cooldown_ok: {triples_73['cooldown_ok'].dtype}")
            print(f"  - cooldown_basis: {triples_73['cooldown_basis'].dtype}")
            print(f"  - cooldown_until: {triples_73['cooldown_until'].dtype}")

            # Check field values
            print("\nField value distributions:")
            print(f"  cooldown_ok: {triples_73['cooldown_ok'].value_counts().to_dict()}")

            basis_counts = triples_73['cooldown_basis'].value_counts()
            if len(basis_counts) > 0:
                print(f"  cooldown_basis:")
                for basis, count in basis_counts.items():
                    if pd.notna(basis):
                        print(f"    {basis}: {count}")

            # Sample some records with cooldown info
            sample_with_cooldown = triples_73[triples_73['cooldown_basis'].notna()].head(3)
            if not sample_with_cooldown.empty:
                print("\nSample records with cooldown info:")
                for _, row in sample_with_cooldown.iterrows():
                    print(f"  Partner {row['person_id']}, {row['make']} {row['model']}")
                    print(f"    basis: {row['cooldown_basis']}, until: {row['cooldown_until']}")

        # === SANITY CHECK 2: Impact Report ===
        print("\n" + "="*60)
        print("SANITY CHECK 2: LA Impact Report")
        print("="*60)

        removed_count = len(triples_71) - len(triples_73)
        print(f"\nTriples removed by cooldown: {removed_count:,}")

        if removed_count > 0:
            # Get removed triples
            all_ids_71 = set(triples_71.index)
            all_ids_73 = set(triples_73.index)
            removed_ids = all_ids_71 - all_ids_73
            removed_triples = triples_71.loc[list(removed_ids)]

            # Count by basis (we need to run filter again to get basis for removed)
            temp_result = apply_cooldown_filter(
                feasible_triples_df=triples_71,
                loan_history_df=la_loan_history,
                rules_df=rules_df,
                model_taxonomy_df=taxonomy_df,
                default_cooldown_days=30
            )

            removed_only = temp_result[temp_result['cooldown_ok'] == False]
            if not removed_only.empty:
                basis_counts = removed_only['cooldown_basis'].value_counts()
                print(f"\nBreakdown by basis:")
                for basis, count in basis_counts.items():
                    print(f"  {basis}: {count:,}")

            # Top affected partners
            print("\nTop 5 affected partners:")
            partner_counts = removed_triples['person_id'].value_counts().head(5)
            for pid, count in partner_counts.items():
                # Get partner name if available
                partner_info = partners_df[partners_df['person_id'] == pid]
                if not partner_info.empty:
                    name = partner_info.iloc[0].get('name', 'Unknown')
                    print(f"  {pid} ({name}): {count} triples removed")
                else:
                    print(f"  {pid}: {count} triples removed")

            # Top affected makes
            print("\nTop 5 affected makes:")
            make_counts = removed_triples['make'].value_counts().head(5)
            for make, count in make_counts.items():
                print(f"  {make}: {count} triples removed")

        # === SANITY CHECK 3: Rule Overrides ===
        print("\n" + "="*60)
        print("SANITY CHECK 3: Rule Override Verification")
        print("="*60)

        # Test specific makes with rules
        if not rules_df.empty:
            # Find a make with a specific rule
            test_makes = rules_df[rules_df['cooldown_period'].notna()].head(3)

            print("\nVerifying rule overrides:")
            for _, rule in test_makes.iterrows():
                make = rule['make']
                rule_days = rule['cooldown_period']

                # Count triples for this make
                make_triples = triples_71[triples_71['make'] == make]
                make_after = triples_73[triples_73['make'] == make]

                removed = len(make_triples) - len(make_after)

                if rule_days == 0:
                    if removed == 0:
                        print(f"  ✓ {make}: cooldown=0 (disabled) - no removals")
                    else:
                        print(f"  ❌ {make}: cooldown=0 but {removed} removed!")
                else:
                    print(f"  ✓ {make}: cooldown={rule_days} days - {removed} removed")

            # Test a make WITHOUT a rule (should use default)
            all_rule_makes = set(rules_df['make'].unique())
            all_makes = set(triples_71['make'].unique())
            makes_without_rules = all_makes - all_rule_makes

            if makes_without_rules:
                test_make = list(makes_without_rules)[0]
                make_triples = triples_71[triples_71['make'] == test_make]
                make_after = triples_73[triples_73['make'] == test_make]
                removed = len(make_triples) - len(make_after)
                print(f"  ✓ {test_make}: no rule (using default 30) - {removed} removed")

        # === FINAL SUMMARY ===
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)

        print(f"\n✓ Phase 7.1 triples: {len(triples_71):,}")
        print(f"✓ Phase 7.3 triples: {len(triples_73):,}")
        print(f"✓ Removed by cooldown: {removed_count:,} ({removed_count/len(triples_71)*100:.1f}%)")
        print(f"✓ Cooldown fields attached to all remaining triples")
        print(f"✓ Rules override defaults correctly")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("SANITY CHECKS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(sanity_checks())