"""
Test OR-Tools vehicle chain solver with REAL database data.
"""

import sys
from app.services.database import DatabaseService
import pandas as pd
from app.chain_builder.geography import (
    score_partners_base,
    calculate_distance_matrix
)
from app.chain_builder.vehicle_exclusions import get_partners_not_reviewed
from app.solver.vehicle_chain_solver import (
    solve_vehicle_chain,
    Partner,
    calculate_slot_dates
)


def test_with_real_data():
    """Test OR-Tools solver with real database data"""

    print("\n=== Testing OR-Tools Vehicle Chain Solver with REAL DATA ===\n")

    db = DatabaseService()

    try:
        # 1. Get real Audi vehicle
        print("Step 1: Loading real Audi vehicle...")
        vehicles_response = db.client.table('vehicles').select('*').eq('office', 'Los Angeles').eq('make', 'Audi').limit(1).execute()

        if not vehicles_response.data:
            print("❌ No Audi vehicles found in LA")
            return

        vehicle = vehicles_response.data[0]
        vin = vehicle['vin']
        make = vehicle['make']
        model = vehicle.get('model', '')

        print(f"  ✓ Vehicle: {make} {model}")
        print(f"  ✓ VIN: {vin}")
        print()

        # 2. Load all necessary data with pagination
        print("Step 2: Loading partner data...")

        partners_response = db.client.table('media_partners').select('*').eq('office', 'Los Angeles').execute()
        partners_df = pd.DataFrame(partners_response.data)
        print(f"  ✓ Loaded {len(partners_df)} LA partners")

        # Load approved_makes with pagination
        approved_makes = []
        offset = 0
        while True:
            response = db.client.table('approved_makes').select('*').range(offset, offset + 999).execute()
            if not response.data:
                break
            approved_makes.extend(response.data)
            offset += 1000
            if len(response.data) < 1000:
                break

        approved_makes_df = pd.DataFrame(approved_makes)
        print(f"  ✓ Loaded {len(approved_makes_df)} approved_makes records")

        # Load loan history with pagination
        loan_history = []
        offset = 0
        while True:
            response = db.client.table('loan_history').select('*').range(offset, offset + 999).execute()
            if not response.data:
                break
            loan_history.extend(response.data)
            offset += 1000
            if len(response.data) < 1000:
                break

        loan_history_df = pd.DataFrame(loan_history)
        print(f"  ✓ Loaded {len(loan_history_df)} loan history records")
        print()

        # 3. Get eligible partners (not reviewed, approved for make)
        print("Step 3: Filtering eligible partners...")

        exclusion_result = get_partners_not_reviewed(
            vin=vin,
            office='Los Angeles',
            loan_history_df=loan_history_df,
            partners_df=partners_df,
            approved_makes_df=approved_makes_df,
            vehicle_make=make
        )

        eligible_partner_ids = exclusion_result['eligible_partners']
        print(f"  ✓ Eligible partners: {len(eligible_partner_ids)}")
        print(f"  ✓ Excluded (reviewed): {len(exclusion_result['excluded_partners'])}")
        print(f"  ✓ Ineligible (not approved for {make}): {len(exclusion_result['ineligible_make'])}")
        print()

        if len(eligible_partner_ids) < 4:
            print(f"❌ Not enough eligible partners. Need at least 4, have {len(eligible_partner_ids)}")
            return

        # 4. Score partners
        print("Step 4: Scoring eligible partners...")

        scores = score_partners_base(
            partners_df=partners_df,
            vehicle_make=make,
            approved_makes_df=approved_makes_df,
            loan_history_df=loan_history_df
        )

        # Filter scores to only eligible partners
        eligible_scores = {pid: scores[pid] for pid in eligible_partner_ids if pid in scores}
        print(f"  ✓ Scored {len(eligible_scores)} eligible partners")

        if eligible_scores:
            avg_score = sum(s['base_score'] for s in eligible_scores.values()) / len(eligible_scores)
            print(f"  ✓ Average base score: {avg_score:.1f}")
        print()

        # 5. Calculate distance matrix for eligible partners
        print("Step 5: Calculating distance matrix...")

        # IMPORTANT: Convert types - person_id is STRING in DB, but eligible_ids are INT
        partners_df['person_id'] = partners_df['person_id'].astype(int)
        eligible_partner_ids_int = [int(pid) for pid in eligible_partner_ids]

        eligible_partners_df = partners_df[partners_df['person_id'].isin(eligible_partner_ids_int)]
        distance_matrix = calculate_distance_matrix(eligible_partners_df)

        print(f"  ✓ Calculated {len(distance_matrix)} pairwise distances")
        print()

        # 6. Build Partner objects for solver
        print("Step 6: Preparing candidate partners for solver...")

        candidates = []
        for _, partner in eligible_partners_df.iterrows():
            person_id = int(partner['person_id'])

            # Get score data
            score_data = scores.get(person_id, {})

            candidates.append(Partner(
                person_id=person_id,
                name=partner.get('name', f'Partner {person_id}'),
                latitude=partner.get('latitude'),
                longitude=partner.get('longitude'),
                base_score=score_data.get('base_score', 0),
                engagement_level=score_data.get('engagement_level', 'neutral'),
                publication_rate=score_data.get('publication_rate', 0.0),
                tier_rank=score_data.get('tier_rank', 'N/A'),
                available=True
            ))

        # Filter to only those with coordinates
        candidates_with_coords = [c for c in candidates if c.latitude is not None and c.longitude is not None]

        print(f"  ✓ Total candidates: {len(candidates)}")
        print(f"  ✓ With coordinates: {len(candidates_with_coords)}")
        print()

        # 7. Test slot date calculation
        print("Step 7: Calculating slot dates (8-day loans)...")

        slot_dates = calculate_slot_dates('2025-11-03', 4, 8)

        print(f"  Chain slots:")
        for slot in slot_dates:
            extended = " (extended)" if slot.extended_for_weekend else ""
            print(f"    Slot {slot.slot_index}: {slot.start_date} → {slot.end_date} ({slot.actual_duration} days){extended}")
        print()

        # 8. SOLVE with OR-Tools
        print("Step 8: Solving with OR-Tools CP-SAT (4 partners)...")
        print(f"  Distance weight: 0.7 (70% prioritize distance)")
        print(f"  Max distance per hop: 50 miles")
        print()

        result = solve_vehicle_chain(
            vin=vin,
            vehicle_make=make,
            office='Los Angeles',
            start_date='2025-11-03',
            num_partners=4,
            days_per_loan=8,
            candidates=candidates,
            distance_matrix=distance_matrix,
            distance_weight=0.7,
            max_distance_per_hop=50.0,
            distance_cost_per_mile=2.0,
            solver_timeout_seconds=30.0
        )

        print(f"  ✓ Solver status: {result.status}")
        print(f"  ✓ Solver time: {result.solver_time_ms}ms")
        print()

        if result.status == 'success':
            print("Step 9: Optimal chain found!")
            print()

            for slot in result.chain:
                print(f"  Slot {slot['slot']}: {slot['start_date']} → {slot['end_date']}")
                print(f"    Partner: {slot['name']} (ID: {slot['person_id']})")
                print(f"    Score: {slot['score']} (Tier: {slot['tier']}, Engagement: {slot['engagement_level']})")

                if slot['handoff']:
                    h = slot['handoff']
                    print(f"    Handoff on {h['date']}: → {h['to_partner']}")
                    print(f"      Distance: {h['distance_miles']} miles (~{h['estimated_drive_time_min']} min)")
                    print(f"      Cost: ${h['logistics_cost']}")
                print()

            # Show optimization stats
            print("Optimization Results:")
            stats = result.optimization_stats
            print(f"  Total quality score: {stats['total_quality_score']}")
            print(f"  Average quality: {stats['average_quality_score']}")
            print(f"  Objective value: {stats['objective_value']}")
            print()

            # Show logistics summary
            print("Logistics Summary:")
            logistics = result.logistics_summary
            print(f"  Total distance: {logistics['total_distance_miles']} miles")
            print(f"  Average per hop: {logistics['average_distance_miles']} miles")
            print(f"  Total drive time: ~{logistics['total_drive_time_min']} minutes")
            print(f"  Total cost: ${logistics['total_logistics_cost']}")

            if logistics['longest_hop']:
                lh = logistics['longest_hop']
                print(f"  Longest hop: {lh['from']} → {lh['to']} ({lh['distance']} mi)")

            if logistics['all_hops_within_limit']:
                print(f"  ✓ All hops within {result.diagnostics['max_distance_limit']} mile limit")
            else:
                print(f"  ⚠️ Some hops exceed limit!")
            print()

            print("=== OR-Tools Solver Test PASSED! ✓ ===\n")

        else:
            print(f"❌ Solver failed: {result.status}")
            print(f"Reason: {result.diagnostics.get('reason')}")
            print()

    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    test_with_real_data()
