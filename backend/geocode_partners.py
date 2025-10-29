"""
Geocode media partner addresses and update database with lat/lng coordinates.

Uses geopy with Nominatim (free, no API key needed).
Rate limited to 1 request per second per Nominatim usage policy.
"""

import os
import sys
import time
import ssl
import certifi
from dotenv import load_dotenv
from supabase import create_client
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Load environment variables from project root
load_dotenv(dotenv_path='/Users/richardrierson/Desktop/Projects/media_scheduler/.env')

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Create SSL context using certifi's certificate bundle
ctx = ssl.create_default_context(cafile=certifi.where())

# Initialize geocoder with SSL context
geolocator = Nominatim(user_agent="media_scheduler_geocoder", ssl_context=ctx)


def geocode_address(address, max_retries=3):
    """
    Geocode an address and return latitude, longitude.

    Args:
        address: Full address string
        max_retries: Number of retry attempts for timeouts

    Returns:
        tuple: (latitude, longitude) or (None, None) if geocoding fails
    """
    if not address or address.strip() == "":
        return None, None

    for attempt in range(max_retries):
        try:
            location = geolocator.geocode(address, timeout=10)
            if location:
                return location.latitude, location.longitude
            else:
                print(f"  ⚠️  No results for: {address}")
                return None, None
        except GeocoderTimedOut:
            if attempt < max_retries - 1:
                print(f"  ⏱️  Timeout, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(2)
            else:
                print(f"  ❌ Timeout after {max_retries} attempts: {address}")
                return None, None
        except GeocoderServiceError as e:
            print(f"  ❌ Service error: {e}")
            return None, None
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            return None, None

    return None, None


def main():
    """Geocode all media partners with addresses."""

    print("🌍 Media Partner Geocoding Script")
    print("=" * 50)

    # Fetch all partners that need geocoding
    print("\n📊 Fetching partners from database...")
    response = supabase.table('media_partners').select('person_id, name, address').execute()
    partners = response.data

    print(f"✅ Found {len(partners)} total partners")

    # Filter partners that need geocoding
    needs_geocoding = [p for p in partners if p.get('address') and p['address'].strip() != '']
    null_addresses = len(partners) - len(needs_geocoding)

    print(f"📍 {len(needs_geocoding)} partners have addresses")
    print(f"⚠️  {null_addresses} partners have null/empty addresses (will skip)")

    # Estimate time
    estimated_minutes = len(needs_geocoding) / 60
    print(f"\n⏱️  Estimated time: ~{estimated_minutes:.1f} minutes")
    print(f"   (Rate limited to 1 request per second)\n")
    print("🚀 Starting geocoding...")

    # Geocode each partner
    success_count = 0
    fail_count = 0
    skip_count = 0

    for i, partner in enumerate(needs_geocoding, 1):
        person_id = partner['person_id']
        name = partner.get('name', 'Unknown')
        address = partner.get('address', '')

        # Use address as-is for geocoding
        full_address = address

        print(f"\n[{i}/{len(needs_geocoding)}] {name} (ID: {person_id})")
        print(f"  Address: {full_address}")

        # Geocode
        lat, lng = geocode_address(full_address)

        if lat and lng:
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

        # Rate limit: 1 request per second
        if i < len(needs_geocoding):
            time.sleep(1.1)  # Slightly over 1 second to be safe

    # Summary
    print("\n" + "=" * 50)
    print("📊 Geocoding Summary")
    print("=" * 50)
    print(f"✅ Successfully geocoded: {success_count}")
    print(f"❌ Failed to geocode: {fail_count}")
    print(f"⚠️  Skipped (no address): {null_addresses}")
    print(f"📍 Total partners: {len(partners)}")

    if success_count > 0:
        success_rate = (success_count / len(needs_geocoding)) * 100
        print(f"\n🎯 Success rate: {success_rate:.1f}%")

    print("\n✨ Geocoding complete!")


if __name__ == "__main__":
    main()