import React from 'react';

/**
 * Assignment Details Panel
 *
 * Shows when user clicks on a timeline bar in Chain Builder
 * Displays full context about the assignment with action buttons
 */
export function AssignmentDetailsPanel({
  assignment,
  onClose,
  onDelete,
  onRequest,
  onUnrequest,
  onBuildChain
}) {
  if (!assignment) return null;

  const isActive = assignment.type === 'active';
  const isManual = assignment.status === 'manual';
  const isRequested = assignment.status === 'requested';

  // Format dates
  const formatDate = (date) => {
    if (!date) return 'N/A';
    if (date instanceof Date) {
      return date.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
    }
    return new Date(date).toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
  };

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-2xl z-50 overflow-y-auto border-l-4 border-indigo-500">
      {/* Header */}
      <div className="bg-indigo-600 text-white p-4 flex justify-between items-center sticky top-0">
        <h2 className="text-lg font-bold">Assignment Details</h2>
        <button
          onClick={onClose}
          className="text-white hover:bg-indigo-700 rounded-full w-8 h-8 flex items-center justify-center transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Status Badge */}
        <div className="flex items-center gap-2">
          <span className={`
            px-3 py-1 rounded-full text-sm font-semibold
            ${isActive ? 'bg-blue-100 text-blue-800' :
              isRequested ? 'bg-pink-100 text-pink-800' :
              'bg-green-100 text-green-800'}
          `}>
            {isActive ? '🔵 ACTIVE' : isRequested ? '🤖 REQUESTED' : '✓ MANUAL'}
          </span>
        </div>

        {/* Vehicle Info (for Partner view) */}
        {assignment.make && assignment.model && (
          <div className="bg-gray-50 p-3 rounded-lg">
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Vehicle</h3>
            <div className="space-y-1">
              <p className="text-lg font-bold">{assignment.make} {assignment.model}</p>
              {assignment.vin && (
                <p className="text-xs text-gray-500 font-mono">{assignment.vin}</p>
              )}
              {assignment.tier && (
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-sm font-semibold">Tier:</span>
                  <span className={`
                    px-2 py-0.5 rounded text-xs font-bold
                    ${assignment.tier === 'A+' ? 'bg-yellow-100 text-yellow-800' :
                      assignment.tier === 'A' ? 'bg-blue-100 text-blue-800' :
                      assignment.tier === 'B' ? 'bg-green-100 text-green-800' :
                      'bg-gray-100 text-gray-800'}
                  `}>
                    {assignment.tier}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Partner Info (for Vehicle view) */}
        {assignment.partner_name && (
          <div className="bg-gray-50 p-3 rounded-lg">
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Partner</h3>
            <div className="space-y-1">
              <p className="text-lg font-bold">{assignment.partner_name}</p>
              {assignment.tier && (
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-sm font-semibold">Tier:</span>
                  <span className={`
                    px-2 py-0.5 rounded text-xs font-bold
                    ${assignment.tier === 'A+' ? 'bg-yellow-100 text-yellow-800' :
                      assignment.tier === 'A' ? 'bg-blue-100 text-blue-800' :
                      assignment.tier === 'B' ? 'bg-green-100 text-green-800' :
                      'bg-gray-100 text-gray-800'}
                  `}>
                    {assignment.tier}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Dates */}
        <div className="bg-gray-50 p-3 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-600 mb-2">Schedule</h3>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Start:</span>
              <span className="text-sm font-semibold">{formatDate(assignment.start || assignment.start_day)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">End:</span>
              <span className="text-sm font-semibold">{formatDate(assignment.end || assignment.end_day)}</span>
            </div>
            {assignment.start && assignment.end && (
              <div className="flex justify-between items-center pt-2 border-t">
                <span className="text-sm text-gray-600">Duration:</span>
                <span className="text-sm font-semibold">
                  {Math.ceil((assignment.end - assignment.start) / (1000 * 60 * 60 * 24))} days
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Office */}
        {assignment.office && (
          <div className="bg-gray-50 p-3 rounded-lg">
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Office</h3>
            <p className="text-sm font-semibold">{assignment.office}</p>
          </div>
        )}

        {/* Score */}
        {assignment.score && (
          <div className="bg-gray-50 p-3 rounded-lg">
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Quality Score</h3>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-indigo-600">{assignment.score}</span>
              <span className="text-sm text-gray-500">/ 1000</span>
            </div>
          </div>
        )}

        {/* Actions */}
        {!isActive && (
          <div className="space-y-2 pt-4 border-t">
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Actions</h3>

            {/* Delete */}
            {assignment.assignment_id && onDelete && (
              <button
                onClick={() => onDelete(assignment)}
                className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-4 rounded transition-colors flex items-center justify-center gap-2"
              >
                <span>✕</span>
                <span>Delete Assignment</span>
              </button>
            )}

            {/* Request (Manual → Requested) */}
            {isManual && assignment.assignment_id && onRequest && (
              <button
                onClick={() => onRequest(assignment)}
                className="w-full bg-pink-600 hover:bg-pink-700 text-white font-semibold py-2 px-4 rounded transition-colors flex items-center justify-center gap-2"
              >
                <span>📤</span>
                <span>Send to FMS (Request)</span>
              </button>
            )}

            {/* Unrequest (Requested → Manual) */}
            {isRequested && assignment.assignment_id && onUnrequest && (
              <button
                onClick={() => onUnrequest(assignment)}
                className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-4 rounded transition-colors flex items-center justify-center gap-2"
              >
                <span>↩️</span>
                <span>Move Back to Manual</span>
              </button>
            )}

            {/* Build Chain (if vehicle/partner has chaining opportunity) */}
            {onBuildChain && (
              <button
                onClick={() => onBuildChain(assignment)}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded transition-colors flex items-center justify-center gap-2"
              >
                <span>🔗</span>
                <span>Build Chain for This {assignment.vin ? 'Vehicle' : 'Partner'}</span>
              </button>
            )}
          </div>
        )}

        {/* Active Assignment Info */}
        {isActive && (
          <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>Active Assignment:</strong> This is a current loan that cannot be modified or deleted from here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default AssignmentDetailsPanel;
