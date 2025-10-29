"""
Check what level cooldown is actually operating at.
"""

import asyncio
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
from app.solver.cooldown_filter import build_cooldown_ledger


async def check_cooldown_level():
    """Check cooldown grouping levels in loan history."""

    print("="*80)
    print("CHECKING COOLDOWN GROUPING LEVELS")
    print("="*80)

    db = DatabaseService()
    await db.initialize()

    try:
        # Load loan history with pagination
        print("\n1. Loading loan history...")
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
        la_loans = loan_history_df[loan_history_df['office'] == 'Los Angeles'].copy()
        print(f"   Found {len(la_loans)} LA loans")

        # Load taxonomy
        print("\n2. Loading model taxonomy...")
        taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
        taxonomy_df = pd.DataFrame(taxonomy_response.data)
        print(f"   Found {len(taxonomy_df)} model classifications")

        # Build ledger
        print("\n3. Building cooldown ledger...")
        ledger = build_cooldown_ledger(la_loans, taxonomy_df)

        # Analyze ledger keys
        print("\n4. Analyzing ledger grouping levels...")

        class_pwr_count = 0
        model_count = 0
        make_count = 0

        for key in ledger.keys():
            if key[0] == "CLASS_PWR":
                class_pwr_count += 1
            elif key[0] == "MODEL":
                model_count += 1
            elif key[0] == "MAKE":
                make_count += 1

        print(f"\nLedger entries by level:")
        print(f"  Class+Powertrain: {class_pwr_count}")
        print(f"  Model: {model_count}")
        print(f"  Make: {make_count}")

        # Check if loan_history has model taxonomy data
        print("\n5. Checking loan_history columns...")
        print(f"   Columns: {list(la_loans.columns)}")

        if 'short_model_class' in la_loans.columns:
            print(f"   Has short_model_class: YES")
            print(f"   Non-null short_model_class: {la_loans['short_model_class'].notna().sum()}/{len(la_loans)}")
        else:
            print(f"   Has short_model_class: NO")

        if 'powertrain' in la_loans.columns:
            print(f"   Has powertrain: YES")
            print(f"   Non-null powertrain: {la_loans['powertrain'].notna().sum()}/{len(la_loans)}")
        else:
            print(f"   Has powertrain: NO")

        # Check if we need to join with taxonomy
        print("\n6. After joining with taxonomy...")

        if 'model' in la_loans.columns and not la_loans.empty:
            # Join with taxonomy
            enhanced_loans = la_loans.merge(
                taxonomy_df[['model', 'short_model_class', 'powertrain']].drop_duplicates(),
                on='model',
                how='left',
                suffixes=('', '_tax')
            )

            # Use taxonomy values if original is null
            if 'short_model_class_tax' in enhanced_loans.columns:
                if 'short_model_class' not in enhanced_loans.columns:
                    enhanced_loans['short_model_class'] = enhanced_loans['short_model_class_tax']
                else:
                    enhanced_loans['short_model_class'] = enhanced_loans['short_model_class'].fillna(enhanced_loans['short_model_class_tax'])

            if 'powertrain_tax' in enhanced_loans.columns:
                if 'powertrain' not in enhanced_loans.columns:
                    enhanced_loans['powertrain'] = enhanced_loans['powertrain_tax']
                else:
                    enhanced_loans['powertrain'] = enhanced_loans['powertrain'].fillna(enhanced_loans['powertrain_tax'])

            print(f"   Records with class+powertrain: {(enhanced_loans['short_model_class'].notna() & enhanced_loans['powertrain'].notna()).sum()}")
            print(f"   Records with model only: {enhanced_loans['model'].notna().sum()}")
            print(f"   Records with make only: {enhanced_loans['make'].notna().sum()}")

            # Sample some records to see what level they're at
            print("\n7. Sample recent loans and their grouping level:")
            recent_loans = enhanced_loans[pd.to_datetime(enhanced_loans['end_date']) > '2025-07-24'].head(10)

            for _, loan in recent_loans.iterrows():
                person_id = loan['person_id']
                make = loan.get('make', 'N/A')
                model = loan.get('model', 'N/A')
                model_class = loan.get('short_model_class', 'N/A')
                powertrain = loan.get('powertrain', 'N/A')

                if pd.notna(model_class) and pd.notna(powertrain) and model_class != 'N/A' and powertrain != 'N/A':
                    level = "CLASS+POWERTRAIN"
                elif pd.notna(model) and model != 'N/A':
                    level = "MODEL"
                else:
                    level = "MAKE"

                print(f"   Partner {person_id}: {make} {model}")
                print(f"      Class: {model_class}, Powertrain: {powertrain}")
                print(f"      → Cooldown level: {level}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(check_cooldown_level())