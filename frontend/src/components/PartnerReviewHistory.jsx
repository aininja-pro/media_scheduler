import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

// FMS "Published" clip mark: orange speech bubble with a tail at the bottom-left.
function PublishedClipIcon({ title, decorative = false }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 16 16"
      className="inline-block align-middle shrink-0"
      aria-hidden={decorative ? 'true' : undefined}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : 'Published'}
    >
      {!decorative && <title>{title || 'Published'}</title>}
      <ellipse cx="8.3" cy="7" rx="6.1" ry="4.7" fill="#F0A000" />
      <path d="M4.4 10.4 2.3 14.2 7.4 11.2z" fill="#F0A000" />
    </svg>
  );
}

// Turn "2026-08-06" into "08/06/26" without shifting a day in US time zones.
function formatLoanDate(dateStr) {
  if (!dateStr) return null;
  const parsed = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString('en-US', {
    month: '2-digit',
    day: '2-digit',
    year: '2-digit',
  });
}

// Show the full loan window, or just the start if the end is missing.
function formatLoanRange(startDate, endDate) {
  const start = formatLoanDate(startDate);
  const end = formatLoanDate(endDate);
  if (start && end) return `${start} – ${end}`;
  if (start) return start;
  return 'Date unavailable';
}

// Partner Review History
// Shows a media partner's loans over the last 6 months.
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

  const sectionTitle = (
    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">🚗 Previous Loans</h3>
  );

  if (loading) {
    return (
      <div>
        {sectionTitle}
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
        {sectionTitle}
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          Error loading history: {error}
        </div>
      </div>
    );
  }

  if (!reviewHistory || !reviewHistory.reviews || reviewHistory.reviews.length === 0) {
    return (
      <div>
        {sectionTitle}
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center italic">
          No loan history in the last 6 months
        </div>
      </div>
    );
  }

  const displayedReviews = showAll ? reviewHistory.reviews : reviewHistory.reviews.slice(0, initialLimit);

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-3 border-l-4 border-orange-500 pl-3">
        <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wide">
          🚗 Previous Loans
        </h3>
        {/* Key replaces the old "Published" column header */}
        <div className="flex items-center gap-1.5 text-xs text-gray-500" aria-label="Published loans show this icon">
          <PublishedClipIcon decorative title="Published" />
          <span>Published</span>
        </div>
      </div>

      {reviewHistory.reviews.length > initialLimit && (
        <div className="flex justify-end mb-2">
          {!showAll ? (
            <button
              onClick={() => setShowAll(true)}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              View All {reviewHistory.reviews.length} Loans →
            </button>
          ) : (
            <button
              onClick={() => setShowAll(false)}
              className="text-xs text-gray-600 hover:text-gray-800"
            >
              ← Show Less
            </button>
          )}
        </div>
      )}

      {/* Stacked rows (not a table) so the vehicle name can use the full width */}
      <ul className="divide-y divide-gray-200">
        {displayedReviews.map((review, idx) => {
          const vehicleName = [review.make, review.model].filter(Boolean).join(' ');
          const publishedTitle = review.clips_count > 0
            ? `Published · ${review.clips_count} clip${review.clips_count !== 1 ? 's' : ''}`
            : 'Published';

          return (
            <li key={`${review.vin}-${review.start_date}-${idx}`} className="py-2.5">
              <p className="text-sm font-medium text-gray-900 leading-snug">
                {vehicleName || 'Unknown vehicle'}
              </p>
              <div className="mt-0.5 flex items-center gap-2 text-xs">
                <span className="flex-1 text-gray-500">
                  {formatLoanRange(review.start_date, review.end_date)}
                </span>
                <a
                  href={`https://fms.driveshop.com/vehicles/list_activities/${review.vehicle_id || review.vin}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 hover:underline font-mono"
                >
                  {review.vin ? review.vin.slice(-8) : 'N/A'}
                </a>
                {/* Keep an icon-width slot so VINs stay lined up when a loan is not published */}
                <span className="w-[18px] flex justify-center">
                  {review.published && (
                    <PublishedClipIcon title={publishedTitle} />
                  )}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
