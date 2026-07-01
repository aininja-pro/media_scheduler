"""
One-time bootstrap: create an initial admin user in Supabase Auth.

Someone has to be the first admin before the in-app "Users" console can be
used. Run this once per admin (you, then Dave). After that, admins add
everyone else from the app - no need to run this again.

Usage (from the backend/ directory, using the venv):

    ./venv/bin/python -m app.scripts.seed_admins \
        --email dave@driveshop.com \
        --password "TempPass123!" \
        --name "Dave Morck"

The account is created already-confirmed and flagged as admin
(user_metadata.is_admin = true). Tell the user to change the temp password
after their first login.
"""

import os
import sys
import argparse

from dotenv import load_dotenv

# Supabase creds live in the project-root .env (same file the geocode
# scripts load). Load it before creating the client.
_ROOT_ENV = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(dotenv_path=os.path.abspath(_ROOT_ENV))

from supabase import create_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an initial admin user in Supabase Auth")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Temporary password (user should change it)")
    parser.add_argument("--name", default="", help="Full name (optional)")
    args = parser.parse_args()

    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not found in environment (.env).")
        return 1

    client = create_client(url, service_key)

    try:
        result = client.auth.admin.create_user({
            "email": args.email,
            "password": args.password,
            "email_confirm": True,
            "user_metadata": {"full_name": args.name, "is_admin": True},
        })
    except Exception as e:
        print(f"ERROR: could not create admin {args.email}: {e}")
        return 1

    print(f"✓ Created admin account: {result.user.email} (id={result.user.id})")
    print("  They can log in now with the temp password; ask them to change it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
