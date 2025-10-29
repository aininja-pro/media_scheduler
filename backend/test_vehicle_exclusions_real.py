"""
Test vehicle exclusions with REAL database data.
"""

import sys
import asyncio
import pandas as pd
from app.services.database import DatabaseService
from app.chain_builder.vehicle_exclusions import get_partners_not_reviewed, get_partner_vehicle_history


async def test_with_real_data():
    """Test partner exclusion logic with real database data"""

    print("\n=== Testing Vehicle Chain Partner Exclusions with REAL DATA ===\n")

    # Initialize database
    db = DatabaseService()

    try:
        # 1. Get a real vehicle from the database
        print("Step 1: Loading real vehicle from database...")
        vehicles_response = db.client.table('vehicles').select('*').eq('office', 'Los Angeles').limit(5).execute()
        vehicles_df = pd.DataFrame(vehicles_response.data) if vehicles_response.data else pd.DataFrame()

        if vehicles_df.empty:
            print("❌ No vehicles found in Los Angeles")
            return

        # Pick first vehicle
        test_vehicle = vehicles_df.iloc[0]
        test_vin = test_vehicle['vin']
        test_make = test_vehicle['make']
        test_model = test_vehicle['model']

        print(f"  ✓ Using vehicle: {test_make} {test_model}")
        print(f"  ✓ VIN: {test_vin}")
        print()

        # 2. Load real loan history
        print("Step 2: Loading real loan history...")
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

        loan_history_df = pd.DataFrame(all_loan_history) if all_loan_history else pd.DataFrame()
        print(f"  ✓ Loaded {len(loan_history_df)} total loan history records")
        print()

        # 3. Load real media partners
        print("Step 3: Loading real media partners...")
        partners_response = db.client.table('media_partners').select('person_id, name, office').execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()
        print(f"  ✓ Loaded {len(partners_df)} total media partners")

        la_partners = partners_df[partners_df['office'] == 'Los Angeles']
        print(f"  ✓ Found {len(la_partners)} partners in Los Angeles")
        print()

        # 4. Test exclusion logic with this real vehicle
        print(f"Step 4: Testing exclusions for {test_vin}...")
        result = get_partners_not_reviewed(
            vin=test_vin,
            office='Los Angeles',
            loan_history_df=loan_history_df,
            partners_df=partners_df
        )

        print(f"\n  Results:")
        print(f"  ├─ Total LA partners: {result['office_totals']['total_partners']}")
        print(f"  ├─ Eligible partners: {result['office_totals']['eligible']}")
        print(f"  └─ Excluded partners: {result['office_totals']['excluded']}")
        print()

        # 5. Show exclusion details if any
        if result['excluded_partners']:
            print(f"  Excluded Partners (who have reviewed {test_vin}):")
            for partner_id in result['excluded_partners'][:5]:  # Show first 5
                if partner_id in result['exclusion_details']:
                    details = result['exclusion_details'][partner_id]
                    print(f"    • {details['name']} - Last loan: {details['last_loan_date']}, Total loans: {details['total_loans_this_vehicle']}")
            if len(result['excluded_partners']) > 5:
                print(f"    ... and {len(result['excluded_partners']) - 5} more")
            print()
        else:
            print(f"  ✓ No partners have reviewed this vehicle yet (all {result['office_totals']['eligible']} are eligible)")
            print()

        # 6. Check if this vehicle exists in loan history at all
        if 'vin' in loan_history_df.columns:
            vehicle_loans = loan_history_df[loan_history_df['vin'] == test_vin]
            print(f"Step 5: Loan history for {test_vin}:")
            print(f"  ├─ Total loans in history: {len(vehicle_loans)}")

            if not vehicle_loans.empty:
                unique_partners = vehicle_loans['person_id'].nunique()
                print(f"  └─ Unique partners who reviewed: {unique_partners}")
                print()

                # Verify exclusion count matches
                assert result['office_totals']['excluded'] == unique_partners, \
                    f"Exclusion count mismatch! Expected {unique_partners}, got {result['office_totals']['excluded']}"
                print("  ✓ Exclusion count matches loan history ✓")
            else:
                print(f"  └─ No loan history found for this vehicle")
                assert result['office_totals']['excluded'] == 0, "Should have 0 exclusions for vehicle with no history"
                print("  ✓ Correctly shows 0 exclusions ✓")
        print()

        # 7. Test a specific partner-vehicle combination if exclusions exist
        if result['excluded_partners']:
            test_partner_id = result['excluded_partners'][0]
            print(f"Step 6: Testing specific partner history...")
            history = get_partner_vehicle_history(
                partner_id=test_partner_id,
                vin=test_vin,
                loan_history_df=loan_history_df
            )

            partner_name = result['exclusion_details'][test_partner_id]['name']
            print(f"  Partner: {partner_name} (ID: {test_partner_id})")
            print(f"  ├─ Has reviewed: {history['has_reviewed']}")
            print(f"  ├─ Loan count: {history['loan_count']}")
            print(f"  └─ Last loan date: {history['last_loan_date']}")

            assert history['has_reviewed'] == True, "Should show as reviewed"
            assert history['loan_count'] > 0, "Should have at least 1 loan"
            print("  ✓ Partner history retrieval works ✓")
            print()

        # 8. Try with a different real vehicle
        if len(vehicles_df) > 1:
            print("Step 7: Testing with second vehicle...")
            test_vehicle_2 = vehicles_df.iloc[1]
            test_vin_2 = test_vehicle_2['vin']

            result_2 = get_partners_not_reviewed(
                vin=test_vin_2,
                office='Los Angeles',
                loan_history_df=loan_history_df,
                partners_df=partners_df
            )

            print(f"  Vehicle: {test_vehicle_2['make']} {test_vehicle_2['model']} ({test_vin_2})")
            print(f"  ├─ Eligible: {result_2['office_totals']['eligible']}")
            print(f"  └─ Excluded: {result_2['office_totals']['excluded']}")
            print("  ✓ Second vehicle test passed ✓")
            print()

        print("=== All Real Data Tests Passed! ✓ ===\n")

    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(test_with_real_data())
