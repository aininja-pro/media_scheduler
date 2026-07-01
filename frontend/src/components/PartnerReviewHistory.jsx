import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

// Partner Review History Component
// Shows a media partner's loans over the last 6 months (published status via FMS car icon).
export default function PartnerReviewHistory({ personId, office, initialLimit = 5 }) {
  const [reviewHistory, setReviewHistory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    const fetchHistory = async () => {
      if (!personId || !office) return;

      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/chain-builder/partner-review-history/${personId}?office=${encodeURIComponent(office)}`
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch: ${response.status}`);
        }

        const data = await response.json();
        setReviewHistory(data);
      } catch (err) {
        console.error('Error fetching partner review history:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [personId, office]);

  if (loading) {
    return (
      <div>
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">🚗 Previous Loans</h3>
        <div className="flex items-center justify-center py-4 bg-gray-50 rounded-lg">
          <svg className="animate-spin h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">🚗 Previous Loans</h3>
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          Error loading history: {error}
        </div>
      </div>
    );
  }

  if (!reviewHistory || !reviewHistory.reviews || reviewHistory.reviews.length === 0) {
    return (
      <div>
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">🚗 Previous Loans</h3>
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center italic">
          No loan history in the last 6 months
        </div>
      </div>
    );
  }

  const displayedReviews = showAll ? reviewHistory.reviews : reviewHistory.reviews.slice(0, initialLimit);

  return (
    <div>
      <div className="flex items-center justify-between mb-3 border-l-4 border-orange-500 pl-3">
        <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wide flex items-center gap-2">
          🚗 Previous Loans
        </h3>
        {reviewHistory.reviews.length > initialLimit && !showAll && (
          <button
            onClick={() => setShowAll(true)}
            className="text-xs text-blue-600 hover:text-blue-800"
          >
            View All {reviewHistory.reviews.length} Loans →
          </button>
        )}
        {showAll && (
          <button
            onClick={() => setShowAll(false)}
            className="text-xs text-gray-600 hover:text-gray-800"
          >
            ← Show Less
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Vehicle</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">VIN</th>
              <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Date</th>
              <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Published</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {displayedReviews.map((review, idx) => (
              <tr key={idx} className="hover:bg-blue-50 transition-colors">
                <td className="px-4 py-2 text-sm text-gray-900">
                  {review.make} {review.model}
                </td>
                <td className="px-4 py-2 text-sm">
                  <a href={`https://fms.driveshop.com/vehicles/list_activities/${review.vehicle_id || review.vin}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline font-mono">
                    {review.vin.slice(-8)}
                  </a>
                </td>
                <td className="px-4 py-2 text-xs text-center text-gray-500">
                  {new Date(review.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </td>
                <td className="px-4 py-2 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <span
                      className={`text-base ${review.published ? '' : 'opacity-30 grayscale'}`}
                      title={review.published ? 'Published' : 'Not published'}
                    >
                      🚗
                    </span>
                    {review.clips_count > 0 && (
                      <span className="text-xs font-bold text-blue-600">
                        {review.clips_count} clip{review.clips_count !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
