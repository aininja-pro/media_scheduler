import requests
import json

# Run the solver
response = requests.post(
    'http://localhost:8000/api/solver/assignment_options',
    json={
        'office': 'Los Angeles',
        'week_start': '2025-09-22',
        'partners_to_notify': ['ALL']
    }
)

if response.ok:
    data = response.json()
    assignments = data.get('greedy_assignments', [])
    
    # Count unique partners
    unique_partners = set()
    make_counts = {}
    
    for a in assignments:
        unique_partners.add(a['person_id'])
        make = a.get('make', 'Unknown')
        make_counts[make] = make_counts.get(make, 0) + 1
    
    print(f'Total assignments: {len(assignments)}')
    print(f'Unique partners: {len(unique_partners)}')
    print(f'\nTop 5 makes assigned:')
    for make, count in sorted(make_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f'  {make}: {count}')
    
    print(f'\nFirst 10 assignments (partner names):')
    for a in assignments[:10]:
        print(f'  {a["person_name"]}: {a["make"]} {a["model"]}, Score: {a.get("score", "?")}')
else:
    print(f'Error: {response.status_code}')
