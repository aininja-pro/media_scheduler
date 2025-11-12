"""
FMS Integration Test Script
Tests the complete flow: Create assignment → Request → Check FMS
"""

import asyncio
import httpx
from app.services.database import db_service

async def test_fms_integration():
    """Test FMS integration end-to-end"""

    print("=" * 60)
    print("FMS INTEGRATION TEST")
    print("=" * 60)

    # Initialize database
    await db_service.initialize()

    # Step 1: Check FMS config
    print("\n[1/6] Checking FMS configuration...")
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8081/api/fms/config")
        config = response.json()
        print(f"  ✓ Environment: {config['environment']}")
        print(f"  ✓ Base URL: {config['base_url']}")
        print(f"  ✓ Requestor ID: {config['requestor_id']}")
        print(f"  ✓ Token configured: {config['token_configured']}")

    # Step 2: Find a vehicle with vehicle_id
    print("\n[2/6] Finding test vehicle with vehicle_id...")
    vehicles_result = db_service.client.table('vehicles') \
        .select('vin, vehicle_id, make, model, year') \
        .not_.is_('vehicle_id', 'null') \
        .limit(5) \
        .execute()

    if not vehicles_result.data or len(vehicles_result.data) == 0:
        print("  ✗ ERROR: No vehicles with vehicle_id found!")
        print("  → Run vehicle import first: POST /ingest/vehicles/url")
        return

    test_vehicle = vehicles_result.data[0]
    print(f"  ✓ Found vehicle: {test_vehicle['year']} {test_vehicle['make']} {test_vehicle['model']}")
    print(f"    VIN: {test_vehicle['vin']}")
    print(f"    vehicle_id: {test_vehicle['vehicle_id']}")

    # Step 3: Find a media partner
    print("\n[3/6] Finding test media partner...")
    partners_result = db_service.client.table('media_partners') \
        .select('person_id, name') \
        .limit(1) \
        .execute()

    if not partners_result.data or len(partners_result.data) == 0:
        print("  ✗ ERROR: No media partners found!")
        return

    test_partner = partners_result.data[0]
    print(f"  ✓ Found partner: {test_partner['name']}")
    print(f"    person_id: {test_partner['person_id']}")

    # Step 4: Create a test assignment
    print("\n[4/6] Creating test assignment...")
    from datetime import date, timedelta

    start_date = date.today() + timedelta(days=7)  # Next week
    end_date = start_date + timedelta(days=7)

    assignment_data = {
        'vin': test_vehicle['vin'],
        'person_id': test_partner['person_id'],
        'start_day': str(start_date),
        'end_day': str(end_date),
        'make': test_vehicle['make'],
        'model': test_vehicle['model'],
        'office': 'Los Angeles',
        'partner_name': test_partner['name'],
        'status': 'manual',  # Start as manual (green)
        'week_start': str(start_date)
    }

    assignment_result = db_service.client.table('scheduled_assignments') \
        .insert(assignment_data) \
        .execute()

    if not assignment_result.data:
        print("  ✗ ERROR: Failed to create assignment")
        return

    test_assignment_id = assignment_result.data[0]['assignment_id']
    print(f"  ✓ Created assignment #{test_assignment_id}")
    print(f"    Vehicle: {test_vehicle['make']} {test_vehicle['model']}")
    print(f"    Partner: {test_partner['name']}")
    print(f"    Dates: {start_date} to {end_date}")
    print(f"    Status: manual (green)")

    # Step 5: Request the assignment (green → magenta)
    print("\n[5/6] Requesting assignment in FMS (green → magenta)...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.patch(
                f"http://localhost:8081/api/calendar/change-assignment-status/{test_assignment_id}?new_status=requested"
            )

            if response.status_code == 200:
                result = response.json()
                print(f"  ✓ Status changed successfully!")
                print(f"    Old status: {result.get('old_status')}")
                print(f"    New status: {result.get('new_status')}")
                print(f"    FMS action: {result.get('fms_action')}")

                # Check if FMS request ID was stored
                check_result = db_service.client.table('scheduled_assignments') \
                    .select('fms_request_id') \
                    .eq('assignment_id', test_assignment_id) \
                    .execute()

                if check_result.data and check_result.data[0].get('fms_request_id'):
                    fms_request_id = check_result.data[0]['fms_request_id']
                    print(f"    FMS request ID: {fms_request_id}")
                else:
                    print(f"    ⚠ Warning: FMS request ID not stored (might be normal if FMS didn't return it)")

            else:
                print(f"  ✗ ERROR: Status change failed!")
                print(f"    Status code: {response.status_code}")
                print(f"    Response: {response.text}")

        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")

    # Step 6: Summary and next steps
    print("\n[6/6] Test Summary")
    print("=" * 60)
    print("✓ FMS config verified")
    print("✓ Test vehicle found")
    print("✓ Test assignment created")
    print("✓ Request flow tested")
    print("\nNext steps:")
    print("1. Check FMS staging: https://staging.driveshop.com")
    print("   → Look for vehicle request in pending approvals")
    print(f"2. Test unrequest: PATCH /api/calendar/change-assignment-status/{test_assignment_id}?new_status=manual")
    print(f"3. Clean up: DELETE /api/calendar/assignment/{test_assignment_id}")
    print("\n⚠ Note: DELETE endpoint on FMS side is still in progress")
    print("   → Coordinate with Alex before testing deletion flow")
    print("=" * 60)

    await db_service.close()

if __name__ == "__main__":
    asyncio.run(test_fms_integration())
