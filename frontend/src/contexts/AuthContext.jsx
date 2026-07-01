import React, { createContext, useContext, useState, useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';

const AuthContext = createContext(null);

const LEGACY_KEY = 'media_scheduler_auth';

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState(null);          // { email, full_name }
  const [isAdmin, setIsAdmin] = useState(false);
  const [accessToken, setAccessToken] = useState(null);
  const [authMode, setAuthMode] = useState(null);  // 'supabase' | 'legacy'
  const [isRecovering, setIsRecovering] = useState(false); // password-reset link in progress

  // Apply a Supabase session to auth state (used on load + auth events).
  const applySession = (session) => {
    const metadata = session.user?.user_metadata || {};
    setUser({ email: session.user?.email, full_name: metadata.full_name || '' });
    setIsAdmin(Boolean(metadata.is_admin));
    setAccessToken(session.access_token || null);
    setAuthMode('supabase');
    setIsAuthenticated(true);
  };

  const resetState = () => {
    setIsAuthenticated(false);
    setUser(null);
    setIsAdmin(false);
    setAccessToken(null);
    setAuthMode(null);
    setIsRecovering(false);
  };

  // Restore an existing session on mount and keep it in sync.
  useEffect(() => {
    let active = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      if (data?.session) {
        applySession(data.session);
      } else if (sessionStorage.getItem(LEGACY_KEY) === 'authenticated') {
        // Legacy shared login (no Supabase session, non-admin).
        setUser({ email: 'DriveShop (shared login)', full_name: '' });
        setIsAdmin(false);
        setAuthMode('legacy');
        setIsAuthenticated(true);
      }
      setIsLoading(false);
    });

    // Keep token fresh and react to sign-in / sign-out / refresh events.
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      // User arrived via a password-reset email link: force the reset screen.
      if (event === 'PASSWORD_RECOVERY') {
        if (session) applySession(session);
        setIsRecovering(true);
        return;
      }
      if (session) {
        applySession(session);
      } else if (sessionStorage.getItem(LEGACY_KEY) !== 'authenticated') {
        resetState();
      }
    });

    return () => {
      active = false;
      sub?.subscription?.unsubscribe();
    };
  }, []);

  // Legacy shared login (called by Login.jsx when the shared credentials match).
  const login = () => {
    sessionStorage.setItem(LEGACY_KEY, 'authenticated');
    setUser({ email: 'DriveShop (shared login)', full_name: '' });
    setIsAdmin(false);
    setAuthMode('legacy');
    setIsAuthenticated(true);
  };

  // Called after the user sets a new password from a reset link; drops the
  // recovery screen and lets them into the app (they're already signed in).
  const finishRecovery = () => setIsRecovering(false);

  const logout = async () => {
    sessionStorage.removeItem(LEGACY_KEY);
    if (authMode === 'supabase') {
      try {
        await supabase.auth.signOut();
      } catch (e) {
        console.warn('Supabase sign-out failed:', e);
      }
    }
    resetState();
  };

  const value = {
    isAuthenticated,
    isLoading,
    user,
    isAdmin,
    accessToken,
    authMode,
    isRecovering,
    login,
    logout,
    finishRecovery,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
