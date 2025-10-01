"""
Update media_partners table with preferred_day_of_week based on loan_history analysis.

This script should be run periodically (monthly/quarterly) or on-demand to refresh
preferred days based on the latest loan history data.

Usage:
    python update_preferred_days.py [--min-loans 5] [--min-confidence 0.40] [--dry-run]
"""

import pandas as pd
import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app.services.database import DatabaseService
from analyze_preferred_days import analyze_preferred_days

# Initialize database service
db_service = DatabaseService()


def update_media_partners_preferred_days(preferred_df, dry_run=False):
    """
    Update media_partners table with preferred_day_of_week.

    Args:
        preferred_df: DataFrame with person_id, office, preferred_day, confidence
        dry_run: If True, only print what would be updated without making changes

    Returns:
        Number of records updated
    """

    if preferred_df.empty:
        print("No preferred days to update.")
        return 0

    print(f"\n{'DRY RUN - ' if dry_run else ''}Updating media_partners table...")
    print(f"Partners to update: {len(preferred_df)}")

    updated_count = 0

    for _, row in preferred_df.iterrows():
        person_id = row['person_id']
        office = row['office']
        preferred_day = row['preferred_day']
        confidence = row['confidence']

        if dry_run:
            print(f"  [DRY RUN] Would update person_id={person_id}, office={office} → {preferred_day} ({confidence:.1%} confidence)")
        else:
            try:
                # Update the media_partners table
                # Note: We assume there's one record per (person_id, office) or we update all matches
                response = db_service.client.table('media_partners').update({
                    'preferred_day_of_week': preferred_day,
                    'preferred_day_confidence': round(confidence * 100, 1)  # Store as percentage
                }).eq('person_id', person_id).eq('office', office).execute()

                if response.data:
                    updated_count += len(response.data)
                    print(f"  ✓ Updated person_id={person_id}, office={office} → {preferred_day} ({confidence:.1%})")
                else:
                    print(f"  ⚠ No record found for person_id={person_id}, office={office}")

            except Exception as e:
                print(f"  ✗ Error updating person_id={person_id}, office={office}: {e}")

    return updated_count


def clear_all_preferred_days(dry_run=False):
    """
    Clear all preferred_day_of_week values (set to NULL).
    Useful for testing or resetting.

    Args:
        dry_run: If True, only print what would be done

    Returns:
        Number of records cleared
    """

    if dry_run:
        print("\n[DRY RUN] Would clear all preferred_day_of_week values")
        return 0

    print("\nClearing all preferred_day_of_week values...")

    try:
        # Update all records to NULL
        response = db_service.client.table('media_partners').update({
            'preferred_day_of_week': None,
            'preferred_day_confidence': None
        }).neq('person_id', '0').execute()  # neq with impossible value = update all

        count = len(response.data) if response.data else 0
        print(f"✓ Cleared {count} records")
        return count

    except Exception as e:
        print(f"✗ Error clearing preferred days: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Update preferred days in media_partners table')
    parser.add_argument('--min-loans', type=int, default=5,
                       help='Minimum number of historical loans required (default: 5)')
    parser.add_argument('--min-confidence', type=float, default=0.40,
                       help='Minimum confidence threshold 0.0-1.0 (default: 0.40)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be updated without making changes')
    parser.add_argument('--clear', action='store_true',
                       help='Clear all preferred days first (use with caution!)')

    args = parser.parse_args()

    print("="*80)
    print("UPDATE PREFERRED DAYS IN MEDIA_PARTNERS")
    print("="*80)
    print(f"\nParameters:")
    print(f"  Min loans: {args.min_loans}")
    print(f"  Min confidence: {args.min_confidence:.0%}")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Clear existing: {args.clear}")

    # Optional: Clear existing values first
    if args.clear:
        if args.dry_run:
            print("\n[DRY RUN] Would clear existing preferred days")
        else:
            confirm = input("\n⚠️  Clear ALL existing preferred days? (yes/no): ")
            if confirm.lower() == 'yes':
                clear_all_preferred_days(dry_run=False)
            else:
                print("Skipping clear operation.")

    # Analyze loan history
    print("\n" + "="*80)
    print("ANALYZING LOAN HISTORY")
    print("="*80)

    preferred_df = analyze_preferred_days(
        min_loans=args.min_loans,
        min_confidence=args.min_confidence
    )

    if preferred_df.empty:
        print("\n⚠️  No partners meet the criteria. No updates will be made.")
        return

    print(f"\nFound {len(preferred_df)} partner-office combinations with preferred days")
    print(f"Average confidence: {preferred_df['confidence'].mean():.1%}")

    # Update database
    print("\n" + "="*80)
    print("UPDATING DATABASE")
    print("="*80)

    updated_count = update_media_partners_preferred_days(preferred_df, dry_run=args.dry_run)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    if args.dry_run:
        print(f"[DRY RUN] Would update {len(preferred_df)} records")
    else:
        print(f"✓ Successfully updated {updated_count} records")
        print(f"\nTo see the results, query media_partners where preferred_day_of_week IS NOT NULL")


if __name__ == "__main__":
    main()
