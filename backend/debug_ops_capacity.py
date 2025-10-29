"""Debug the ops capacity filtering issue."""

import pandas as pd
import sys
import os
import logging

logging.basicConfig(level=logging.DEBUG)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.solver.ortools_feasible_v2 import build_feasible_start_day_triples

vehicles = pd.DataFrame([
    {'vin': 'VIN001', 'make': 'Toyota', 'model': 'Camry', 'office': 'LA'},
])

partners = pd.DataFrame([
    {'person_id': 'P001', 'office': 'LA'},
])

approved_makes = pd.DataFrame([
    {'person_id': 'P001', 'make': 'Toyota', 'rank': 'A'},
])

# Vehicle available all week
availability = []
for day in range(7):
    availability.append({
        'vin': 'VIN001',
        'date': f'2025-09-{22+day:02d}',
        'available': True
    })
availability_df = pd.DataFrame(availability)

# Ops capacity: Monday has 0 slots, Tuesday-Friday have slots
ops_capacity = pd.DataFrame([
    {'office': 'LA', 'date': '2025-09-22', 'slots': 0},   # Monday - no slots
    {'office': 'LA', 'date': '2025-09-23', 'slots': 15},  # Tuesday
    {'office': 'LA', 'date': '2025-09-24', 'slots': 15},  # Wednesday
    {'office': 'LA', 'date': '2025-09-25', 'slots': 15},  # Thursday
    {'office': 'LA', 'date': '2025-09-26', 'slots': 15},  # Friday
])

print("Ops capacity data:")
print(ops_capacity)
print()

# Build triples
triples = build_feasible_start_day_triples(
    vehicles_df=vehicles,
    partners_df=partners,
    availability_df=availability_df,
    approved_makes_df=approved_makes,
    ops_capacity_df=ops_capacity,
    week_start='2025-09-22',
    office='LA'
)

print(f"Generated {len(triples)} triples")
if not triples.empty:
    print(triples[['vin', 'person_id', 'start_day', 'start_day_ok']])