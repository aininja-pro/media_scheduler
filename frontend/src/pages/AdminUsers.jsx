import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../contexts/AuthContext';

/**
 * Admin console for managing who can sign in to the scheduler.
 * Only rendered for admins (App.jsx gates the tab on `isAdmin`).
 * Users are backed by Supabase Auth via /api/admin/users.
 */
const AdminUsers = () => {
  const { accessToken } = useAuth();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  // Add-user form state
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [makeAdmin, setMakeAdmin] = useState(false);
  const [fmsUserId, setFmsUserId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');

  const authHeaders = useCallback(() => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  }), [accessToken]);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users`, {
        headers: authHeaders(),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to load users (${res.status})`);
      }
      const data = await res.json();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authHeaders]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setFormError('');
    setFormSuccess('');
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          email: email.trim(),
          password,
          full_name: fullName.trim(),
          is_admin: makeAdmin,
          fms_user_id: fmsUserId.trim(),
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.detail || `Failed to create user (${res.status})`);
      }
      setFormSuccess(`Created ${body.email}. Share the temporary password with them to change on first login.`);
      setEmail('');
      setFullName('');
      setPassword('');
      setMakeAdmin(false);
      setFmsUserId('');
      fetchUsers();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetPassword = async (u) => {
    const newPassword = window.prompt(
      `Enter a new temporary password for ${u.email} (at least 8 characters):`
    );
    if (newPassword === null) return; // cancelled
    if (newPassword.length < 8) {
      alert('Password must be at least 8 characters.');
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${u.id}/reset-password`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ password: newPassword }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.detail || `Failed to reset password (${res.status})`);
      }
      alert(`Password updated for ${u.email}. Share it with them to change on next login.`);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleSetFmsUserId = async (u) => {
    const value = window.prompt(
      `FMS User ID for ${u.email} (their user ID in the FMS system, used as the requestor on vehicle requests). Leave empty to clear:`,
      u.fms_user_id || ''
    );
    if (value === null) return; // cancelled
    const trimmed = value.trim();
    if (trimmed && !/^\d+$/.test(trimmed)) {
      alert('FMS User ID must be a number (e.g. 9202).');
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${u.id}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ fms_user_id: trimmed }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.detail || `Failed to update FMS User ID (${res.status})`);
      }
      fetchUsers();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleDelete = async (u) => {
    if (!window.confirm(`Remove ${u.email}? They will no longer be able to sign in.`)) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${u.id}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.detail || `Failed to delete user (${res.status})`);
      }
      fetchUsers();
    } catch (err) {
      alert(err.message);
    }
  };

  const formatDate = (value) => {
    if (!value) return '—';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
  };

  return (
    <>
      <div className="mb-6">
        <h2 className="text-3xl font-bold text-gray-900 mb-3">User Management</h2>
        <p className="text-lg text-gray-600">
          Add or remove people who can sign in to the Media Scheduler.
        </p>
      </div>

      {/* Add user */}
      <div className="mb-8 bg-white rounded-lg shadow-md p-6">
        <h3 className="text-xl font-semibold text-gray-900 mb-4">Add a user</h3>
        <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="patrick@driveshop.com"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={submitting}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Patrick Example"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={submitting}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Temporary password</label>
            <input
              type="text"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={submitting}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">FMS User ID</label>
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={fmsUserId}
              onChange={(e) => setFmsUserId(e.target.value)}
              placeholder="e.g. 9202 — their user ID in FMS"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={submitting}
            />
            <p className="mt-1 text-xs text-gray-500">
              Used as the requestor when they send vehicle requests to FMS. Without it, they cannot submit to FMS.
            </p>
          </div>
          <div className="flex items-end">
            <label className="inline-flex items-center gap-2 text-sm font-medium text-gray-700">
              <input
                type="checkbox"
                checked={makeAdmin}
                onChange={(e) => setMakeAdmin(e.target.checked)}
                className="h-4 w-4"
                disabled={submitting}
              />
              Admin (can manage users)
            </label>
          </div>

          <div className="md:col-span-2">
            {formError && (
              <div className="mb-3 rounded-md bg-red-50 p-3 text-sm font-medium text-red-800">
                {formError}
              </div>
            )}
            {formSuccess && (
              <div className="mb-3 rounded-md bg-green-50 p-3 text-sm font-medium text-green-800">
                {formSuccess}
              </div>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Adding…' : 'Add user'}
            </button>
          </div>
        </form>
      </div>

      {/* User list */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-xl font-semibold text-gray-900">Current users</h3>
          <button
            onClick={fetchUsers}
            className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="p-6 text-gray-500">Loading users…</div>
        ) : loadError ? (
          <div className="p-6 text-red-700">{loadError}</div>
        ) : users.length === 0 ? (
          <div className="p-6 text-gray-500">No users yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr>
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-6 py-3 font-medium">Email</th>
                <th className="px-6 py-3 font-medium">Role</th>
                <th className="px-6 py-3 font-medium">FMS User ID</th>
                <th className="px-6 py-3 font-medium">Created</th>
                <th className="px-6 py-3 font-medium">Last sign-in</th>
                <th className="px-6 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-6 py-3 text-gray-900">{u.full_name || '—'}</td>
                  <td className="px-6 py-3 text-gray-900">{u.email}</td>
                  <td className="px-6 py-3">
                    {u.is_admin ? (
                      <span className="px-2 py-1 rounded-full font-semibold text-xs bg-indigo-100 text-indigo-800">
                        Admin
                      </span>
                    ) : (
                      <span className="px-2 py-1 rounded-full font-semibold text-xs bg-gray-100 text-gray-700">
                        User
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-3">
                    {u.fms_user_id ? (
                      <span className="text-gray-900">{u.fms_user_id}</span>
                    ) : (
                      <span
                        className="px-2 py-1 rounded-full font-semibold text-xs bg-amber-100 text-amber-800"
                        title="This user cannot send requests to FMS until an FMS User ID is set."
                      >
                        Not set
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-gray-600">{formatDate(u.created_at)}</td>
                  <td className="px-6 py-3 text-gray-600">{formatDate(u.last_sign_in_at)}</td>
                  <td className="px-6 py-3 text-right whitespace-nowrap">
                    <button
                      onClick={() => handleSetFmsUserId(u)}
                      className="mr-2 px-3 py-1.5 bg-indigo-100 hover:bg-indigo-200 text-indigo-800 font-semibold rounded transition-colors"
                    >
                      Set FMS ID
                    </button>
                    <button
                      onClick={() => handleResetPassword(u)}
                      className="mr-2 px-3 py-1.5 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold rounded transition-colors"
                    >
                      Reset password
                    </button>
                    <button
                      onClick={() => handleDelete(u)}
                      className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white font-semibold rounded transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
};

export default AdminUsers;
