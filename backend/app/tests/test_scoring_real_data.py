"""
Real data integration test for candidate scoring.

This script tests compute_candidate_scores against actual Supabase data
and integrates with the candidate generation from Step 1.
"""

import asyncio
import pandas as pd
import time

from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores
from app.services.database import db_service


async def fetch_scoring_data():
    """Fetch the required data for scoring from Supabase."""
    print("Fetching scoring data from Supabase...")

    try:
        # Fetch approved makes (partner ranks)
        partner_rank_response = db_service.client.table('approved_makes').select(
            'person_id, make, rank'
        ).execute()
        partner_rank_df = pd.DataFrame(partner_rank_response.data) if partner_rank_response.data else pd.DataFrame()
        print(f"Found {len(partner_rank_df)} partner rank records")

        # Fetch media partners (for geo bonus)
        partners_response = db_service.client.table('media_partners').select(
            'person_id, office, default_loan_region'
        ).execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()
        print(f"Found {len(partners_df)} partner records")

        return partner_rank_df, partners_df

    except Exception as e:
        print(f"Error fetching scoring data: {e}")
        return pd.DataFrame(), pd.DataFrame()


async def test_end_to_end_scoring():
    """Test complete pipeline: candidate generation → scoring with real data."""
    print("=" * 60)
    print("Testing candidate generation + scoring with REAL data")
    print("=" * 60)

    # Test database connection
    print("\n1. Testing database connection...")
    connection_ok = await db_service.test_connection()
    if not connection_ok:
        print("❌ Database connection failed!")
        return
    print("✅ Database connection successful")

    # Import and run the real data candidate generation test
    from app.tests.test_candidates_real_data import (
        fetch_availability_data,
        fetch_cooldown_data,
        fetch_publication_data,
        fetch_eligibility_data
    )

    # Generate candidates first (Step 1)
    print("\n2. Generating candidates...")
    from datetime import datetime, timedelta

    today = datetime.now()
    days_since_monday = today.weekday()
    current_monday = (today - timedelta(days=days_since_monday)).date()
    week_start = current_monday.strftime('%Y-%m-%d')
    office = "Los Angeles"

    availability_df, cooldown_df, publication_df, eligibility_df = await asyncio.gather(
        fetch_availability_data(office, week_start),
        fetch_cooldown_data(),
        fetch_publication_data(),
        fetch_eligibility_data()
    )

    if availability_df.empty:
        print("❌ No availability data found")
        return

    # Generate candidates
    start_time = time.time()
    candidates_df = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start=week_start,
        eligibility_df=eligibility_df if not eligibility_df.empty else None,
        min_available_days=5
    )
    candidate_time = time.time() - start_time

    print(f"✅ Generated {len(candidates_df):,} candidates in {candidate_time:.3f}s")

    if candidates_df.empty:
        print("❌ No candidates generated")
        return

    # Fetch scoring data (Step 2 requirements)
    print("\n3. Fetching scoring data...")
    partner_rank_df, partners_df = await fetch_scoring_data()

    if partner_rank_df.empty:
        print("❌ No partner rank data found")
        return

    if partners_df.empty:
        print("❌ No partner data found")
        return

    # Compute scores
    print("\n4. Computing candidate scores...")
    start_time = time.time()

    scored_candidates = compute_candidate_scores(
        candidates_df=candidates_df,
        partner_rank_df=partner_rank_df,
        partners_df=partners_df,
        publication_df=publication_df,
        rank_weights={"A+": 100, "A": 70, "B": 40, "C": 10},
        geo_bonus_points=10,
        history_bonus_points=5
    )

    scoring_time = time.time() - start_time

    print(f"✅ Scored {len(scored_candidates):,} candidates in {scoring_time:.3f}s")
    print(f"   Performance: {len(scored_candidates)/scoring_time:.0f} candidates/second")

    # Analyze scoring results
    print("\n5. Scoring Analysis:")
    print(f"   - Total candidates: {len(scored_candidates):,}")
    print(f"   - Score range: {scored_candidates['score'].min()}-{scored_candidates['score'].max()}")
    print(f"   - Average score: {scored_candidates['score'].mean():.1f}")

    # Rank distribution
    rank_dist = scored_candidates['rank'].value_counts().sort_index()
    print(f"   - Rank distribution: {dict(rank_dist)}")

    # Bonus distribution
    geo_bonus_count = (scored_candidates['geo_bonus'] > 0).sum()
    history_bonus_count = (scored_candidates['history_bonus'] > 0).sum()
    print(f"   - Geo bonuses: {geo_bonus_count:,} ({geo_bonus_count/len(scored_candidates)*100:.1f}%)")
    print(f"   - History bonuses: {history_bonus_count:,} ({history_bonus_count/len(scored_candidates)*100:.1f}%)")

    # Top scoring candidates
    print(f"\n6. Top 5 scoring candidates:")
    top_candidates = scored_candidates.nlargest(5, 'score')
    print("   VIN          Partner  Make     Rank  Score  (R+G+H)")
    print("   " + "-" * 50)
    for _, row in top_candidates.iterrows():
        vin_short = row['vin'][-8:] if len(str(row['vin'])) > 8 else row['vin']
        print(f"   {vin_short:<12} {row['person_id']:<8} {row['make']:<8} {row['rank']:<4} {row['score']:<5} ({row['rank_weight']}+{row['geo_bonus']}+{row['history_bonus']})")

    # Validate all expected columns exist
    print(f"\n7. Validation:")
    expected_new_cols = ["rank", "rank_weight", "geo_bonus", "history_bonus", "score"]
    missing_cols = [col for col in expected_new_cols if col not in scored_candidates.columns]

    if missing_cols:
        print(f"   ❌ Missing columns: {missing_cols}")
    else:
        print(f"   ✅ All scoring columns present: {expected_new_cols}")

    # Check data integrity
    original_count = len(candidates_df)
    scored_count = len(scored_candidates)

    if original_count == scored_count:
        print(f"   ✅ Row count preserved: {scored_count:,}")
    else:
        print(f"   ❌ Row count changed: {original_count:,} → {scored_count:,}")

    # Sample results
    print(f"\n8. Sample scored candidates (first 3):")
    sample_cols = ['vin', 'person_id', 'market', 'make', 'rank', 'geo_bonus', 'history_bonus', 'score']
    sample = scored_candidates[sample_cols].head(3)
    for col in sample.columns:
        if col == 'vin':
            sample[col] = sample[col].apply(lambda x: str(x)[-8:] if len(str(x)) > 8 else x)

    print(sample.to_string(index=False))

    print(f"\n✅ End-to-end scoring test completed successfully!")
    return scored_candidates


async def main():
    """Run the real data scoring integration test."""
    try:
        result = await test_end_to_end_scoring()
        return result
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(main())