"""
Test to investigate the 100% partner eligibility anomaly.
All 202 partners showing eligible seems suspicious.
"""

import pandas as pd
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.database import DatabaseService
import asyncio

async def analyze_partner_eligibility():
    """Analyze why all partners show as eligible."""

    # Initialize database
    db = DatabaseService()
    await db.initialize()

    # Get LA partners
    partners_response = db.client.table('media_partners').select('*').eq('office', 'Los Angeles').execute()
    partners_df = pd.DataFrame(partners_response.data)
    print(f"Total LA partners: {len(partners_df)}")

    # Get current activity to check partner availability
    activity_response = db.client.table('current_activity').select('*').execute()
    activity_df = pd.DataFrame(activity_response.data)

    # Check how many partners have active vehicles
    if 'person_id' in activity_df.columns:
        active_partners = activity_df['person_id'].dropna().unique()
        print(f"Partners with active vehicles: {len(active_partners)}")

        # Check which LA partners have active vehicles
        la_active = set(partners_df['person_id']) & set(active_partners)
        print(f"LA partners with active vehicles: {len(la_active)}")
        print(f"LA partners available (no active vehicle): {len(partners_df) - len(la_active)}")
    else:
        print("WARNING: person_id not found in current_activity table!")
        print("Available columns:", activity_df.columns.tolist())

    # Get approved makes for LA partners
    approved_response = db.client.table('approved_makes').select('*').execute()
    approved_df = pd.DataFrame(approved_response.data)

    # Filter to LA partners only
    la_partner_ids = set(partners_df['person_id'])
    la_approved = approved_df[approved_df['person_id'].isin(la_partner_ids)]

    print(f"\nApproved makes for LA partners:")
    print(f"Total approved make relationships: {len(la_approved)}")
    print(f"Unique LA partners with approvals: {la_approved['person_id'].nunique()}")

    # Check partner distribution by rank
    if 'rank' in la_approved.columns:
        rank_counts = la_approved['rank'].value_counts()
        print("\nRank distribution:")
        for rank, count in rank_counts.items():
            print(f"  {rank}: {count}")

    # Check for partners without any approved makes
    partners_with_approvals = set(la_approved['person_id'])
    partners_without_approvals = la_partner_ids - partners_with_approvals
    print(f"\nPartners without any approved makes: {len(partners_without_approvals)}")

    # Get loan history to check cooldowns
    loan_response = db.client.table('loan_history').select('*').execute()
    loan_df = pd.DataFrame(loan_response.data)

    # Check recent loans (last 60 days)
    if not loan_df.empty and 'end_date' in loan_df.columns:
        loan_df['end_date'] = pd.to_datetime(loan_df['end_date'])
        cutoff_date = pd.Timestamp('2024-09-22') - pd.Timedelta(days=60)
        recent_loans = loan_df[loan_df['end_date'] > cutoff_date]

        # LA partners with recent loans
        la_recent = recent_loans[recent_loans['person_id'].isin(la_partner_ids)]
        unique_partners_recent = la_recent['person_id'].nunique()
        print(f"\nLA partners with loans in last 60 days: {unique_partners_recent}")
        print(f"LA partners potentially in cooldown: {unique_partners_recent}")

        # Check tier cap status
        print("\nAnalyzing tier cap usage...")
        # Get rules for tier caps
        rules_response = db.client.table('rules').select('*').execute()
        rules_df = pd.DataFrame(rules_response.data)

        # Calculate loans in last 12 months
        cutoff_12m = pd.Timestamp('2024-09-22') - pd.Timedelta(days=365)
        loans_12m = loan_df[loan_df['end_date'] > cutoff_12m]

        # Count by partner and make
        if not loans_12m.empty:
            loan_counts = loans_12m.groupby(['person_id', 'make']).size().reset_index(name='loan_count')

            # Merge with ranks
            loan_counts = loan_counts.merge(
                la_approved[['person_id', 'make', 'rank']],
                on=['person_id', 'make'],
                how='left'
            )

            # Check against caps
            tier_caps = {'A+': 100, 'A': 70, 'B': 40, 'C': 10}
            over_cap = []
            for _, row in loan_counts.iterrows():
                rank = row['rank']
                if rank in tier_caps and row['loan_count'] >= tier_caps[rank]:
                    over_cap.append(row)

            if over_cap:
                print(f"Partners at or over tier cap: {len(over_cap)}")
                for item in over_cap[:5]:  # Show first 5
                    print(f"  {item['person_id']}: {item['make']} ({item['rank']}) - {item['loan_count']} loans")
            else:
                print("No partners at tier cap limits")

    # Summary
    print("\n=== ELIGIBILITY SUMMARY ===")
    print(f"Total LA partners: {len(partners_df)}")
    print(f"Partners with active vehicles: {len(la_active) if 'person_id' in activity_df.columns else 'Unknown'}")
    print(f"Partners without approved makes: {len(partners_without_approvals)}")
    print(f"Partners with recent loans (cooldown risk): {unique_partners_recent if 'unique_partners_recent' in locals() else 'Unknown'}")

    available_count = len(partners_df) - len(la_active) if 'person_id' in activity_df.columns else len(partners_df)
    print(f"\nExpected available partners: ~{available_count}")
    print("If UI shows all 202 as eligible, there's likely an issue with availability filtering")

    await db.close()

if __name__ == "__main__":
    asyncio.run(analyze_partner_eligibility())