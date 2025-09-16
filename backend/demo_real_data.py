#!/usr/bin/env python3
"""
Demo script using REAL data from Supabase tables.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from datetime import date
from app.etl.availability import build_availability_grid
from app.services.database import db_service

async def fetch_real_data_demo():
    """Fetch real data from Supabase and run availability grid."""

    print("🔌 Connecting to Supabase...")

    try:
        # Test connection first
        is_connected = await db_service.test_connection()
        if not is_connected:
            print("❌ Database connection failed")
            return

        print("✅ Connected to Supabase!")

        # Fetch vehicles data
        print("\n📋 Fetching vehicles data...")
        vehicles_response = db_service.client.table('vehicles').select('*').limit(10).execute()
        if not vehicles_response.data:
            print("❌ No vehicles data found")
            return

        vehicles_df = pd.DataFrame(vehicles_response.data)
        print(f"📊 Found {len(vehicles_df)} vehicles")
        print(f"🏢 Offices: {vehicles_df['office'].unique().tolist()}")
        print(f"🔑 Sample VINs: {vehicles_df['vin'].head(3).tolist()}")

        # Fetch current activity data
        print("\n🔧 Fetching current activity data...")
        activity_response = db_service.client.table('current_activity').select('*').limit(20).execute()

        if activity_response.data:
            activity_df = pd.DataFrame(activity_response.data)
            print(f"📊 Found {len(activity_df)} activities")
            print(f"🎯 Activity types: {activity_df['activity_type'].unique().tolist()}")

            # Map activity column names to match our function expectations
            if 'vehicle_vin' in activity_df.columns:
                activity_df['vin'] = activity_df['vehicle_vin']
        else:
            print("⚠️ No activity data found - creating empty DataFrame")
            activity_df = pd.DataFrame()

        # Show sample of real data
        print("\n=== REAL VEHICLES DATA (sample) ===")
        display_cols = ['vin', 'make', 'model', 'office', 'in_service_date', 'expected_turn_in_date']
        available_cols = [col for col in display_cols if col in vehicles_df.columns]
        print(vehicles_df[available_cols].head())

        if not activity_df.empty:
            print("\n=== REAL ACTIVITY DATA (sample) ===")
            activity_display_cols = ['vin', 'activity_type', 'start_date', 'end_date']
            available_activity_cols = [col for col in activity_display_cols if col in activity_df.columns]
            print(activity_df[available_activity_cols].head())

        # Pick an office that has vehicles
        office_counts = vehicles_df['office'].value_counts()
        target_office = office_counts.index[0]  # Office with most vehicles
        office_vehicle_count = office_counts.iloc[0]

        print(f"\n🎯 Running availability grid for office: {target_office}")
        print(f"📊 {office_vehicle_count} vehicles in this office")

        # Convert date columns if they're strings
        for date_col in ['in_service_date', 'expected_turn_in_date']:
            if date_col in vehicles_df.columns:
                vehicles_df[date_col] = pd.to_datetime(vehicles_df[date_col], errors='coerce').dt.date

        if not activity_df.empty:
            for date_col in ['start_date', 'end_date']:
                if date_col in activity_df.columns:
                    activity_df[date_col] = pd.to_datetime(activity_df[date_col], errors='coerce').dt.date

        # Run availability grid for next week
        week_start = "2025-01-20"  # Monday
        print(f"📅 Week: {week_start} to 2025-01-26")

        result = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=week_start,
            office=target_office
        )

        print(f"\n📊 AVAILABILITY GRID RESULTS:")
        print(f"   Shape: {result.shape}")
        print(f"   Expected rows: {office_vehicle_count} VINs × 7 days = {office_vehicle_count * 7}")

        # Show summary
        total_available = result['available'].sum()
        total_slots = len(result)
        availability_rate = (total_available / total_slots * 100) if total_slots > 0 else 0

        print(f"\n📈 SUMMARY:")
        print(f"   ✅ Available VIN-days: {total_available}")
        print(f"   ❌ Blocked VIN-days: {total_slots - total_available}")
        print(f"   📊 Availability rate: {availability_rate:.1f}%")

        # Show first few rows of actual results
        print(f"\n📅 FIRST 10 ROWS OF REAL AVAILABILITY DATA:")
        print(result.head(10).to_string(index=False))

        # Group by VIN to show per-vehicle availability
        print(f"\n🚗 PER-VEHICLE AVAILABILITY:")
        vin_summary = result.groupby('vin')['available'].agg(['sum', 'count']).reset_index()
        vin_summary['availability_rate'] = (vin_summary['sum'] / vin_summary['count'] * 100).round(1)
        vin_summary.columns = ['VIN', 'Available Days', 'Total Days', 'Availability %']
        print(vin_summary.head(10).to_string(index=False))


    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fetch_real_data_demo())