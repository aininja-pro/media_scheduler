#!/usr/bin/env python3
"""
Demo script to show what build_availability_grid returns.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
from datetime import date
from app.etl.availability import build_availability_grid

# Create sample data
vehicles_df = pd.DataFrame([
    {
        'vin': 'VIN001',
        'make': 'Toyota',
        'model': 'Camry',
        'office': 'Austin',
        'in_service_date': None,
        'expected_turn_in_date': date(2025, 1, 16)  # Thursday
    },
    {
        'vin': 'VIN002',
        'make': 'Honda',
        'model': 'Accord',
        'office': 'Austin',
        'in_service_date': date(2025, 1, 14),  # Tuesday
        'expected_turn_in_date': None
    },
    {
        'vin': 'VIN003',
        'make': 'Ford',
        'model': 'F-150',
        'office': 'Austin',
        'in_service_date': None,
        'expected_turn_in_date': None
    }
])

# Create sample activity data
activity_df = pd.DataFrame([
    {
        'vin': 'VIN003',
        'activity_type': 'service',
        'start_date': date(2025, 1, 15),  # Wednesday
        'end_date': date(2025, 1, 16)     # Thursday
    }
])

print("=== SAMPLE INPUT DATA ===")
print("\n📋 VEHICLES:")
print(vehicles_df[['vin', 'make', 'model', 'office', 'in_service_date', 'expected_turn_in_date']])

print("\n🔧 ACTIVITIES:")
print(activity_df)

print("\n=== AVAILABILITY GRID OUTPUT ===")

# Generate availability grid for week starting Monday 2025-01-13
result = build_availability_grid(
    vehicles_df=vehicles_df,
    activity_df=activity_df,
    week_start="2025-01-13",  # Monday
    office="Austin"
)

print(f"\n📊 OUTPUT SHAPE: {result.shape} (rows × columns)")
print(f"   Expected: {len(vehicles_df)} VINs × 7 days = {len(vehicles_df) * 7} rows")

print("\n📅 FULL AVAILABILITY GRID:")
print(result.to_string(index=False))

print("\n=== SUMMARY BY VIN ===")
for vin in result['vin'].unique():
    vin_data = result[result['vin'] == vin]
    available_days = vin_data[vin_data['available'] == True]['day'].tolist()
    blocked_days = vin_data[vin_data['available'] == False]['day'].tolist()

    print(f"\n🚗 {vin}:")
    print(f"   ✅ Available: {len(available_days)} days - {[d.strftime('%a %m/%d') for d in available_days]}")
    print(f"   ❌ Blocked:   {len(blocked_days)} days - {[d.strftime('%a %m/%d') for d in blocked_days]}")

    # Show reasons for blocking
    vehicle_info = vehicles_df[vehicles_df['vin'] == vin].iloc[0]
    vin_activities = activity_df[activity_df['vin'] == vin]

    reasons = []
    if pd.notna(vehicle_info['expected_turn_in_date']):
        reasons.append(f"Turn-in: {vehicle_info['expected_turn_in_date'].strftime('%a %m/%d')}")
    if pd.notna(vehicle_info['in_service_date']):
        reasons.append(f"In-service: {vehicle_info['in_service_date'].strftime('%a %m/%d')}")
    if not vin_activities.empty:
        for _, act in vin_activities.iterrows():
            reasons.append(f"{act['activity_type'].title()}: {act['start_date'].strftime('%m/%d')}-{act['end_date'].strftime('%m/%d')}")

    if reasons:
        print(f"   📋 Constraints: {', '.join(reasons)}")

print("\n=== PIVOT VIEW (VIN × DAY) ===")
pivot = result.pivot(index='vin', columns='day', values='available')
pivot.columns = [d.strftime('%a\n%m/%d') for d in pivot.columns]
print(pivot.to_string())

print(f"\n✅ Total available VIN-days: {result['available'].sum()}")
print(f"❌ Total blocked VIN-days: {(~result['available']).sum()}")
print(f"📊 Availability rate: {result['available'].mean():.1%}")