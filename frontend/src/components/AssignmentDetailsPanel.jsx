import React, { useState, useEffect } from 'react';

/**
 * Assignment Details Panel
 *
 * Shows when user clicks on a timeline bar in Chain Builder
 * Displays full context about the assignment with action buttons
 * NOW INCLUDES: Review history for vehicles/partners with filter buttons
 */
export function AssignmentDetailsPanel({
  assignment,
  onClose,
  onDelete,
  onRequest,
  onUnrequest,
  onBuildChain,
  office // Need office for API calls
}) {
  if (!assignment) return null;

  const isActive = assignment.type === 'active';
  const isManual = assignment.status === 'manual';
  const isRequested = assignment.status === 'requested';

  // Review history state
  const [reviewHistory, setReviewHistory] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [historyError, setHistoryError] = useState(null);

  // Fetch review history when assignment changes
  useEffect(() => {
    const fetchReviewHistory = async () => {
      if (!assignment || !office) return;

      setLoadingHistory(true);
      setHistoryError(null);
      setShowAllHistory(false);

      try {
        let url;
        // Determine which endpoint to call based on view mode
        if (assignment.vin) {
          // Vehicle view - show partners who reviewed this vehicle
          url = `http://localhost:8081/api/chain-builder/vehicle-review-history/${encodeURIComponent(assignment.vin)}?office=${encodeURIComponent(office)}`;
        } else if (assignment.person_id) {
          // Partner view - show vehicles this partner has reviewed
          url = `http://localhost:8081/api/chain-builder/partner-review-history/${assignment.person_id}?office=${encodeURIComponent(office)}`;
        } else {
          // Can't determine what to fetch
          setLoadingHistory(false);
          return;
        }

        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to fetch review history: ${response.status}`);
        }

        const data = await response.json();
        setReviewHistory(data);
      } catch (error) {
        console.error('Error fetching review history:', error);
        setHistoryError(error.message);
      } finally {
        setLoadingHistory(false);
      }
    };

    fetchReviewHistory();
  }, [assignment, office]);

  // Format dates
  const formatDate = (date) => {
    if (!date) return 'N/A';
    if (date instanceof Date) {
      return date.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
    }
    return new Date(date).toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
  };

  // Format date to relative (e.g., "2 months ago")
  const formatRelativeDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 30) return `${diffDays} days ago`;
    if (diffDays < 60) return '1 month ago';
    const months = Math.floor(diffDays / 30);
    return `${months} months ago`;
  };

  // Handle filter button clicks
  const handleFilterClick = () => {
    // Emit event to parent (ChainBuilder) to apply filter
    const eventType = assignment.vin ? 'APPLY_VEHICLE_HISTORY_FILTER' : 'APPLY_PARTNER_HISTORY_FILTER';
    const eventData = assignment.vin
      ? { vin: assignment.vin, reviewHistory }
      : { person_id: assignment.person_id, reviewHistory };

    window.dispatchEvent(new CustomEvent(eventType, { detail: eventData }));
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

        {/* Review History Section */}
        <div className="bg-gray-50 p-3 rounded-lg border-t-2 border-indigo-200">
          <h3 className="text-sm font-semibold text-gray-600 mb-2">
            {assignment.vin ? '📋 Review History' : '🚗 Vehicles Reviewed'}
          </h3>

          {/* Loading State */}
          {loadingHistory && (
            <div className="flex items-center justify-center py-4">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          )}

          {/* Error State */}
          {historyError && (
            <div className="bg-red-50 border border-red-200 p-2 rounded text-sm text-red-700">
              Error loading history: {historyError}
            </div>
          )}

          {/* Review History List */}
          {!loadingHistory && !historyError && reviewHistory && (
            <>
              {reviewHistory.reviews && reviewHistory.reviews.length > 0 ? (
                <>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {reviewHistory.reviews.slice(0, showAllHistory ? undefined : 5).map((review, idx) => (
                      <div
                        key={idx}
                        className="bg-white p-2 rounded border border-gray-200 hover:border-indigo-300 transition-colors"
                      >
                        {/* Vehicle View: Show Partner Info */}
                        {assignment.vin && (
                          <>
                            <div className="flex justify-between items-start">
                              <div className="flex-1">
                                <p className="font-semibold text-sm">{review.partner_name}</p>
                                <p className="text-xs text-gray-500" title={`${review.start_date} to ${review.end_date}`}>
                                  {formatRelativeDate(review.start_date)}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className={`text-lg ${review.published ? 'text-green-600' : 'text-gray-400'}`}>
                                  {review.published ? '✓' : '✗'}
                                </span>
                                {review.clips_count > 0 && (
                                  <span className="text-xs font-bold text-indigo-600">
                                    {review.clips_count} clip{review.clips_count !== 1 ? 's' : ''}
                                  </span>
                                )}
                              </div>
                            </div>
                            {!review.published && (
                              <p className="text-xs text-gray-400 mt-1">Not Published</p>
                            )}
                          </>
                        )}

                        {/* Partner View: Show Vehicle Info */}
                        {assignment.person_id && (
                          <>
                            <div className="flex justify-between items-start">
                              <div className="flex-1">
                                <p className="font-semibold text-sm">
                                  {review.make} {review.model}
                                </p>
                                <p className="text-xs text-gray-500 font-mono">
                                  {review.vin.slice(-4)}
                                </p>
                                <p className="text-xs text-gray-500" title={`${review.start_date} to ${review.end_date}`}>
                                  {formatRelativeDate(review.start_date)}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className={`text-lg ${review.published ? 'text-green-600' : 'text-gray-400'}`}>
                                  {review.published ? '✓' : '✗'}
                                </span>
                                {review.clips_count > 0 && (
                                  <span className="text-xs font-bold text-indigo-600">
                                    {review.clips_count} clip{review.clips_count !== 1 ? 's' : ''}
                                  </span>
                                )}
                              </div>
                            </div>
                            {!review.published && (
                              <p className="text-xs text-gray-400 mt-1">Not Published</p>
                            )}
                          </>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* View All Button */}
                  {reviewHistory.total_historical_reviews > 5 && !showAllHistory && (
                    <button
                      onClick={() => setShowAllHistory(true)}
                      className="w-full mt-2 text-xs text-indigo-600 hover:text-indigo-800 font-semibold py-1 border border-indigo-200 rounded hover:bg-indigo-50 transition-colors"
                    >
                      View All {reviewHistory.total_historical_reviews} Reviews →
                    </button>
                  )}

                  {/* Collapse Button */}
                  {showAllHistory && (
                    <button
                      onClick={() => setShowAllHistory(false)}
                      className="w-full mt-2 text-xs text-gray-600 hover:text-gray-800 font-semibold py-1 border border-gray-200 rounded hover:bg-gray-50 transition-colors"
                    >
                      ← Show Less
                    </button>
                  )}

                  {/* Filter Button */}
                  <button
                    onClick={handleFilterClick}
                    className="w-full mt-2 bg-indigo-100 hover:bg-indigo-200 text-indigo-700 font-semibold py-2 px-3 rounded transition-colors flex items-center justify-center gap-2 text-sm"
                  >
                    <span>🔍</span>
                    <span>
                      {assignment.vin
                        ? `Filter to Partners with History`
                        : `Filter to Vehicles with History`}
                    </span>
                  </button>
                </>
              ) : (
                <div className="text-sm text-gray-500 italic py-2">
                  {assignment.vin
                    ? 'No review history found for this vehicle in the last 6 months.'
                    : 'No review history found for this partner in the last 6 months.'}
                </div>
              )}
            </>
          )}
        </div>

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
