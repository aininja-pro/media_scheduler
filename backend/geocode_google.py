"""
Geocode addresses using Google Maps Geocoding API.
Processes CSV file and updates missing lat/lng coordinates.
"""

import argparse
import csv
import time
import os
import sys
import requests
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv(dotenv_path='/Users/richardrierson/Desktop/Projects/media_scheduler/.env')

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def geocode_address_google(address, api_key, region='us', components=None):
    """
    Geocode an address using Google Maps Geocoding API.

    Args:
        address: Full address string
        api_key: Google API key
        region: Region bias (default 'us')
        components: Component filters (e.g., 'country:US')

    Returns:
        tuple: (latitude, longitude) or (None, None) if geocoding fails
    """
    if not address or address.strip() == "":
        return None, None

    base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    params = {
        'address': address,
        'key': api_key,
        'region': region
    }

    if components:
        params['components'] = components

    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data['status'] == 'OK' and len(data['results']) > 0:
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
        elif data['status'] == 'ZERO_RESULTS':
            return None, None
        else:
            print(f"  ⚠️  API Error: {data['status']}")
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request error: {e}")
        return None, None
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(description='Geocode addresses using Google Maps API')
    parser.add_argument('--input', required=True, help='Input CSV file path')
    parser.add_argument('--output', required=True, help='Output CSV file path')
    parser.add_argument('--key', required=True, help='Google API key')
    parser.add_argument('--address-column', default='address', help='Address column name')
    parser.add_argument('--region', default='us', help='Region bias')
    parser.add_argument('--components', help='Component filters (e.g., country:US)')
    parser.add_argument('--rps', type=float, default=5, help='Requests per second')

    args = parser.parse_args()

    print("🗺️  Google Maps Geocoding Script")
    print("=" * 50)

    # Read CSV
    print(f"\n📊 Reading {args.input}...")

    rows = []
    with open(args.input, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"✅ Found {len(rows)} total rows")

    # Filter rows that need geocoding (missing lat/lng)
    needs_geocoding = [r for r in rows if not r.get('latitude') or not r.get('longitude')]

    print(f"📍 {len(needs_geocoding)} rows need geocoding")
    print(f"✓ {len(rows) - len(needs_geocoding)} rows already have coordinates")

    if len(needs_geocoding) == 0:
        print("\n✨ All addresses already geocoded!")
        return

    # Calculate rate limiting
    delay = 1.0 / args.rps
    estimated_time = len(needs_geocoding) * delay / 60

    print(f"\n⏱️  Estimated time: ~{estimated_time:.1f} minutes")
    print(f"   (Rate: {args.rps} requests per second)\n")
    print("🚀 Starting geocoding...")

    # Geocode each address
    success_count = 0
    fail_count = 0

    for i, row in enumerate(needs_geocoding, 1):
        person_id = row.get('person_id')
        name = row.get('name', 'Unknown')
        address = row.get(args.address_column, '')

        print(f"\n[{i}/{len(needs_geocoding)}] {name} (ID: {person_id})")
        print(f"  Address: {address}")

        # Geocode
        lat, lng = geocode_address_google(
            address,
            args.key,
            region=args.region,
            components=args.components
        )

        if lat and lng:
            # Update the row
            row['latitude'] = lat
            row['longitude'] = lng

            # Update database
            try:
                supabase.table('media_partners').update({
                    'latitude': lat,
                    'longitude': lng
                }).eq('person_id', person_id).execute()

                print(f"  ✅ Success: {lat:.6f}, {lng:.6f}")
                success_count += 1
            except Exception as e:
                print(f"  ❌ Database update failed: {e}")
                fail_count += 1
        else:
            print(f"  ❌ Geocoding failed")
            fail_count += 1

        # Rate limit
        if i < len(needs_geocoding):
            time.sleep(delay)

    # Write output CSV
    print(f"\n📝 Writing output to {args.output}...")

    with open(args.output, 'w', encoding='utf-8', newline='') as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Summary
    print("\n" + "=" * 50)
    print("📊 Geocoding Summary")
    print("=" * 50)
    print(f"✅ Successfully geocoded: {success_count}")
    print(f"❌ Failed to geocode: {fail_count}")
    print(f"📁 Output saved to: {args.output}")

    if success_count > 0:
        success_rate = (success_count / len(needs_geocoding)) * 100
        print(f"\n🎯 Success rate: {success_rate:.1f}%")

    print("\n✨ Geocoding complete!")


if __name__ == "__main__":
    main()