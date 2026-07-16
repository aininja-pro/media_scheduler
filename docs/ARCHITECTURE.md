# Architecture

High-level overview of how the Media Scheduler app fits together. See also
`docs/database-schema.md` and `docs/api-reference.md`.

## System overview

- **Frontend** — React 19 single-page app (`frontend/`), built with Vite and styled
  with Tailwind CSS. Navigation is tab-based (`activeTab` state in
  `frontend/src/App.jsx`); there is no client-side router. Components call the backend
  directly with `fetch` using `API_BASE_URL` from `frontend/src/config.js`.
- **Backend** — FastAPI app (`backend/app/`). Routers live in `backend/app/routers/`
  and are registered in `backend/app/main.py`. Data access goes through
  `backend/app/services/database.py`, which wraps the Supabase Python client using the
  service-role key.
- **Data store** — Supabase (Postgres). Business tables (vehicles, media_partners,
  scheduled_assignments, budgets, etc.) plus Supabase Auth for user accounts.
- **Nightly sync** — APScheduler job in `main.py` pulls FMS data on a cron schedule.

## Authentication & user management

The app supports **two sign-in paths**, resolved in `frontend/src/components/Login.jsx`:

1. **Per-user login (Supabase Auth).** Individual accounts live in Supabase Auth
   (`auth.users`). The browser signs in with `supabase.auth.signInWithPassword`
   (`frontend/src/lib/supabaseClient.js`, public anon key). `AuthContext`
   (`frontend/src/contexts/AuthContext.jsx`) restores/refreshes the session and exposes
   `user`, `isAdmin`, and `accessToken`. The admin flag is stored per user in
   `user_metadata.is_admin`; the display name in `user_metadata.full_name`.
2. **Shared DriveShop login (admin).** The familiar shared username
   (`VITE_AUTH_USERNAME`, e.g. `driveshop`) is mapped at login to a real Supabase admin
   account (`VITE_SHARED_ADMIN_EMAIL`, e.g. `driveshop@driveshop.com`). So typing the
   shared username/password signs into that Supabase account and gets a normal admin
   session (token + Users tab). People keep using the same shared credentials as before.
3. **Env fallback (non-admin, degraded).** If Supabase sign-in fails (e.g. misconfigured),
   the original `VITE_AUTH_USERNAME` / `VITE_AUTH_PASSWORD` check still logs in via a
   `sessionStorage` flag. This path has no token and is non-admin — a safety net only.

`AuthGate` in `App.jsx` shows `Login` until authenticated, then the app.

### Admin console

Admins (users with `is_admin: true`) see a **Users** tab (`frontend/src/pages/AdminUsers.jsx`)
that lets them add and remove users. It calls the admin API:

- `GET/POST /api/admin/users`, `DELETE /api/admin/users/{id}`,
  `POST /api/admin/users/{id}/reset-password` — implemented in
  `backend/app/routers/users.py` on top of Supabase Auth's admin API
  (`client.auth.admin.*`).

These endpoints are protected by the `require_admin` dependency: the caller must send a
Supabase access token (`Authorization: Bearer <token>`) belonging to an admin. The shared
DriveShop login qualifies because it is backed by a real Supabase admin account; only the
non-admin env fallback (no token) cannot reach the admin API.

Everyone (per-user or shared login) has full access to the rest of the app; only the
Users tab / admin API is restricted to admins.

### Self-service password management

Per-user (Supabase) accounts can manage their own passwords without an admin:

- **Change password** — an **Account** tab (`frontend/src/components/ChangePassword.jsx`),
  shown whenever `authMode === 'supabase'`, calls `supabase.auth.updateUser({ password })`.
- **Forgot password** — a "Forgot password?" link on the login screen calls
  `supabase.auth.resetPasswordForEmail(email, { redirectTo: window.location.origin })`.
  The email link returns the user to the app, where Supabase fires a `PASSWORD_RECOVERY`
  event; `AuthContext` sets `isRecovering`, and `AuthGate` shows the recovery variant of
  `ChangePassword` to set a new password before entering the app.

Admins can also reset any user's password from the Users tab (the "Reset password" button
→ `POST /api/admin/users/{id}/reset-password`). The legacy shared login has no Supabase
account, so none of these apply to it.

**Supabase config:** for the forgot-password email flow, each app origin
(`http://localhost:5173`, the production URL, etc.) must be listed under Supabase →
Authentication → URL Configuration → Redirect URLs.

### Bootstrapping the first admin

Someone must be the first admin before the console can be used. Run once per initial
admin:

```
cd backend
./venv/bin/python -m app.scripts.seed_admins --email you@driveshop.com --password "TempPass123!" --name "Your Name"
```

After that, admins add everyone else from the Users tab.

### Environment variables

- Backend (project-root `.env`): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- Frontend (`frontend/.env.*`): `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (anon key is
  browser-safe), plus the legacy `VITE_AUTH_USERNAME` / `VITE_AUTH_PASSWORD`.

## FMS integration (vehicle requests)

Submitting an assignment to FMS (`backend/app/routers/fms_integration.py`) flows through
three gates before the request is sent to `FMS_BASE_URL/api/v1/vehicle_requests`:

1. **Attribution.** `resolve_fms_requestor` verifies the caller's Supabase token and uses
   `user_metadata.fms_user_id` as the FMS `requestor_id` (set per user in the Users tab).
   No token or no FMS User ID → 401/403; there is deliberately no shared fallback ID, so
   every FMS request is attributed to a real person. The frontend attaches the token via
   `getAuthHeader()` (`frontend/src/lib/supabaseClient.js`).
2. **Conflict re-check.** `find_vehicle_conflicts` (`backend/app/services/conflicts.py`)
   verifies the vehicle isn't already booked for the dates — against `current_activity`
   (real FMS activity, synced nightly) and other `scheduled_assignments`. Conflicts → 409
   with a plain-English description. The same check runs when chains are saved
   (`_reject_if_chain_conflicts` in `backend/app/routers/chain_builder.py`), but the
   submit-time re-check matters because FMS activity changes between planning and
   submission.
3. **Submission + audit.** Every attempt (blocked, failed, or succeeded) is recorded in
   the `fms_submission_log` table via `log_fms_submission` — who, which assignment, when,
   and the outcome — since Render's log retention is short. On success the returned FMS
   request ID is stored on the assignment (`fms_request_id`).

Status flow: green (`planned`/`manual`) → magenta (`requested`) only after FMS accepts;
on any failure the status is rolled back, so a pink bar always means "actually in FMS".
The UI shows the outcome in a blocking dialog (`frontend/src/components/FmsResultModal.jsx`).
