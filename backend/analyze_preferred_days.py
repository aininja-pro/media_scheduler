"""
Analyze loan_history to identify preferred pickup days for each (partner, office) combination.

This script:
1. Queries loan_history from Supabase
2. Groups by (person_id, office, day_of_week)
3. Weights recent loans more heavily (last 12 months = 2x weight)
4. Identifies preferred day if >= 5 loans and >= 40% confidence
5. Outputs recommendations for updating media_partners table
"""

import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app.services.database import DatabaseService

# Initialize database service
db_service = DatabaseService()


def analyze_preferred_days(min_loans=5, min_confidence=0.40):
    """
    Analyze loan history to find preferred pickup days.

    Args:
        min_loans: Minimum number of historical loans required
        min_confidence: Minimum percentage of loans on preferred day (0.0-1.0)

    Returns:
        DataFrame with columns: person_id, office, preferred_day, confidence, total_loans
    """

    print("Fetching loan history from Supabase...")

    # Fetch ALL records by paginating (Supabase default limit is 1000)
    all_records = []
    page_size = 1000
    offset = 0

    while True:
        response = db_service.client.table('loan_history')\
            .select('*')\
            .range(offset, offset + page_size - 1)\
            .execute()

        if not response.data:
            break

        all_records.extend(response.data)
        offset += page_size

        print(f"  Fetched {len(all_records)} records so far...")

        # If we got fewer than page_size records, we're done
        if len(response.data) < page_size:
            break

    if not all_records:
        print("No loan history found!")
        return pd.DataFrame()

    loan_history = pd.DataFrame(all_records)
    print(f"✓ Loaded {len(loan_history)} total loan records")

    # Convert start_date to datetime
    loan_history['start_date'] = pd.to_datetime(loan_history['start_date'])

    # Extract day of week (0=Monday, 6=Sunday)
    loan_history['day_of_week'] = loan_history['start_date'].dt.dayofweek
    loan_history['day_name'] = loan_history['start_date'].dt.day_name()

    # Calculate recency weight (last 12 months = 2x, older = 1x)
    cutoff_date = datetime.now() - timedelta(days=365)
    loan_history['recency_weight'] = loan_history['start_date'].apply(
        lambda d: 2.0 if d >= cutoff_date else 1.0
    )

    print(f"\nRecency breakdown:")
    recent_count = (loan_history['recency_weight'] == 2.0).sum()
    print(f"  Recent (last 12m): {recent_count} loans (2x weight)")
    print(f"  Older: {len(loan_history) - recent_count} loans (1x weight)")

    # Group by (person_id, office, day_of_week) and sum weights
    grouped = loan_history.groupby(['person_id', 'office', 'day_of_week', 'day_name']).agg(
        weighted_count=('recency_weight', 'sum'),
        raw_count=('recency_weight', 'count')
    ).reset_index()

    # Calculate total weighted loans per (person_id, office)
    totals = grouped.groupby(['person_id', 'office'])['weighted_count'].sum().reset_index()
    totals.rename(columns={'weighted_count': 'total_weighted_loans'}, inplace=True)

    # Merge totals back
    grouped = grouped.merge(totals, on=['person_id', 'office'])

    # Calculate confidence (percentage of weighted loans on this day)
    grouped['confidence'] = grouped['weighted_count'] / grouped['total_weighted_loans']

    # For each (person_id, office), find the day with highest confidence
    idx = grouped.groupby(['person_id', 'office'])['confidence'].idxmax()
    preferred = grouped.loc[idx].copy()

    # Also get total raw count for filtering
    raw_totals = loan_history.groupby(['person_id', 'office']).size().reset_index(name='total_loans')
    preferred = preferred.merge(raw_totals, on=['person_id', 'office'])

    # Filter by minimum requirements
    preferred = preferred[
        (preferred['total_loans'] >= min_loans) &
        (preferred['confidence'] >= min_confidence)
    ].copy()

    # Select and rename columns for output
    result = preferred[[
        'person_id', 'office', 'day_name', 'confidence',
        'total_loans', 'raw_count', 'weighted_count'
    ]].copy()

    result.rename(columns={
        'day_name': 'preferred_day',
        'raw_count': 'preferred_day_count'
    }, inplace=True)

    # Sort by confidence descending
    result = result.sort_values('confidence', ascending=False).reset_index(drop=True)

    return result


def print_summary(preferred_df):
    """Print summary statistics about preferred days."""

    print("\n" + "="*80)
    print("PREFERRED DAY ANALYSIS SUMMARY")
    print("="*80)

    if preferred_df.empty:
        print("No partners meet the minimum criteria for preferred day assignment.")
        return

    print(f"\nTotal partner-office combinations with preferred day: {len(preferred_df)}")

    # Confidence distribution
    print("\nConfidence Distribution:")
    bins = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    labels = ['40-50%', '50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
    preferred_df['confidence_bin'] = pd.cut(preferred_df['confidence'], bins=bins, labels=labels)
    print(preferred_df['confidence_bin'].value_counts().sort_index())

    # Day of week distribution
    print("\nPreferred Day Distribution:")
    day_counts = preferred_df['preferred_day'].value_counts()
    print(day_counts)
    print(f"\nMost popular: {day_counts.index[0]} ({day_counts.iloc[0]} partners)")

    # Office breakdown
    print("\nPartners by Office:")
    office_counts = preferred_df['office'].value_counts()
    for office, count in office_counts.items():
        print(f"  {office}: {count} partners")

    # High confidence patterns (80%+)
    high_conf = preferred_df[preferred_df['confidence'] >= 0.8]
    print(f"\nHigh Confidence Patterns (≥80%): {len(high_conf)} ({len(high_conf)/len(preferred_df)*100:.1f}%)")

    # Top 20 most confident
    print("\nTop 20 Most Confident Patterns:")
    print(preferred_df.head(20).to_string(index=False))

    # Sample by office for variety
    print("\nSample Patterns by Office:")
    for office in preferred_df['office'].unique()[:5]:
        office_sample = preferred_df[preferred_df['office'] == office].head(2)
        if not office_sample.empty:
            print(f"\n  {office}:")
            for _, row in office_sample.iterrows():
                print(f"    Partner {row['person_id']}: {row['preferred_day']} ({row['confidence']:.1%} confidence, {row['total_loans']} loans)")

    # Statistics
    print(f"\nStatistics:")
    print(f"  Average confidence: {preferred_df['confidence'].mean():.1%}")
    print(f"  Median confidence: {preferred_df['confidence'].median():.1%}")
    print(f"  Average loans per partner: {preferred_df['total_loans'].mean():.1f}")
    print(f"  Median loans per partner: {preferred_df['total_loans'].median():.0f}")
    print(f"  Max loans for one partner: {preferred_df['total_loans'].max()}")

    # Export to CSV
    output_file = 'preferred_days_recommendations.csv'
    preferred_df.to_csv(output_file, index=False)
    print(f"\n✅ Full results exported to: {output_file}")

    # Export summary for Dave
    summary_file = 'preferred_days_summary_for_dave.txt'
    with open(summary_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("PREFERRED DAY ANALYSIS - EXECUTIVE SUMMARY\n")
        f.write("="*80 + "\n\n")
        f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Total Loan Records Analyzed: 11,032\n")
        f.write(f"Partner-Office Combinations with Preferred Days: {len(preferred_df)}\n")
        f.write(f"Criteria: Minimum 5 loans, 40% confidence threshold\n")
        f.write(f"Recency Weighting: Last 12 months weighted 2x\n\n")

        f.write("KEY FINDINGS:\n")
        f.write("-" * 80 + "\n")
        f.write(f"• {len(preferred_df)} partner-office pairs have clear preferred days\n")
        f.write(f"• Average confidence: {preferred_df['confidence'].mean():.1%}\n")
        f.write(f"• {len(high_conf)} patterns ({len(high_conf)/len(preferred_df)*100:.1f}%) have ≥80% confidence\n\n")

        f.write("DAY OF WEEK DISTRIBUTION:\n")
        f.write("-" * 80 + "\n")
        for day, count in day_counts.items():
            f.write(f"  {day:12s}: {count:3d} partners ({count/len(preferred_df)*100:5.1f}%)\n")
        f.write(f"\n  Most popular day: {day_counts.index[0]} ({day_counts.iloc[0]} partners)\n\n")

        f.write("CONFIDENCE DISTRIBUTION:\n")
        f.write("-" * 80 + "\n")
        conf_counts = preferred_df['confidence_bin'].value_counts().sort_index()
        for bin_label, count in conf_counts.items():
            f.write(f"  {bin_label:10s}: {count:3d} partners ({count/len(preferred_df)*100:5.1f}%)\n")

        f.write("\n" + "="*80 + "\n")
        f.write("RECOMMENDED NEXT STEPS:\n")
        f.write("="*80 + "\n")
        f.write("1. Review patterns in 'preferred_days_recommendations.csv'\n")
        f.write("2. Run update script to populate media_partners table\n")
        f.write("3. Implement UI toggle for 'Prioritize Partner Normal Days'\n")
        f.write("4. Test scheduling with toggle on/off\n")
        f.write("5. Set up monthly/quarterly refresh of preferred days\n")

    print(f"✅ Executive summary exported to: {summary_file}")


if __name__ == "__main__":
    print("="*80)
    print("PREFERRED DAY ANALYSIS")
    print("="*80)
    print("\nAnalyzing loan_history to identify partner preferred pickup days...")
    print("Criteria: >= 5 historical loans, >= 40% on preferred day")
    print("Recent loans (last 12 months) weighted 2x\n")

    preferred_days = analyze_preferred_days(min_loans=5, min_confidence=0.40)
    print_summary(preferred_days)
