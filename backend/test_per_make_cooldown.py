"""
Test that cooldown is per-make - partner blocked for Toyota should still get Honda.
"""

import asyncio
import pandas as pd
from app.services.database import db_service
from app.etl.cooldown import compute_cooldown_flags


async def test_per_make_cooldown():
    """Test that cooldown is enforced per-make, not per-partner."""

    print("=" * 60)
    print("Testing Per-Make Cooldown Logic")
    print("=" * 60)

    week_start = "2025-09-22"

    # Get some real loan history to analyze
    loan_response = db_service.client.table('loan_history').select(
        'person_id, make, model, start_date, end_date'
    ).limit(100).execute()  # Just sample for analysis

    loan_df = pd.DataFrame(loan_response.data) if loan_response.data else pd.DataFrame()

    if loan_df.empty:
        print("❌ No loan history data")
        return

    # Convert dates
    for date_col in ['start_date', 'end_date']:
        if date_col in loan_df.columns:
            loan_df[date_col] = pd.to_datetime(loan_df[date_col], errors='coerce').dt.date

    rules_response = db_service.client.table('rules').select('*').execute()
    rules_df = pd.DataFrame(rules_response.data) if rules_response.data else pd.DataFrame()

    # Compute cooldown flags
    cooldown_df = compute_cooldown_flags(
        loan_history_df=loan_df,
        rules_df=rules_df,
        week_start=week_start,
        default_days=60
    )

    if cooldown_df.empty:
        print("❌ No cooldown data computed")
        return

    print(f"Analyzing cooldown for sample partners...")

    # Look at partners who have multiple makes
    partner_make_counts = cooldown_df.groupby('person_id')['make'].count().sort_values(ascending=False)

    print(f"\nPartners with multiple makes (should have different cooldown status per make):")

    for person_id in partner_make_counts.head(5).index:
        partner_cooldowns = cooldown_df[cooldown_df['person_id'] == person_id]

        print(f"\n📋 Partner {person_id}:")
        for _, row in partner_cooldowns.iterrows():
            status = "AVAILABLE" if row['cooldown_ok'] else "BLOCKED"
            cooldown_until = row['cooldown_until'].strftime('%Y-%m-%d') if pd.notna(row['cooldown_until']) else "N/A"
            print(f"   {row['make']}: {status} (until {cooldown_until})")

    # Check if any partner has mixed cooldown status (some makes available, others blocked)
    mixed_partners = []
    for person_id in partner_make_counts.index:
        partner_cooldowns = cooldown_df[cooldown_df['person_id'] == person_id]
        available_count = partner_cooldowns['cooldown_ok'].sum()
        total_count = len(partner_cooldowns)

        if 0 < available_count < total_count:  # Some available, some blocked
            mixed_partners.append({
                'person_id': person_id,
                'available': available_count,
                'total': total_count
            })

    if mixed_partners:
        print(f"\n🎯 Partners with MIXED cooldown status (proves per-make logic works):")
        for partner in mixed_partners[:3]:
            print(f"   Partner {partner['person_id']}: {partner['available']}/{partner['total']} makes available")
    else:
        print(f"\n⚠️  No partners found with mixed cooldown status")
        print(f"   This could mean:")
        print(f"   - All partners had recent loans across ALL their approved makes, OR")
        print(f"   - All partners have no recent loans for ANY of their makes")

    # Overall cooldown stats
    total_combinations = len(cooldown_df)
    available_combinations = cooldown_df['cooldown_ok'].sum()
    blocked_combinations = total_combinations - available_combinations

    print(f"\n📊 Overall Cooldown Stats:")
    print(f"   - Total partner-make combinations: {total_combinations}")
    print(f"   - Available: {available_combinations} ({available_combinations/total_combinations*100:.1f}%)")
    print(f"   - Blocked: {blocked_combinations} ({blocked_combinations/total_combinations*100:.1f}%)")

    print(f"\n✅ Per-make cooldown analysis complete")


if __name__ == "__main__":
    asyncio.run(test_per_make_cooldown())