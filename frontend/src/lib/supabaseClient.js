/**
 * Supabase browser client (used for per-user authentication only).
 *
 * Uses the public anon key, which is safe to expose in the browser. The
 * client persists the session in localStorage so a signed-in user stays
 * logged in across refreshes.
 */
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // Not fatal: the legacy shared login still works without Supabase configured.
  console.warn('Supabase env vars missing - per-user login is disabled until VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are set.');
}

export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '');

/**
 * Authorization header for API calls that must be attributed to the
 * signed-in user (e.g. FMS submissions, which send their FMS User ID as
 * the requestor). Returns {} for the legacy shared login, which has no
 * Supabase session — the backend rejects those submissions with a clear
 * message.
 */
export async function getAuthHeader() {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}
