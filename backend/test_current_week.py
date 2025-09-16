#!/usr/bin/env python3
"""
Test availability grid for current week (Sept 9-15, 2025).
Today is Sunday, Sept 14th, 2025.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import asyncio
from datetime import date
from app.etl.availability import build_availability_grid
from app.services.database import db_service

async def test_current_week():
    """Test availability for this week (Sept 9-15, 2025)."""

    print("🔌 Fetching real data from Supabase...")

    # Fetch vehicles data
    vehicles_response = db_service.client.table('vehicles').select('*').execute()
    vehicles_df = pd.DataFrame(vehicles_response.data)
    print(f"📋 Found {len(vehicles_df)} vehicles")

    # Fetch current activity data
    activity_response = db_service.client.table('current_activity').select('*').execute()
    if activity_response.data:
        activity_df = pd.DataFrame(activity_response.data)
        if 'vehicle_vin' in activity_df.columns:
            activity_df['vin'] = activity_df['vehicle_vin']
        print(f"🔧 Found {len(activity_df)} current activities")
    else:
        activity_df = pd.DataFrame()
        print("⚠️ No current activities found")

    # Convert date columns
    for date_col in ['in_service_date', 'expected_turn_in_date']:
        if date_col in vehicles_df.columns:
            vehicles_df[date_col] = pd.to_datetime(vehicles_df[date_col], errors='coerce').dt.date

    if not activity_df.empty:
        for date_col in ['start_date', 'end_date']:
            if date_col in activity_df.columns:
                activity_df[date_col] = pd.to_datetime(activity_df[date_col], errors='coerce').dt.date

    print("\n📋 Vehicle lifecycle windows (sample):")
    for _, v in vehicles_df.head(8).iterrows():
        in_svc = v.get('in_service_date', 'None')
        turn_in = v.get('expected_turn_in_date', 'None')
        office = v.get('office', 'Unknown')
        print(f"   {office}: {v['vin'][-8:]} | {in_svc} → {turn_in}")

    # Current week: Monday Sept 9, 2025 (today is Sunday Sept 14)
    current_week = "2025-09-09"  # Monday
    print(f"\n🎯 Testing current week: {current_week} to 2025-09-15")
    print(f"📅 Today is Sunday, Sept 14th, 2025")

    # Test each office
    offices = vehicles_df['office'].value_counts()
    print(f"\n🏢 Offices found: {dict(offices)}")

    for office_name, vehicle_count in offices.items():
        print(f"\n{'='*50}")
        print(f"🏢 TESTING OFFICE: {office_name}")
        print(f"📊 {vehicle_count} vehicles in this office")

        result = build_availability_grid(
            vehicles_df=vehicles_df,
            activity_df=activity_df,
            week_start=current_week,
            office=office_name
        )

        # Calculate summary
        total_available = result['available'].sum()
        total_slots = len(result)
        availability_rate = (total_available / total_slots * 100) if total_slots > 0 else 0

        print(f"   📊 Grid shape: {result.shape}")
        print(f"   ✅ Available VIN-days: {total_available}")
        print(f"   ❌ Blocked VIN-days: {total_slots - total_available}")
        print(f"   📈 Availability rate: {availability_rate:.1f}%")

        if total_available > 0:
            # Show today's availability (Sunday, Sept 14)
            today = date(2025, 9, 14)
            today_available = result[
                (result['day'] == today) &
                (result['available'] == True)
            ]

            print(f"\n   📅 Available TODAY (Sunday, Sept 14):")
            if len(today_available) > 0:
                for _, row in today_available.iterrows():
                    print(f"      ✅ {row['vin'][-8:]} ({vehicles_df[vehicles_df['vin']==row['vin']]['make'].iloc[0]})")
            else:
                print(f"      ❌ No vehicles available today")

            # Show Monday availability (tomorrow for scheduling)
            monday = date(2025, 9, 9)
            monday_available = result[
                (result['day'] == monday) &
                (result['available'] == True)
            ]

            print(f"\n   📅 Were available MONDAY (Sept 9 - start of week):")
            if len(monday_available) > 0:
                for _, row in monday_available.iterrows():
                    print(f"      ✅ {row['vin'][-8:]} ({vehicles_df[vehicles_df['vin']==row['vin']]['make'].iloc[0]})")
            else:
                print(f"      ❌ No vehicles available Monday")

        else:
            # Analyze why no vehicles are available
            office_vehicles = vehicles_df[vehicles_df['office'] == office_name]
            print(f"\n   🔍 Why no availability? Checking constraints...")

            for _, v in office_vehicles.head(3).iterrows():
                vin_short = v['vin'][-8:]
                in_svc = v.get('in_service_date')
                turn_in = v.get('expected_turn_in_date')
                sept_14 = date(2025, 9, 14)

                constraints = []
                if in_svc and sept_14 < in_svc:
                    constraints.append(f"Not in service until {in_svc}")
                elif turn_in and sept_14 > turn_in:
                    constraints.append(f"Turned in on {turn_in}")

                # Check for activities
                vin_activities = activity_df[activity_df['vin'] == v['vin']]
                for _, act in vin_activities.iterrows():
                    start = act.get('start_date')
                    end = act.get('end_date')
                    if start and end and start <= sept_14 <= end:
                        constraints.append(f"{act.get('activity_type', 'Activity')} until {end}")

                status = " | ".join(constraints) if constraints else "Available (check logic)"
                print(f"      {vin_short}: {status}")

    print(f"\n🎉 CURRENT WEEK AVAILABILITY TEST COMPLETE!")

if __name__ == "__main__":
    asyncio.run(test_current_week())