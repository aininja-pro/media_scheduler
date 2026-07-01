import React, { useState } from 'react';
import driveShopLogo from '../assets/DriveShop_WebLogo.png';
import backgroundImage from '../assets/locations-2.jpg';
import { supabase } from '../lib/supabaseClient';

/**
 * Self-service password change form.
 *
 * variant="account"  → embedded card shown inside the app (Account tab).
 * variant="recovery" → full-screen card shown after a "forgot password"
 *                      email link, before the user re-enters the app.
 *
 * Both use the signed-in Supabase session, so no current password is needed
 * (Supabase authenticates via the session / recovery token).
 */
const ChangePassword = ({ variant = 'account', onSuccess }) => {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setSaving(true);
    const { error: err } = await supabase.auth.updateUser({ password });
    setSaving(false);

    if (err) {
      setError(err.message);
      return;
    }
    setPassword('');
    setConfirm('');
    setSuccess('Your password has been updated.');
    if (onSuccess) onSuccess();
  };

  const form = (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">New password</label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 8 characters"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          disabled={saving}
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Confirm new password</label>
        <input
          type="password"
          required
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Re-enter password"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          disabled={saving}
        />
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm font-medium text-red-800">{error}</div>
      )}
      {success && (
        <div className="rounded-md bg-green-50 p-3 text-sm font-medium text-green-800">{success}</div>
      )}

      <button
        type="submit"
        disabled={saving}
        className="px-5 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {saving ? 'Saving…' : 'Update password'}
      </button>
    </form>
  );

  if (variant === 'recovery') {
    return (
      <div
        className="min-h-screen flex items-center justify-center bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: `url(${backgroundImage})` }}
      >
        <div className="max-w-md w-full space-y-6 p-8 bg-white/95 backdrop-blur-sm rounded-lg shadow-xl">
          <div className="text-center">
            <div className="bg-black rounded-lg p-4 mx-auto inline-block mb-4">
              <img src={driveShopLogo} alt="DriveShop" className="h-16 w-auto" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900">Set a new password</h2>
            <p className="mt-2 text-sm text-gray-600">Choose a new password to finish signing in.</p>
          </div>
          {form}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="mb-6">
        <h2 className="text-3xl font-bold text-gray-900 mb-3">Account</h2>
        <p className="text-lg text-gray-600">Change the password you use to sign in.</p>
      </div>
      <div className="max-w-md bg-white rounded-lg shadow-md p-6">{form}</div>
    </>
  );
};

export default ChangePassword;
