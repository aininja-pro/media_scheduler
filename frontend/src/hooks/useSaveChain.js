import { useState } from 'react';
import { EventManager, EventTypes } from '../utils/eventManager';

/**
 * Shared hook for saving chains (both Partner and Vehicle modes)
 * Handles:
 * - API calls
 * - Success/error messages
 * - Event emission for cross-component sync
 * - Loading states
 */
export function useSaveChain() {
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [saveError, setSaveError] = useState('');

  const saveChain = async ({
    endpoint,
    payload,
    onSuccess
  }) => {
    setIsSaving(true);
    setSaveMessage('');
    setSaveError('');

    try {
      const response = await fetch(`http://localhost:8081${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to save chain');
      }

      // Set success message
      const statusLabel = payload.status === 'manual' ? 'Manual' : 'Requested';
      setSaveMessage(`✅ ${data.message} Slots cleared for next build.`);

      // Emit global event so Calendar can reload
      EventManager.emit(EventTypes.CHAIN_DATA_UPDATED, {
        office: payload.office,
        partnerId: payload.person_id,
        vin: payload.vin,
        status: payload.status,
        assignmentIds: data.assignment_ids
      });

      // Call success callback if provided
      if (onSuccess) {
        await onSuccess(data);
      }

      setIsSaving(false);
      return { success: true, data };

    } catch (error) {
      console.error('Save chain error:', error);
      setSaveError(error.message);
      setIsSaving(false);
      return { success: false, error: error.message };
    }
  };

  return {
    saveChain,
    isSaving,
    saveMessage,
    saveError,
    setSaveMessage,
    setSaveError
  };
}
