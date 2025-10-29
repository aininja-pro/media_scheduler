"""
Script to review and export Phase 7 table data for client review.

This helps you verify the migration and prepare data for client validation.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from app.services.database import DatabaseService


async def review_phase7_migration():
    """Review the migrated data in Phase 7 tables."""

    db = DatabaseService()
    await db.initialize()

    print("=" * 80)
    print("PHASE 7 DATA MIGRATION REVIEW")
    print("=" * 80)

    # 1. Review ops_capacity vs ops_capacity_calendar
    print("\n1. OPS CAPACITY COMPARISON")
    print("-" * 40)

    # Get original ops_capacity
    ops_orig_response = db.client.table('ops_capacity').select('*').execute()
    ops_orig_df = pd.DataFrame(ops_orig_response.data)

    print(f"Original ops_capacity table: {len(ops_orig_df)} offices")
    for _, row in ops_orig_df.iterrows():
        print(f"  {row['office']}: {row['drivers_per_day']} drivers/day")

    # Get new ops_capacity_calendar
    ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
    ops_cal_df = pd.DataFrame(ops_cal_response.data)

    if not ops_cal_df.empty:
        print(f"\nNew ops_capacity_calendar: {len(ops_cal_df)} total entries")

        # Group by office
        by_office = ops_cal_df.groupby('office').agg({
            'slots': ['mean', 'min', 'max'],
            'date': ['min', 'max', 'count']
        })

        print("\nCalendar summary by office:")
        for office in by_office.index:
            stats = by_office.loc[office]
            print(f"  {office}:")
            print(f"    Date range: {stats[('date', 'min')]} to {stats[('date', 'max')]}")
            print(f"    Days configured: {stats[('date', 'count')]}")
            print(f"    Slots: avg={stats[('slots', 'mean')]:.1f}, min={stats[('slots', 'min')]}, max={stats[('slots', 'max')]}")

    # 2. Review model_taxonomy
    print("\n2. MODEL TAXONOMY REVIEW")
    print("-" * 40)

    taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
    taxonomy_df = pd.DataFrame(taxonomy_response.data)

    if not taxonomy_df.empty:
        print(f"Total models classified: {len(taxonomy_df)}")

        # Class distribution
        print("\nVehicle class distribution:")
        class_counts = taxonomy_df['short_model_class'].value_counts()
        for class_name, count in class_counts.items():
            print(f"  {class_name}: {count} models")

        # Powertrain distribution
        print("\nPowertrain distribution:")
        power_counts = taxonomy_df['powertrain'].value_counts()
        for power_type, count in power_counts.items():
            print(f"  {power_type}: {count} models")

        # Makes covered
        print(f"\nMakes covered: {taxonomy_df['make'].nunique()}")
        makes_list = sorted(taxonomy_df['make'].unique())[:10]
        print(f"  First 10: {', '.join(makes_list)}")

    # 3. Check for gaps in vehicle coverage
    print("\n3. VEHICLE COVERAGE CHECK")
    print("-" * 40)

    vehicles_response = db.client.table('vehicles').select('make, model').execute()
    vehicles_df = pd.DataFrame(vehicles_response.data)

    if not vehicles_df.empty:
        # Find vehicles without taxonomy
        vehicles_unique = vehicles_df.drop_duplicates(subset=['make', 'model'])

        if not taxonomy_df.empty:
            # Merge to find gaps
            merged = vehicles_unique.merge(
                taxonomy_df[['make', 'model']],
                on=['make', 'model'],
                how='left',
                indicator=True
            )

            missing = merged[merged['_merge'] == 'left_only']

            print(f"Vehicles in fleet: {len(vehicles_unique)}")
            print(f"Vehicles with taxonomy: {len(vehicles_unique) - len(missing)}")
            print(f"Vehicles MISSING taxonomy: {len(missing)}")

            if len(missing) > 0:
                print("\nFirst 20 vehicles needing classification:")
                for _, row in missing.head(20).iterrows():
                    print(f"  {row['make']} {row['model']}")

    # 4. Export for client review
    print("\n4. EXPORTING DATA FOR CLIENT REVIEW")
    print("-" * 40)

    # Export ops_capacity_calendar for next 30 days
    if not ops_cal_df.empty:
        ops_cal_df['date'] = pd.to_datetime(ops_cal_df['date'])
        next_30_days = ops_cal_df[
            ops_cal_df['date'] <= datetime.now() + timedelta(days=30)
        ].sort_values(['office', 'date'])

        next_30_days.to_csv('ops_capacity_calendar_review.csv', index=False)
        print(f"✓ Exported ops_capacity_calendar_review.csv ({len(next_30_days)} rows)")

    # Export model_taxonomy
    if not taxonomy_df.empty:
        taxonomy_sorted = taxonomy_df.sort_values(['make', 'model'])
        taxonomy_sorted.to_csv('model_taxonomy_review.csv', index=False)
        print(f"✓ Exported model_taxonomy_review.csv ({len(taxonomy_sorted)} rows)")

    # Export missing vehicles
    if len(missing) > 0:
        missing[['make', 'model']].to_csv('vehicles_needing_taxonomy.csv', index=False)
        print(f"✓ Exported vehicles_needing_taxonomy.csv ({len(missing)} vehicles)")

    # 5. Generate update templates
    print("\n5. UPDATE TEMPLATES FOR CLIENT")
    print("-" * 40)

    # Create template for capacity overrides
    template_capacity = pd.DataFrame({
        'office': ['Los Angeles'] * 5 + ['Denver'] * 5,
        'date': pd.date_range('2025-10-01', periods=5).tolist() * 2,
        'slots': [15, 15, 10, 15, 15] * 2,  # Example with one reduced day
        'notes': ['Normal'] * 2 + ['Staff meeting - reduced'] + ['Normal'] * 7
    })
    template_capacity.to_csv('template_capacity_overrides.csv', index=False)
    print("✓ Created template_capacity_overrides.csv")

    # Create template for missing taxonomy
    if len(missing) > 0:
        template_taxonomy = missing[['make', 'model']].head(50).copy()
        template_taxonomy['short_model_class'] = '??? (Sedan/SUV/Truck/Van/Coupe)'
        template_taxonomy['powertrain'] = '??? (Gas/Hybrid/EV/PHEV/Diesel)'
        template_taxonomy['notes'] = 'Please classify'
        template_taxonomy.to_csv('template_taxonomy_updates.csv', index=False)
        print("✓ Created template_taxonomy_updates.csv")

    await db.close()

    print("\n" + "=" * 80)
    print("REVIEW COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review the exported CSV files with your client")
    print("2. Get corrections for any misclassified vehicles")
    print("3. Identify special dates needing capacity adjustments")
    print("4. Upload corrected data via /ingest endpoints")


async def check_data_quality():
    """Check for common data quality issues."""

    db = DatabaseService()
    await db.initialize()

    print("\n" + "=" * 80)
    print("DATA QUALITY CHECKS")
    print("=" * 80)

    # Check for duplicate make/model with different classifications
    taxonomy_response = db.client.table('model_taxonomy').select('*').execute()
    taxonomy_df = pd.DataFrame(taxonomy_response.data)

    if not taxonomy_df.empty:
        duplicates = taxonomy_df[taxonomy_df.duplicated(subset=['make', 'model'], keep=False)]
        if not duplicates.empty:
            print("\n⚠️  WARNING: Duplicate make/model entries found:")
            print(duplicates[['make', 'model', 'short_model_class', 'powertrain']])

    # Check for gaps in calendar
    ops_cal_response = db.client.table('ops_capacity_calendar').select('*').execute()
    ops_cal_df = pd.DataFrame(ops_cal_response.data)

    if not ops_cal_df.empty:
        ops_cal_df['date'] = pd.to_datetime(ops_cal_df['date'])

        for office in ops_cal_df['office'].unique():
            office_data = ops_cal_df[ops_cal_df['office'] == office].sort_values('date')

            # Check for gaps
            dates = pd.to_datetime(office_data['date'])
            date_range = pd.date_range(dates.min(), dates.max())
            missing_dates = date_range.difference(dates)

            if len(missing_dates) > 0:
                print(f"\n⚠️  {office} has {len(missing_dates)} missing dates in calendar")
                if len(missing_dates) <= 10:
                    for date in missing_dates[:10]:
                        print(f"    Missing: {date.date()}")

    await db.close()


if __name__ == "__main__":
    print("Running Phase 7 data migration review...")
    asyncio.run(review_phase7_migration())

    print("\nRunning data quality checks...")
    asyncio.run(check_data_quality())