import { useState } from 'react';
import { EventManager, EventTypes } from '../utils/eventManager';

/**
 * Shared hook for deleting assignments
 * Handles:
 * - Single assignment deletion
 * - Batch chain deletion (multiple assignments)
 * - Event emission for cross-component sync
 * - Loading and error states
 */
export function useDeleteAssignment() {
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteMessage, setDeleteMessage] = useState('');
  const [deleteError, setDeleteError] = useState('');

  /**
   * Delete a single assignment by ID
   */
  const deleteAssignment = async ({
    assignmentId,
    office,
    partnerId,
    vin,
    onSuccess
  }) => {
    setIsDeleting(true);
    setDeleteMessage('');
    setDeleteError('');

    try {
      const response = await fetch(
        `http://localhost:8081/api/calendar/delete-assignment/${assignmentId}`,
        { method: 'DELETE' }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Failed to delete assignment');
      }

      setDeleteMessage('✅ Assignment deleted successfully');

      // Emit global event
      EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
        office,
        partnerId,
        vin,
        action: 'delete',
        assignmentId
      });

      if (onSuccess) {
        await onSuccess(data);
      }

      setIsDeleting(false);
      return { success: true, data };

    } catch (error) {
      console.error('Delete assignment error:', error);
      setDeleteError(error.message);
      setIsDeleting(false);
      return { success: false, error: error.message };
    }
  };

  /**
   * Delete multiple assignments (for "Delete Chain" buttons)
   */
  const deleteChain = async ({
    assignments,
    office,
    partnerId,
    vin,
    status, // 'manual' or 'requested'
    onSuccess
  }) => {
    setIsDeleting(true);
    setDeleteMessage('');
    setDeleteError('');

    try {
      let successCount = 0;
      let failCount = 0;

      for (const assignment of assignments) {
        try {
          const response = await fetch(
            `http://localhost:8081/api/calendar/delete-assignment/${assignment.assignment_id}`,
            { method: 'DELETE' }
          );

          if (response.ok) {
            successCount++;
          } else {
            failCount++;
          }
        } catch (err) {
          failCount++;
          console.error('Failed to delete assignment:', assignment.assignment_id, err);
        }
      }

      if (successCount > 0) {
        const statusLabel = status === 'manual' ? 'manual' : 'requested';
        setDeleteMessage(`✅ Deleted ${successCount} ${statusLabel} assignment(s)`);

        // Emit global event
        EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
          office,
          partnerId,
          vin,
          action: 'deleteChain',
          status,
          count: successCount
        });

        if (onSuccess) {
          await onSuccess({ successCount, failCount });
        }
      }

      if (failCount > 0) {
        setDeleteError(`⚠️ Failed to delete ${failCount} assignment(s)`);
      }

      setIsDeleting(false);
      return { success: successCount > 0, successCount, failCount };

    } catch (error) {
      console.error('Delete chain error:', error);
      setDeleteError(error.message);
      setIsDeleting(false);
      return { success: false, error: error.message };
    }
  };

  return {
    deleteAssignment,
    deleteChain,
    isDeleting,
    deleteMessage,
    deleteError,
    setDeleteMessage,
    setDeleteError
  };
}
