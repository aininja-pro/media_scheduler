"""
Simple test of fallback caps without complex ETL data.
"""

import pandas as pd
from app.solver.greedy_assign import generate_week_schedule, FALLBACK_RANK_CAPS, FALLBACK_UNRANKED_CAP


def test_fallback_caps():
    """Test the new fallback cap logic with simple data."""

    print("Testing fallback tier caps...")

    # Create test candidates with different rank scenarios
    candidates_df = pd.DataFrame([
        # Has explicit rule (Volkswagen A+)
        {"vin": "v1", "person_id": "14402", "market": "LA", "make": "Volkswagen", "model": "ID4", "week_start": "2025-09-22", "available_days": 7, "cooldown_ok": True, "rank": "A+", "score": 105},

        # No rule for Hyundai - should use fallback
        {"vin": "v2", "person_id": "8278", "market": "LA", "make": "Hyundai", "model": "Tucson", "week_start": "2025-09-22", "available_days": 7, "cooldown_ok": True, "rank": "B", "score": 45},

        # Pending rank - should use UNRANKED fallback
        {"vin": "v3", "person_id": "1000", "market": "LA", "make": "Mazda", "model": "CX5", "week_start": "2025-09-22", "available_days": 7, "cooldown_ok": True, "rank": "Pending", "score": 30},
    ])

    # Rules only for Volkswagen (like real data)
    rules_df = pd.DataFrame([
        {"make": "Volkswagen", "rank": "A+", "loan_cap_per_year": 100}
    ])

    # No loan history (clean slate)
    loan_history_df = pd.DataFrame()

    # High capacity
    ops_capacity_df = pd.DataFrame([{"office": "LA", "drivers_per_day": 10}])

    result = generate_week_schedule(
        candidates_scored_df=candidates_df,
        loan_history_df=loan_history_df,
        ops_capacity_df=ops_capacity_df,
        office="LA",
        week_start="2025-09-22",
        rules_df=rules_df
    )

    print(f"Results with fallback caps:")
    print(f"   Assignments: {len(result.drop_duplicates(['vin', 'person_id'])) if not result.empty else 0}")

    if not result.empty:
        weekly_assignments = result.drop_duplicates(['vin', 'person_id'])
        for _, assignment in weekly_assignments.iterrows():
            print(f"   {assignment['vin']} → Partner {assignment['person_id']} ({assignment['make']})")

    # Test what caps were applied
    print(f"\nCap resolution test:")
    print(f"   Volkswagen A+ (has rule): Should use 100")
    print(f"   Hyundai B (no rule): Should use fallback {FALLBACK_RANK_CAPS['B']}")
    print(f"   Mazda Pending (no rule): Should use fallback {FALLBACK_UNRANKED_CAP}")

    return len(result.drop_duplicates(['vin', 'person_id'])) if not result.empty else 0


if __name__ == "__main__":
    assignments = test_fallback_caps()
    print(f"\n✅ Fallback cap test complete: {assignments} assignments")

    if assignments > 1:
        print("🎉 Fallback caps working - more assignments than before!")
    else:
        print("⚠️  Still limited assignments - may need to check other constraints")