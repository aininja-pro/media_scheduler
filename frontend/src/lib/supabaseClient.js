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
