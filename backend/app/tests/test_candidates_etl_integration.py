"""
Real ETL integration test for candidate generation using proper ETL endpoints.

This script uses the existing Phase 4 ETL endpoints that include proper:
- Vehicle lifecycle constraints (in_service_date, expected_turn_in_date)
- Activity blocking logic
- Cooldown calculations with rules
- Publication rate analytics
"""

import asyncio
import pandas as pd
import time
import httpx
from datetime import datetime, timedelta

from app.solver.candidates import build_weekly_candidates
from app.solver.scoring import compute_candidate_scores


async def fetch_etl_availability_data(office: str, week_start: str) -> pd.DataFrame:
    """Fetch availability data using the proper ETL endpoint."""
    print(f"Fetching ETL availability data for {office}, week starting {week_start}...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"http://localhost:8081/api/etl/availability",
                params={"office": office, "week_start": week_start}
            )

            if response.status_code != 200:
                print(f"ETL availability endpoint failed: {response.status_code} - {response.text}")
                return pd.DataFrame()

            data = response.json()

            # Convert ETL response to DataFrame format expected by build_weekly_candidates
            availability_records = []

            for row in data.get("rows", []):
                vin = row["vin"]
                make = row["make"]
                model = row.get("model", "")
                office_name = row["office"]
                availability_array = row["availability"]  # 7-day boolean array

                # Convert to individual date records
                week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
                for day_idx, available in enumerate(availability_array):
                    date_str = (week_start_date + timedelta(days=day_idx)).strftime('%Y-%m-%d')
                    availability_records.append({
                        'vin': vin,
                        'date': date_str,
                        'market': office_name,  # office = market
                        'make': make,
                        'model': model,
                        'available': available
                    })

            availability_df = pd.DataFrame(availability_records)
            print(f"✅ ETL Availability: {len(availability_df)} records from proper ETL endpoint")

            # Show availability stats
            if not availability_df.empty:
                total_vin_days = len(availability_df)
                available_vin_days = availability_df['available'].sum()
                availability_rate = available_vin_days / total_vin_days * 100
                unique_vins = availability_df['vin'].nunique()
                print(f"   - {unique_vins} vehicles, {available_vin_days}/{total_vin_days} VIN-days available ({availability_rate:.1f}%)")

            return availability_df

    except Exception as e:
        print(f"Error fetching ETL availability data: {e}")
        return pd.DataFrame()


async def fetch_etl_cooldown_data(week_start: str) -> pd.DataFrame:
    """
    Generate cooldown data using database logic.

    Note: Cooldown is computed within availability endpoint, but we need
    it in the format expected by build_weekly_candidates.
    """
    print(f"Computing ETL cooldown data for week starting {week_start}...")

    try:
        from app.services.database import db_service
        from app.etl.cooldown import compute_cooldown_flags

        # Get loan history to compute cooldowns
        loan_history_response = db_service.client.table('loan_history').select(
            'person_id, make, model, start_date, end_date'
        ).order('end_date', desc=True).execute()

        loan_history_df = pd.DataFrame(loan_history_response.data) if loan_history_response.data else pd.DataFrame()

        # Get rules for cooldown calculation
        rules_response = db_service.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

        if loan_history_df.empty:
            print("⚠️  No loan history data for cooldown calculation")
            return pd.DataFrame()

        # Convert date columns
        for date_col in ['start_date', 'end_date']:
            if date_col in loan_history_df.columns:
                loan_history_df[date_col] = pd.to_datetime(loan_history_df[date_col], errors='coerce').dt.date

        # Compute cooldown flags using existing ETL function
        cooldown_df = compute_cooldown_flags(
            loan_history_df=loan_history_df,
            rules_df=rules_df,
            week_start=week_start,
            default_days=60
        )

        print(f"✅ ETL Cooldown: {len(cooldown_df)} records computed with proper ETL logic")

        # Show cooldown stats
        if not cooldown_df.empty:
            cooldown_ok_count = cooldown_df['cooldown_ok'].sum()
            cooldown_rate = cooldown_ok_count / len(cooldown_df) * 100
            print(f"   - {cooldown_ok_count}/{len(cooldown_df)} partner-make pairs not in cooldown ({cooldown_rate:.1f}%)")

        return cooldown_df

    except Exception as e:
        print(f"Error computing ETL cooldown data: {e}")
        return pd.DataFrame()


async def fetch_etl_publication_data() -> pd.DataFrame:
    """Fetch publication rate data using the proper ETL endpoint."""
    print("Fetching ETL publication rate data...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"http://localhost:8081/api/etl/publication_rates",
                params={"window_months": 24, "min_observed": 3}
            )

            if response.status_code != 200:
                print(f"ETL publication rates endpoint failed: {response.status_code} - {response.text}")
                return pd.DataFrame()

            data = response.json()

            # Convert grains to DataFrame format expected by build_weekly_candidates
            publication_records = []
            for grain in data.get("grains", []):
                publication_records.append({
                    'person_id': grain['person_id'],
                    'make': grain['make'],
                    'loans_total_24m': grain['loans_total_24m'],
                    'loans_observed_24m': grain.get('loans_observed_24m', 0),
                    'publications_observed_24m': grain['publications_24m'],
                    'publication_rate_observed': grain['publication_rate'],
                    'coverage': 1.0 if grain['has_clip_data'] else 0.0,  # Convert has_clip_data to coverage
                    'supported': grain.get('supported', False)
                })

            publication_df = pd.DataFrame(publication_records)
            print(f"✅ ETL Publication: {len(publication_df)} records from proper ETL endpoint")

            # Show publication stats
            if not publication_df.empty:
                with_data_count = publication_df['coverage'].gt(0).sum()
                supported_count = publication_df['supported'].sum()
                avg_coverage = publication_df['coverage'].mean()
                print(f"   - {with_data_count}/{len(publication_df)} have publication data, {supported_count} supported")
                print(f"   - Average coverage: {avg_coverage:.1%}")

            return publication_df

    except Exception as e:
        print(f"Error fetching ETL publication data: {e}")
        return pd.DataFrame()


async def fetch_etl_eligibility_data() -> pd.DataFrame:
    """Fetch eligibility data from approved_makes table."""
    print("Fetching eligibility data from approved_makes...")

    try:
        # Use database service directly for this simple table fetch
        from app.services.database import db_service

        eligibility_response = db_service.client.table('approved_makes').select(
            'person_id, make, rank'
        ).execute()

        eligibility_df = pd.DataFrame(eligibility_response.data) if eligibility_response.data else pd.DataFrame()
        print(f"✅ Eligibility: {len(eligibility_df)} records from approved_makes table")

        return eligibility_df

    except Exception as e:
        print(f"Error fetching eligibility data: {e}")
        return pd.DataFrame()


async def fetch_etl_partner_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch partner rank and partner office data for scoring."""
    print("Fetching partner data for scoring...")

    try:
        from app.services.database import db_service

        # Fetch approved makes for rank data
        partner_rank_response = db_service.client.table('approved_makes').select(
            'person_id, make, rank'
        ).execute()
        partner_rank_df = pd.DataFrame(partner_rank_response.data) if partner_rank_response.data else pd.DataFrame()

        # Fetch media partners for geo bonus data
        partners_response = db_service.client.table('media_partners').select(
            'person_id, office, default_loan_region'
        ).execute()
        partners_df = pd.DataFrame(partners_response.data) if partners_response.data else pd.DataFrame()

        print(f"✅ Partner scoring data: {len(partner_rank_df)} ranks, {len(partners_df)} partners")

        return partner_rank_df, partners_df

    except Exception as e:
        print(f"Error fetching partner data: {e}")
        return pd.DataFrame(), pd.DataFrame()


async def test_etl_integration():
    """Test complete pipeline using proper ETL endpoints."""
    print("=" * 80)
    print("Testing Phase 5 with PROPER ETL ENDPOINTS (including vehicle lifecycle)")
    print("=" * 80)

    # Set up test parameters
    today = datetime.now()
    days_since_monday = today.weekday()
    current_monday = (today - timedelta(days=days_since_monday)).date()
    week_start = current_monday.strftime('%Y-%m-%d')
    office = "Los Angeles"

    print(f"\nTesting with office: {office}, week: {week_start}")

    # 1. Fetch all ETL data using proper endpoints
    print("\n" + "="*50)
    print("STEP 1: Fetching ETL Data")
    print("="*50)

    start_time = time.time()

    availability_df, cooldown_df, publication_df, eligibility_df = await asyncio.gather(
        fetch_etl_availability_data(office, week_start),
        fetch_etl_cooldown_data(week_start),
        fetch_etl_publication_data(),
        fetch_etl_eligibility_data()
    )

    etl_fetch_time = time.time() - start_time
    print(f"\n⏱️  ETL data fetch completed in {etl_fetch_time:.3f}s")

    # Validate we have data
    if availability_df.empty:
        print("❌ No availability data from ETL endpoint")
        return None

    if cooldown_df.empty:
        print("❌ No cooldown data from ETL endpoint")
        return None

    if publication_df.empty:
        print("❌ No publication data from ETL endpoint")
        return None

    # 2. Generate candidates using ETL data
    print("\n" + "="*50)
    print("STEP 2: Generating Candidates")
    print("="*50)

    start_time = time.time()

    candidates_df = build_weekly_candidates(
        availability_df=availability_df,
        cooldown_df=cooldown_df,
        publication_df=publication_df,
        week_start=week_start,
        eligibility_df=eligibility_df if not eligibility_df.empty else None,
        min_available_days=5  # Relaxed for testing
    )

    candidate_time = time.time() - start_time

    print(f"✅ Generated {len(candidates_df):,} candidates in {candidate_time:.3f}s")
    print(f"   - Performance: {len(candidates_df)/candidate_time:.0f} candidates/second")

    if candidates_df.empty:
        print("❌ No candidates generated - check ETL data constraints")
        return None

    # Analyze candidate generation results
    unique_vins = candidates_df['vin'].nunique()
    unique_partners = candidates_df['person_id'].nunique()
    avg_available_days = candidates_df['available_days'].mean()

    print(f"   - Unique VINs: {unique_vins}")
    print(f"   - Unique partners: {unique_partners}")
    print(f"   - Average available days: {avg_available_days:.1f}")

    # 3. Score candidates
    print("\n" + "="*50)
    print("STEP 3: Scoring Candidates")
    print("="*50)

    # Fetch partner data for scoring
    partner_rank_df, partners_df = await fetch_etl_partner_data()

    if partner_rank_df.empty or partners_df.empty:
        print("❌ Missing partner data for scoring")
        return None

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
    print(f"   - Performance: {len(scored_candidates)/scoring_time:.0f} candidates/second")

    # 4. Final Analysis
    print("\n" + "="*50)
    print("STEP 4: Analysis with PROPER ETL Data")
    print("="*50)

    print(f"📊 Candidate Analysis:")
    print(f"   - Total candidates: {len(scored_candidates):,}")
    print(f"   - Score range: {scored_candidates['score'].min()}-{scored_candidates['score'].max()}")
    print(f"   - Average score: {scored_candidates['score'].mean():.1f}")

    # Rank distribution
    rank_dist = scored_candidates['rank'].value_counts().sort_index()
    print(f"   - Rank distribution: {dict(rank_dist)}")

    # Bonus analysis
    geo_bonus_count = (scored_candidates['geo_bonus'] > 0).sum()
    history_bonus_count = (scored_candidates['history_bonus'] > 0).sum()
    geo_pct = geo_bonus_count / len(scored_candidates) * 100
    history_pct = history_bonus_count / len(scored_candidates) * 100

    print(f"   - Geo bonuses: {geo_bonus_count:,} ({geo_pct:.1f}%)")
    print(f"   - History bonuses: {history_bonus_count:,} ({history_pct:.1f}%)")

    # Top candidates
    print(f"\n🏆 Top 5 candidates:")
    top_candidates = scored_candidates.nlargest(5, 'score')
    for i, (_, row) in enumerate(top_candidates.iterrows(), 1):
        vin_short = str(row['vin'])[-8:] if len(str(row['vin'])) > 8 else row['vin']
        print(f"   {i}. {vin_short} + Partner {row['person_id']} ({row['make']}, Rank {row['rank']}) = {row['score']} pts")

    # Performance summary
    total_time = etl_fetch_time + candidate_time + scoring_time
    print(f"\n⚡ Performance Summary:")
    print(f"   - ETL fetch: {etl_fetch_time:.3f}s")
    print(f"   - Candidate generation: {candidate_time:.3f}s")
    print(f"   - Scoring: {scoring_time:.3f}s")
    print(f"   - Total: {total_time:.3f}s")

    print(f"\n✅ ETL Integration test completed successfully!")
    print(f"   Using PROPER vehicle lifecycle constraints from Phase 4 ETL!")

    return scored_candidates


async def main():
    """Run the ETL integration test."""
    try:
        result = await test_etl_integration()
        return result
    except Exception as e:
        print(f"❌ ETL integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(main())