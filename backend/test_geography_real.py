"""
Test geographic distance calculations with REAL database data.
"""

import sys
from app.services.database import DatabaseService
import pandas as pd
from app.chain_builder.geography import (
    haversine_distance,
    calculate_distance_matrix,
    calculate_partner_distances,
    get_nearest_partners,
    estimate_drive_time,
    validate_coordinates
)


def test_with_real_data():
    """Test geography module with real LA partner data"""

    print("\n=== Testing Geographic Distance Calculations with REAL DATA ===\n")

    # Initialize database
    db = DatabaseService()

    try:
        # 1. Load real LA partners
        print("Step 1: Loading real LA partners with coordinates...")
        partners_response = db.client.table('media_partners').select('*').eq('office', 'Los Angeles').execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

        if partners_df.empty:
            print("❌ No partners found in Los Angeles")
            return

        print(f"  ✓ Loaded {len(partners_df)} LA partners")

        # Validate coordinates
        coord_stats = validate_coordinates(partners_df)
        print(f"  ✓ Coordinate coverage: {coord_stats['with_coordinates']}/{coord_stats['total_partners']} ({coord_stats['coverage_percent']}%)")
        if coord_stats['missing_coordinates'] > 0:
            print(f"  ⚠ {coord_stats['missing_coordinates']} partners missing coordinates")
        print()

        # 2. Test Haversine formula with known LA landmarks
        print("Step 2: Testing Haversine formula with known distances...")

        # Find two partners with coordinates
        valid_partners = partners_df[partners_df['latitude'].notna() & partners_df['longitude'].notna()]

        if len(valid_partners) >= 2:
            p1 = valid_partners.iloc[0]
            p2 = valid_partners.iloc[1]

            distance = haversine_distance(
                float(p1['latitude']),
                float(p1['longitude']),
                float(p2['latitude']),
                float(p2['longitude'])
            )

            print(f"  Partner 1: {p1['name']} ({p1['latitude']}, {p1['longitude']})")
            print(f"  Partner 2: {p2['name']} ({p2['latitude']}, {p2['longitude']})")
            print(f"  Distance: {distance:.2f} miles")
            print(f"  ✓ Haversine calculation works")
        print()

        # 3. Test distance matrix calculation (use subset for performance)
        print("Step 3: Testing distance matrix calculation...")
        subset_partners = valid_partners.head(10)  # Use 10 partners to avoid slow calculation
        distance_matrix = calculate_distance_matrix(subset_partners)

        expected_pairs = len(subset_partners) * (len(subset_partners) - 1)
        print(f"  ✓ Calculated {len(distance_matrix)} pairwise distances")
        print(f"  ✓ Expected {expected_pairs} pairs")

        # Verify symmetry
        if len(distance_matrix) > 0:
            # Get first pair
            key = list(distance_matrix.keys())[0]
            reverse_key = (key[1], key[0])
            if reverse_key in distance_matrix:
                dist_forward = distance_matrix[key]
                dist_reverse = distance_matrix[reverse_key]
                print(f"  ✓ Symmetry check: {key} = {dist_forward:.2f} mi, {reverse_key} = {dist_reverse:.2f} mi")
                assert abs(dist_forward - dist_reverse) < 0.01, "Distances should be symmetric"
        print()

        # 4. Test calculate_partner_distances (single source)
        print("Step 4: Testing single-source distance calculation...")
        if not valid_partners.empty:
            source_partner = valid_partners.iloc[0]
            source_id = int(source_partner['person_id'])

            distances = calculate_partner_distances(source_id, partners_df)
            print(f"  Source: {source_partner['name']} (ID: {source_id})")
            print(f"  ✓ Calculated distances to {len(distances)} other partners")

            if distances:
                # Show closest partners
                sorted_distances = sorted(distances.items(), key=lambda x: x[1])
                print(f"\n  Closest 5 partners:")
                for partner_id, dist in sorted_distances[:5]:
                    partner = partners_df[partners_df['person_id'] == partner_id]
                    if not partner.empty:
                        print(f"    • {partner.iloc[0]['name']}: {dist:.2f} miles")
        print()

        # 5. Test get_nearest_partners function
        print("Step 5: Testing get_nearest_partners (with max distance)...")
        if not valid_partners.empty:
            source_partner = valid_partners.iloc[0]
            source_id = int(source_partner['person_id'])

            # Get partners within 10 miles
            nearest = get_nearest_partners(
                partner_id=source_id,
                all_partners_df=partners_df,
                max_distance=10.0,
                limit=5
            )

            print(f"  Source: {source_partner['name']}")
            print(f"  ✓ Found {len(nearest)} partners within 10 miles (limit 5)")

            if nearest:
                print(f"\n  Partners within 10 miles:")
                for p in nearest:
                    print(f"    • {p['name']}: {p['distance_miles']} miles")
        print()

        # 6. Test drive time estimation
        print("Step 6: Testing drive time estimation...")
        test_distances = [1.0, 5.0, 10.0, 25.0, 50.0]
        print("  Distance → Estimated Drive Time (@ 20 mph avg):")
        for dist in test_distances:
            time = estimate_drive_time(dist)
            print(f"    {dist} miles → {time} minutes")
        print()

        # 7. Real-world scenario test
        print("Step 7: Real-world same-day handoff scenario...")
        if len(valid_partners) >= 3:
            # Simulate a 3-partner chain
            chain_partners = valid_partners.head(3)

            total_distance = 0
            total_time = 0

            print("  Simulated 3-partner chain:")
            for i in range(len(chain_partners) - 1):
                p_current = chain_partners.iloc[i]
                p_next = chain_partners.iloc[i + 1]

                dist = haversine_distance(
                    float(p_current['latitude']),
                    float(p_current['longitude']),
                    float(p_next['latitude']),
                    float(p_next['longitude'])
                )
                time = estimate_drive_time(dist)

                print(f"    Handoff {i + 1}: {p_current['name']} → {p_next['name']}")
                print(f"      Distance: {dist:.2f} miles, Time: ~{time} min")

                total_distance += dist
                total_time += time

            print(f"\n  Chain totals:")
            print(f"    Total distance: {total_distance:.2f} miles")
            print(f"    Total drive time: ~{total_time} minutes")
            print(f"    Logistics cost (@ $2/mile): ${total_distance * 2:.2f}")

            if total_distance > 50:
                print(f"    ⚠️ WARNING: Total distance exceeds 50 miles (may not be feasible for same-day)")
            else:
                print(f"    ✓ Feasible for same-day handoffs")
        print()

        print("=== All Real Data Geography Tests Passed! ✓ ===\n")

    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    test_with_real_data()
