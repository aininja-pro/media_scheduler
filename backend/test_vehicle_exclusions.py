"""
Test script for vehicle exclusions module.
"""

import sys
import pandas as pd
from app.chain_builder.vehicle_exclusions import get_partners_not_reviewed, get_partner_vehicle_history


def test_partner_exclusions():
    """Test partner exclusion logic"""

    print("\n=== Testing Vehicle Chain Partner Exclusions ===\n")

    # Mock data
    partners_data = [
        {'person_id': 1001, 'name': 'LA Times', 'office': 'Los Angeles'},
        {'person_id': 1002, 'name': 'KTLA News', 'office': 'Los Angeles'},
        {'person_id': 1003, 'name': 'Daily News', 'office': 'Los Angeles'},
        {'person_id': 1004, 'name': 'NBC LA', 'office': 'Los Angeles'},
        {'person_id': 2001, 'name': 'SF Chronicle', 'office': 'San Francisco'},
    ]

    loan_history_data = [
        {'person_id': 1001, 'vin': 'VIN123', 'start_date': '2024-01-15', 'end_date': '2024-01-22'},
        {'person_id': 1001, 'vin': 'VIN123', 'start_date': '2024-03-10', 'end_date': '2024-03-17'},  # Reviewed twice
        {'person_id': 1002, 'vin': 'VIN123', 'start_date': '2024-02-01', 'end_date': '2024-02-08'},
        {'person_id': 1003, 'vin': 'VIN456', 'start_date': '2024-01-20', 'end_date': '2024-01-27'},  # Different vehicle
        {'person_id': 1004, 'vin': 'VIN789', 'start_date': '2024-02-15', 'end_date': '2024-02-22'},  # Different vehicle
    ]

    partners_df = pd.DataFrame(partners_data)
    loan_history_df = pd.DataFrame(loan_history_data)

    # Test 1: Get partners who haven't reviewed VIN123
    print("Test 1: Partners who haven't reviewed VIN123")
    result = get_partners_not_reviewed(
        vin='VIN123',
        office='Los Angeles',
        loan_history_df=loan_history_df,
        partners_df=partners_df
    )

    print(f"  Total partners in LA: {result['office_totals']['total_partners']}")
    print(f"  Eligible partners: {result['office_totals']['eligible']}")
    print(f"  Excluded partners: {result['office_totals']['excluded']}")
    print(f"  Eligible partner IDs: {result['eligible_partners']}")
    print(f"  Excluded partner IDs: {result['excluded_partners']}")

    # Verify: Partners 1001 and 1002 reviewed VIN123, so 1003 and 1004 should be eligible
    assert 1003 in result['eligible_partners'], "Partner 1003 should be eligible"
    assert 1004 in result['eligible_partners'], "Partner 1004 should be eligible"
    assert 1001 in result['excluded_partners'], "Partner 1001 should be excluded (reviewed VIN123)"
    assert 1002 in result['excluded_partners'], "Partner 1002 should be excluded (reviewed VIN123)"
    print("  ✓ Exclusions correct\n")

    # Test 2: Check exclusion details
    print("Test 2: Exclusion details for partner 1001")
    if 1001 in result['exclusion_details']:
        details = result['exclusion_details'][1001]
        print(f"  Name: {details['name']}")
        print(f"  Last loan date: {details['last_loan_date']}")
        print(f"  Total loans this vehicle: {details['total_loans_this_vehicle']}")
        assert details['total_loans_this_vehicle'] == 2, "Partner 1001 should have 2 loans of VIN123"
        print("  ✓ Exclusion details correct\n")

    # Test 3: Get specific partner-vehicle history
    print("Test 3: Partner 1001 history with VIN123")
    history = get_partner_vehicle_history(
        partner_id=1001,
        vin='VIN123',
        loan_history_df=loan_history_df
    )
    print(f"  Has reviewed: {history['has_reviewed']}")
    print(f"  Loan count: {history['loan_count']}")
    print(f"  Last loan date: {history['last_loan_date']}")
    assert history['has_reviewed'] == True, "Partner 1001 has reviewed VIN123"
    assert history['loan_count'] == 2, "Partner 1001 has 2 loans of VIN123"
    print("  ✓ Partner history correct\n")

    # Test 4: Partner who hasn't reviewed the vehicle
    print("Test 4: Partner 1003 history with VIN123")
    history = get_partner_vehicle_history(
        partner_id=1003,
        vin='VIN123',
        loan_history_df=loan_history_df
    )
    print(f"  Has reviewed: {history['has_reviewed']}")
    print(f"  Loan count: {history['loan_count']}")
    assert history['has_reviewed'] == False, "Partner 1003 hasn't reviewed VIN123"
    assert history['loan_count'] == 0, "Partner 1003 has 0 loans of VIN123"
    print("  ✓ Partner history correct\n")

    # Test 5: New vehicle (no history)
    print("Test 5: Partners for brand new vehicle")
    result = get_partners_not_reviewed(
        vin='VIN_BRAND_NEW',
        office='Los Angeles',
        loan_history_df=loan_history_df,
        partners_df=partners_df
    )
    print(f"  Eligible partners: {result['office_totals']['eligible']}")
    print(f"  Excluded partners: {result['office_totals']['excluded']}")
    assert result['office_totals']['eligible'] == 4, "All 4 LA partners should be eligible for new vehicle"
    assert result['office_totals']['excluded'] == 0, "No exclusions for new vehicle"
    print("  ✓ New vehicle logic correct\n")

    print("=== All Tests Passed! ✓ ===\n")


if __name__ == '__main__':
    try:
        test_partner_exclusions()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
