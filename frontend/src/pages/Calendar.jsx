import React, { useState, useEffect, useMemo } from 'react';
import { EventManager, EventTypes } from '../utils/eventManager';
import { API_BASE_URL } from '../config';

/**
 * Format partner name for display
 * @param {string} name - Full name (e.g., "John Smith" or "Mary Jo Smith")
 * @param {string} format - 'lastFirst' or 'firstLast'
 * @returns {string} Formatted name
 */
const formatPartnerName = (name, format = 'lastFirst') => {
  if (!name) return '';

  const parts = name.trim().split(/\s+/);

  // Single word name (e.g., "Madonna")
  if (parts.length === 1) {
    return name;
  }

  // Multiple words: last word = last name, rest = first name
  const lastName = parts[parts.length - 1];
  const firstName = parts.slice(0, -1).join(' ');

  if (format === 'lastFirst') {
    return `${lastName}, ${firstName}`;
  } else {
    return name; // firstLast - return original
  }
};

// Partner Review History Component
function PartnerReviewHistory({ personId, office }) {
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

  const displayedReviews = showAll ? reviewHistory.reviews : reviewHistory.reviews.slice(0, 5);

  return (
    <div>
      <div className="flex items-center justify-between mb-3 border-l-4 border-orange-500 pl-3">
        <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wide flex items-center gap-2">
          🚗 Previous Loans
        </h3>
        {reviewHistory.reviews.length > 5 && !showAll && (
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
                  <a href="#" className="text-blue-600 hover:text-blue-800 font-mono">
                    {review.vin.slice(-8)}
                  </a>
                </td>
                <td className="px-4 py-2 text-xs text-center text-gray-500">
                  {new Date(review.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </td>
                <td className="px-4 py-2 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <span className={`text-base ${review.published ? 'text-green-600' : 'text-gray-400'}`}>
                      {review.published ? '✓' : '✗'}
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

// Vehicle Review History Component
function VehicleReviewHistory({ vin, office }) {
  const [reviewHistory, setReviewHistory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    const fetchHistory = async () => {
      if (!vin || !office) return;

      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/chain-builder/vehicle-review-history/${encodeURIComponent(vin)}?office=${encodeURIComponent(office)}`
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch: ${response.status}`);
        }

        const data = await response.json();
        setReviewHistory(data);
      } catch (err) {
        console.error('Error fetching review history:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [vin, office]);

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

  if (loading) {
    return (
      <div>
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">📋 Review History</h3>
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
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">📋 Review History</h3>
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          Error loading history: {error}
        </div>
      </div>
    );
  }

  if (!reviewHistory || !reviewHistory.reviews || reviewHistory.reviews.length === 0) {
    return (
      <div>
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">📋 Review History</h3>
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center italic">
          No review history in the last 6 months
        </div>
      </div>
    );
  }

  const displayedReviews = showAll ? reviewHistory.reviews : reviewHistory.reviews.slice(0, 5);

  return (
    <div>
      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">📋 Review History</h3>
      <div className="bg-gray-50 rounded-lg p-3 space-y-2">
        {displayedReviews.map((review, idx) => (
          <div key={idx} className="bg-white rounded border border-gray-200 p-2 hover:border-blue-300 transition-colors">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">{review.partner_name}</p>
                <p className="text-xs text-gray-500" title={`${review.start_date} to ${review.end_date}`}>
                  {formatRelativeDate(review.start_date)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-base ${review.published ? 'text-green-600' : 'text-gray-400'}`}>
                  {review.published ? '✓' : '✗'}
                </span>
                {review.clips_count > 0 && (
                  <span className="text-xs font-bold text-blue-600">
                    {review.clips_count} clip{review.clips_count !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
            </div>
            {!review.published && (
              <p className="text-xs text-gray-400 mt-1">Not Published</p>
            )}
          </div>
        ))}

        {reviewHistory.total_historical_reviews > 5 && !showAll && (
          <button
            onClick={() => setShowAll(true)}
            className="w-full text-xs text-blue-600 hover:text-blue-800 font-semibold py-1 border border-blue-200 rounded hover:bg-blue-50 transition-colors mt-2"
          >
            View All {reviewHistory.total_historical_reviews} Reviews →
          </button>
        )}

        {showAll && (
          <button
            onClick={() => setShowAll(false)}
            className="w-full text-xs text-gray-600 hover:text-gray-800 font-semibold py-1 border border-gray-200 rounded hover:bg-gray-50 transition-colors mt-2"
          >
            ← Show Less
          </button>
        )}
      </div>
    </div>
  );
}

// Haversine distance calculation (in miles)
const calculateDistance = (lat1, lon1, lat2, lon2) => {
  const R = 3959; // Earth's radius in miles
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
};

function Calendar({ sharedOffice, onOfficeChange, isActive, onBuildChainForVehicle, onBuildChainForPartner }) {
  // Use shared office from parent, default to 'Los Angeles' if not provided
  const [selectedOffice, setSelectedOffice] = useState(sharedOffice || 'Los Angeles');

  // Update selectedOffice when sharedOffice prop changes
  useEffect(() => {
    if (sharedOffice) {
      setSelectedOffice(sharedOffice);
    }
  }, [sharedOffice]);

  // Update parent when local office changes
  const handleOfficeChange = (newOffice) => {
    setSelectedOffice(newOffice);
    if (onOfficeChange) {
      onOfficeChange(newOffice);
    }
  };
  const [selectedMonth, setSelectedMonth] = useState('');
  const [viewStartDate, setViewStartDate] = useState(null); // Custom start date for sliding view
  const [viewEndDate, setViewEndDate] = useState(null); // Custom end date for sliding view
  const [activities, setActivities] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // View mode toggle
  const [viewMode, setViewMode] = useState('vehicle'); // 'vehicle' or 'partner'

  // Partner distances cache
  const [partnerDistances, setPartnerDistances] = useState({});

  // Filters
  const [vinFilter, setVinFilter] = useState('');
  const [makeFilter, setMakeFilter] = useState('');
  const [partnerFilter, setPartnerFilter] = useState('');
  const [activityFilter, setActivityFilter] = useState('all'); // 'all', 'with-activity', 'no-activity'

  // Multi-select filters
  const [selectedPartners, setSelectedPartners] = useState([]); // Array of person_ids
  const [selectedVehicles, setSelectedVehicles] = useState([]); // Array of VINs
  const [selectedTiers, setSelectedTiers] = useState([]); // Array of tier ranks (A+, A, B, C)
  const [selectedMakes, setSelectedMakes] = useState([]); // Array of makes
  const [showPartnerDropdown, setShowPartnerDropdown] = useState(false);
  const [showVehicleDropdown, setShowVehicleDropdown] = useState(false);
  const [vehicleSearchQuery, setVehicleSearchQuery] = useState(''); // Search term for vehicle filter

  // Hover actions for timeline bars
  const [hoveredAssignment, setHoveredAssignment] = useState(null); // assignment_id of hovered bar

  // Handle status change (green → magenta)
  const requestAssignment = async (assignmentId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/calendar/change-assignment-status/${assignmentId}?new_status=requested`, {
        method: 'PATCH'
      });

      if (!response.ok) {
        const errorData = await response.json();
        if (response.status === 500) {
          alert('⚠️ Failed to send request to FMS.\n\nThe assignment has NOT been marked as requested. Please try again or contact support if the issue persists.');
        } else {
          alert(`Failed to request: ${errorData.detail || errorData.message || 'Unknown error'}`);
        }
        return;
      }

      const data = await response.json();

      if (data.success) {
        // Check if FMS action was performed
        if (data.fms_action === 'create') {
          alert('✓ Assignment requested successfully!\n\nThe request has been sent to FMS for approval.');
        } else {
          alert('✓ Assignment status changed to requested.');
        }

        // Reload activities to show magenta bar
        loadActivities();
      } else {
        alert(`Failed to request: ${data.message || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Request assignment error:', err);
      alert(`Network error: Could not connect to server.\n\n${err.message}`);
    }
  };

  // Handle unrequest (magenta → green)
  const unrequestAssignment = async (assignmentId) => {
    try {
      // Change back to 'planned' status (this will delete from FMS)
      const response = await fetch(`${API_BASE_URL}/api/calendar/change-assignment-status/${assignmentId}?new_status=planned`, {
        method: 'PATCH'
      });

      if (!response.ok) {
        const errorData = await response.json();
        if (response.status === 500) {
          alert('⚠️ Failed to unrequest from FMS.\n\nThe request may still be active in FMS. Please try again or contact support.');
        } else {
          alert(`Failed to unrequest: ${errorData.detail || errorData.message || 'Unknown error'}`);
        }
        return;
      }

      const data = await response.json();

      if (data.success) {
        // Check if FMS action was performed
        if (data.fms_action === 'delete') {
          alert('✓ Assignment unrequested successfully!\n\nThe request has been deleted from FMS and the assignment is back to planned status.');
        } else {
          alert('✓ Assignment status changed back to planned.');
        }

        // Reload activities to show green bar again
        loadActivities();
      } else {
        alert(`Failed to unrequest: ${data.message || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Unrequest assignment error:', err);
      alert(`Network error: Could not connect to server.\n\n${err.message}`);
    }
  };

  // Handle delete assignment
  const deleteAssignment = async (assignmentId, status) => {
    if (!confirm('Delete this assignment?')) return;

    try {
      let response;

      // If status is 'requested' (magenta), use FMS delete endpoint
      if (status === 'requested') {
        response = await fetch(`${API_BASE_URL}/api/fms/delete-vehicle-request/${assignmentId}`, {
          method: 'DELETE'
        });
      } else {
        // For non-requested assignments (green), use regular delete
        response = await fetch(`${API_BASE_URL}/api/calendar/delete-assignment/${assignmentId}`, {
          method: 'DELETE'
        });
      }

      if (!response.ok) {
        const errorData = await response.json();
        if (response.status === 500 && status === 'requested') {
          alert('⚠️ Failed to delete from FMS.\n\nThe assignment may still exist in FMS. Please try again or contact support.');
        } else {
          alert(`Failed to delete: ${errorData.detail || errorData.message || 'Unknown error'}`);
        }
        return;
      }

      const data = await response.json();

      if (data.success) {
        // Show appropriate success message
        if (status === 'requested' && data.deleted_from_fms) {
          alert('✓ Assignment deleted successfully!\n\nThe request has been deleted from FMS and removed from the scheduler.');
        } else {
          alert('✓ Assignment deleted successfully!');
        }

        // Reload activities
        loadActivities();

        // Emit event so Chain Builder can reload
        EventManager.emit(EventTypes.CALENDAR_DATA_UPDATED, {
          office: selectedOffice,
          action: 'delete',
          assignmentId
        });
      } else {
        alert(`Failed to delete: ${data.message || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Delete assignment error:', err);
      alert(`Network error: Could not connect to server.\n\n${err.message}`);
    }
  };

  const [showTierDropdown, setShowTierDropdown] = useState(false);
  const [showMakeDropdown, setShowMakeDropdown] = useState(false);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('.multi-select-dropdown')) {
        setShowPartnerDropdown(false);
        setShowVehicleDropdown(false);
        setShowTierDropdown(false);
        setShowMakeDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Sorting
  const [sortBy, setSortBy] = useState('make'); // 'make', 'model', 'vin'
  const [sortOrder, setSortOrder] = useState('asc'); // 'asc', 'desc'

  // What-If Mode for drag-drop scenarios
  const [whatIfMode, setWhatIfMode] = useState(false);
  const [scenarioChanges, setScenarioChanges] = useState({});

  // Vehicle context (reuse existing side panel)
  const [selectedVin, setSelectedVin] = useState(null);
  const [vehicleContext, setVehicleContext] = useState(null);
  const [loadingVehicleContext, setLoadingVehicleContext] = useState(false);

  // Chaining opportunities
  const [chainingOpportunities, setChainingOpportunities] = useState(null);
  const [loadingChains, setLoadingChains] = useState(false);

  // Partner context for partner view
  const [selectedPartnerId, setSelectedPartnerId] = useState(null);
  const [partnerContext, setPartnerContext] = useState(null);
  const [showPartnerTimeline, setShowPartnerTimeline] = useState(false);
  const [loadingPartnerContext, setLoadingPartnerContext] = useState(false);

  // Load offices
  const [offices, setOffices] = useState([]);

  // All vehicles and partners for the office (full inventory)
  const [allVehicles, setAllVehicles] = useState([]);
  const [allPartners, setAllPartners] = useState([]);
  const [partnerTiers, setPartnerTiers] = useState({}); // {person_id: {make: rank, ...}}

  useEffect(() => {
    const loadOffices = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/offices`);
        const data = await response.json();
        if (data && data.length > 0) {
          setOffices(data.map(office => office.name));
          if (!data.find(o => o.name === selectedOffice)) {
            setSelectedOffice(data[0].name);
          }
        }
      } catch (err) {
        console.error('Failed to load offices:', err);
        setOffices(['Los Angeles', 'Atlanta', 'Chicago', 'Dallas', 'Denver', 'Detroit', 'Miami', 'Phoenix', 'San Francisco', 'Seattle']);
      }
    };
    loadOffices();
  }, []);

  // Set current month as default and center on today
  useEffect(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const monthStr = `${year}-${month}`;
    setSelectedMonth(monthStr);

    // Center view on today (2 weeks before and after)
    const today = new Date();
    const viewStart = new Date(today);
    viewStart.setDate(today.getDate() - 14);
    const viewEnd = new Date(today);
    viewEnd.setDate(today.getDate() + 14);

    setViewStartDate(viewStart);
    setViewEndDate(viewEnd);
  }, []);

  // When month selector changes, reset view to show full month
  const handleMonthChange = (monthStr) => {
    setSelectedMonth(monthStr);
    const [year, month] = monthStr.split('-');
    const startOfMonth = new Date(parseInt(year), parseInt(month) - 1, 1);
    const endOfMonth = new Date(parseInt(year), parseInt(month), 0);
    setViewStartDate(startOfMonth);
    setViewEndDate(endOfMonth);
  };

  // Slide view forward by 7 days
  const slideForward = () => {
    if (!viewStartDate || !viewEndDate) return;
    const newStart = new Date(viewStartDate);
    const newEnd = new Date(viewEndDate);
    newStart.setDate(newStart.getDate() + 7);
    newEnd.setDate(newEnd.getDate() + 7);
    setViewStartDate(newStart);
    setViewEndDate(newEnd);
    // Clear month selector since we're now in custom range
    setSelectedMonth('');
  };

  // Slide view backward by 7 days
  const slideBackward = () => {
    if (!viewStartDate || !viewEndDate) return;
    const newStart = new Date(viewStartDate);
    const newEnd = new Date(viewEndDate);
    newStart.setDate(newStart.getDate() - 7);
    newEnd.setDate(newEnd.getDate() - 7);
    setViewStartDate(newStart);
    setViewEndDate(newEnd);
    // Clear month selector since we're now in custom range
    setSelectedMonth('');
  };

  // Clear all filters
  const clearAllFilters = () => {
    setVinFilter('');
    setMakeFilter('');
    setPartnerFilter('');
    setActivityFilter('all');
    setSelectedPartners([]);
    setSelectedVehicles([]);
    setSelectedTiers([]);
    setSelectedMakes([]);
    setSortBy('make');
    setSortOrder('asc');
  };

  // Load all vehicles for the office (full inventory)
  useEffect(() => {
    const loadVehicles = async () => {
      if (!selectedOffice) return;
      try {
        const response = await fetch(`${API_BASE_URL}/api/calendar/vehicles?office=${selectedOffice}`);
        if (response.ok) {
          const data = await response.json();
          setAllVehicles(data.vehicles || []);
        }
      } catch (err) {
        console.error('Failed to load vehicles:', err);
      }
    };
    loadVehicles();
  }, [selectedOffice]);

  // Load all media partners for the office (full inventory with distances)
  useEffect(() => {
    const loadPartners = async () => {
      if (!selectedOffice) return;
      try {
        const response = await fetch(`${API_BASE_URL}/api/calendar/media-partners?office=${selectedOffice}`);
        if (response.ok) {
          const data = await response.json();
          setAllPartners(data.partners || []);

          // Build distance cache from partner data
          const distances = {};
          (data.partners || []).forEach(partner => {
            if (partner.distance_miles !== null && partner.distance_miles !== undefined) {
              distances[partner.person_id] = {
                success: true,
                distance_miles: partner.distance_miles,
                location_type: partner.location_type
              };
            }
          });
          setPartnerDistances(distances);
        }

        // Fetch tier data for all partners in one call
        const tierResponse = await fetch(`${API_BASE_URL}/api/calendar/partner-tiers?office=${selectedOffice}`);
        if (tierResponse.ok) {
          const tierData = await tierResponse.json();
          setPartnerTiers(tierData.tiers || {});
        }
      } catch (err) {
        console.error('Failed to load partners:', err);
      }
    };
    loadPartners();
  }, [selectedOffice]);

  // Load activities when tab becomes active or office changes
  useEffect(() => {
    if (isActive && selectedOffice && viewStartDate && viewEndDate) {
      loadActivities();
    }
  }, [isActive, selectedOffice]);

  // Fetch distances for partners with activities (optimization - only fetch what we need)
  useEffect(() => {
    if (selectedOffice && activities.length > 0) {
      const fetchDistances = async () => {
        const distances = { ...partnerDistances }; // Keep existing distances

        // Get unique partners from activities
        const uniquePartners = [...new Set(activities.map(a => a.person_id))];

        // Only fetch distances for partners we don't already have
        const partnersToFetch = uniquePartners.filter(id => !distances[id]);

        for (const personId of partnersToFetch) {
          try {
            const params = new URLSearchParams({
              person_id: personId,
              office: selectedOffice
            });
            const response = await fetch(`${API_BASE_URL}/api/ui/phase7/partner-distance?${params}`);
            if (response.ok) {
              const data = await response.json();
              if (data.success) {
                distances[personId] = data;
              }
            }
          } catch (err) {
            console.error(`Failed to fetch distance for partner ${personId}:`, err);
          }
        }

        setPartnerDistances(distances);
      };

      fetchDistances();
    }
  }, [selectedOffice, activities]);

  // Listen for Chain Builder updates
  useEffect(() => {
    const handleChainDataUpdate = (detail) => {
      console.log('[Calendar] Received chain data update event:', detail);
      // Reload activities if the office matches
      if (detail.office === selectedOffice) {
        console.log('[Calendar] Office matches, reloading activities...');
        loadActivities();
      }
    };

    const handler = EventManager.on(EventTypes.CHAIN_DATA_UPDATED, handleChainDataUpdate);

    // Cleanup on unmount
    return () => {
      EventManager.off(EventTypes.CHAIN_DATA_UPDATED, handler);
    };
  }, [selectedOffice]); // Re-subscribe when office changes

  const loadActivities = async () => {
    if (!selectedOffice || !viewStartDate || !viewEndDate) return;

    setIsLoading(true);
    setError('');

    try {
      // Fetch 3-month buffer (6 weeks back, 12 weeks forward) to show all scheduled chains
      const today = new Date();
      const fetchStart = new Date(today);
      fetchStart.setDate(today.getDate() - 42); // 6 weeks back
      const fetchEnd = new Date(today);
      fetchEnd.setDate(today.getDate() + 84); // 12 weeks forward

      const startDate = fetchStart.toISOString().split('T')[0];
      const endDate = fetchEnd.toISOString().split('T')[0];

      const params = new URLSearchParams({
        office: selectedOffice,
        start_date: startDate,
        end_date: endDate
      });

      const response = await fetch(`${API_BASE_URL}/api/calendar/activity?${params}`);
      if (!response.ok) throw new Error('Failed to fetch activities');

      const data = await response.json();
      setActivities(data.activities || []);
    } catch (err) {
      setError(err.message);
      console.error('Error loading activities:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Helper: Parse date string as local date (YYYY-MM-DD)
  const parseLocalDate = (dateStr) => {
    if (!dateStr || typeof dateStr !== 'string') return null;
    try {
      // Handle ISO format (2025-11-10T00:00:00) by extracting just the date part
      const datePart = dateStr.split('T')[0];
      const parts = datePart.split('-');
      if (parts.length !== 3) return null;
      const [year, month, day] = parts.map(Number);
      if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
      return new Date(year, month - 1, day);
    } catch (e) {
      return null;
    }
  };

  // Helper: Check if activity overlaps with the current view range
  const activityOverlapsMonth = (activity) => {
    if (!viewStartDate || !viewEndDate) return false;

    const rangeStart = new Date(viewStartDate);
    rangeStart.setHours(0, 0, 0, 0);
    const rangeEnd = new Date(viewEndDate);
    rangeEnd.setHours(23, 59, 59, 999);

    const activityStart = parseLocalDate(activity.start_date);
    const activityEnd = parseLocalDate(activity.end_date);

    return activityEnd >= rangeStart && activityStart <= rangeEnd;
  };

  // Group activities by VIN - START with ALL vehicles for office
  const groupedByVin = useMemo(() => {
    const grouped = {};

    // First, add ALL vehicles for this office (full inventory)
    allVehicles.forEach(vehicle => {
      const vehicleActivities = [];

      // Add lifecycle unavailability periods as synthetic activities
      if (viewStartDate && viewEndDate) {
        const rangeStart = new Date(viewStartDate);
        const rangeEnd = new Date(viewEndDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // Check if vehicle is not in service yet (before in_service_date)
        if (vehicle.in_service_date) {
          const inServiceDate = new Date(vehicle.in_service_date);
          // Only show if in_service_date is in the future
          if (inServiceDate > today && inServiceDate > rangeStart) {
            vehicleActivities.push({
              vin: vehicle.vin,
              status: 'unavailable',
              activity_type: 'Not in service yet',
              start_date: rangeStart.toISOString().split('T')[0],
              end_date: new Date(Math.min(inServiceDate.getTime() - 86400000, rangeEnd.getTime())).toISOString().split('T')[0],
              partner_name: 'Not in service'
            });
          }
        }

        // Note: expected_turn_in_date is shown in vehicle info, not as unavailability
        // Turn-in is a soft date, vehicles can still have loans before it
      }

      grouped[vehicle.vin] = {
        vin: vehicle.vin,
        make: vehicle.make,
        model: vehicle.model,
        office: vehicle.office,
        in_service_date: vehicle.in_service_date,
        expected_turn_in_date: vehicle.expected_turn_in_date,
        activities: vehicleActivities
      };
    });

    // Then, add actual loan activities to vehicles
    activities.forEach(activity => {
      const vin = activity.vin;
      if (grouped[vin]) {
        grouped[vin].activities.push(activity);
      }
    });

    return grouped;
  }, [allVehicles, activities, viewStartDate, viewEndDate]);

  // Group activities by Partner - START with ALL partners for office
  const groupedByPartner = useMemo(() => {
    const grouped = {};

    // First, add ALL partners for this office (full inventory)
    allPartners.forEach(partner => {
      grouped[partner.person_id] = {
        person_id: partner.person_id,
        partner_name: partner.name,
        office: partner.office,
        activities: []
      };
    });

    // Then, add activities to partners that have them
    activities.forEach(activity => {
      const partnerId = activity.person_id;
      if (grouped[partnerId]) {
        grouped[partnerId].activities.push(activity);
      }
    });

    return grouped;
  }, [allPartners, activities]);

  // Apply filters based on view mode
  const filteredVins = Object.values(groupedByVin).filter(vehicle => {
    // Multi-select vehicle filter
    if (selectedVehicles.length > 0 && !selectedVehicles.includes(vehicle.vin)) return false;

    // Activity filter
    const hasActivityThisMonth = vehicle.activities.some(a => activityOverlapsMonth(a));
    if (activityFilter === 'with-activity' && !hasActivityThisMonth) return false;
    if (activityFilter === 'no-activity' && hasActivityThisMonth) return false;

    // Multi-select make filter
    if (selectedMakes.length > 0 && !selectedMakes.includes(vehicle.make)) return false;

    // Other filters
    if (vinFilter && !vehicle.vin.toLowerCase().includes(vinFilter.toLowerCase())) return false;
    if (makeFilter && vehicle.make !== makeFilter) return false;
    if (partnerFilter) {
      const hasPartner = vehicle.activities.some(a =>
        a.partner_name?.toLowerCase().includes(partnerFilter.toLowerCase())
      );
      if (!hasPartner) return false;
    }
    return true;
  });

  const filteredPartners = Object.values(groupedByPartner).filter(partner => {
    // Multi-select partner filter
    if (selectedPartners.length > 0 && !selectedPartners.includes(partner.person_id)) return false;

    // Tier filter - show partners who have selected tier(s) for the selected make (or any make if no make selected)
    if (selectedTiers.length > 0) {
      const partnerTierData = partnerTiers[partner.person_id];
      if (!partnerTierData) return false; // Partner has no approved makes

      let hasTier = false;
      if (makeFilter) {
        // Check if partner has selected tier for the filtered make
        const rank = partnerTierData[makeFilter];
        if (rank && selectedTiers.includes(rank)) {
          hasTier = true;
        }
      } else {
        // Check if partner has selected tier for ANY make
        const ranks = Object.values(partnerTierData);
        if (ranks.some(rank => selectedTiers.includes(rank))) {
          hasTier = true;
        }
      }
      if (!hasTier) return false;
    }

    // Activity filter
    const hasActivityThisMonth = partner.activities.some(a => activityOverlapsMonth(a));
    if (activityFilter === 'with-activity' && !hasActivityThisMonth) return false;
    if (activityFilter === 'no-activity' && hasActivityThisMonth) return false;

    // Other filters
    if (partnerFilter && !partner.partner_name.toLowerCase().includes(partnerFilter.toLowerCase())) return false;

    // Make filter - behavior depends on Activity filter
    if (makeFilter) {
      if (activityFilter === 'all') {
        // Show ALL partners approved for this make (check tier data)
        const partnerTierData = partnerTiers[partner.person_id];
        const isApprovedForMake = partnerTierData && partnerTierData[makeFilter];
        if (!isApprovedForMake) return false;
      } else {
        // Show only partners with activities of this make
        const hasMake = partner.activities.some(a => a.make === makeFilter);
        if (!hasMake) return false;
      }
    }
    if (vinFilter) {
      const hasVin = partner.activities.some(a =>
        a.vin?.toLowerCase().includes(vinFilter.toLowerCase())
      );
      if (!hasVin) return false;
    }
    return true;
  });

  // Apply sorting to vehicle view
  const sortedVins = [...filteredVins].sort((a, b) => {
    let compareA, compareB;

    switch (sortBy) {
      case 'make':
        compareA = a.make || '';
        compareB = b.make || '';
        break;
      case 'model':
        compareA = a.model || '';
        compareB = b.model || '';
        break;
      case 'vin':
        compareA = a.vin || '';
        compareB = b.vin || '';
        break;
      default:
        compareA = a.make || '';
        compareB = b.make || '';
    }

    const comparison = compareA.localeCompare(compareB);
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  // Sort partners by LAST name, respecting sort order
  const sortedPartners = filteredPartners.sort((a, b) => {
    const nameA = a.partner_name || '';
    const nameB = b.partner_name || '';
    
    // Extract last name (last word in the name) and clean special characters
    const getCleanLastName = (name) => {
      const parts = name.trim().split(/\s+/);
      const lastName = parts[parts.length - 1] || '';
      // Remove leading special characters like quotes, parentheses, brackets
      return lastName.replace(/^[^\w]+/, '');
    };
    
    const lastNameA = getCleanLastName(nameA);
    const lastNameB = getCleanLastName(nameB);
    
    const comparison = lastNameA.localeCompare(lastNameB);
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  // Choose which data to display based on view mode
  const displayData = viewMode === 'vehicle' ? sortedVins : sortedPartners;

  // Get unique makes for filter
  const uniqueMakes = [...new Set(activities.map(a => a.make).filter(Boolean))].sort();

  // Fetch vehicle context
  const fetchVehicleContext = async (vin) => {
    if (vehicleContext && vehicleContext.vin === vin) return;

    setLoadingVehicleContext(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/ui/phase7/vehicle-context/${vin}`);
      if (!response.ok) throw new Error('Failed to fetch vehicle context');
      const data = await response.json();
      setVehicleContext(data);
    } catch (err) {
      console.error('Error fetching vehicle context:', err);
      setVehicleContext(null);
    } finally {
      setLoadingVehicleContext(false);
    }
  };

  const handleActivityClick = async (vin) => {
    setSelectedVin(vin);
    setLoadingVehicleContext(true);

    try {
      // Fetch full enhanced vehicle context from API
      const vehicleResponse = await fetch(`${API_BASE_URL}/api/ui/phase7/vehicle-context/${vin}`);
      if (vehicleResponse.ok) {
        const vehicleData = await vehicleResponse.json();
        setVehicleContext(vehicleData);

        // Fetch chaining opportunities if vehicle has current activity
        if (vehicleData.current_activity && selectedOffice) {
          setLoadingChains(true);
          try {
            const params = new URLSearchParams({
              office: selectedOffice,
              max_distance: 50
            });
            const chainResponse = await fetch(`${API_BASE_URL}/api/ui/phase7/vehicle-chains/${vin}?${params}`);
            if (chainResponse.ok) {
              const chainData = await chainResponse.json();
              setChainingOpportunities(chainData);
            }
          } catch (err) {
            console.error('Failed to fetch chaining opportunities:', err);
            setChainingOpportunities(null);
          } finally {
            setLoadingChains(false);
          }
        } else {
          setChainingOpportunities(null);
        }
      } else {
        console.error('Failed to fetch vehicle context');
        setVehicleContext(null);
      }
    } catch (err) {
      console.error('Error in handleActivityClick:', err);
      setVehicleContext(null);
    } finally {
      setLoadingVehicleContext(false);
    }
  };

  const handlePartnerClick = async (partnerId, partnerName) => {
    setSelectedPartnerId(partnerId);
    setLoadingPartnerContext(true);

    try {
      // Get ALL activities for this partner - same data source as Gantt chart
      // Use == to handle string/number type mismatch
      const partnerActivities = activities.filter(a => a.person_id == partnerId);

      // Get partner info from allPartners list
      const partnerInfo = allPartners.find(p => p.person_id === partnerId);
      const partnerOffice = partnerInfo?.office || selectedOffice;

      if (partnerActivities.length > 0) {
        const sortedActivities = [...partnerActivities].sort((a, b) =>
          new Date(a.start_date) - new Date(b.start_date)
        );

        // Filter by status - matching Gantt chart colors exactly
        const currentLoans = sortedActivities.filter(a => a.status === 'active');
        const recommendedLoans = sortedActivities.filter(a => a.status === 'planned');
        const requestedLoans = sortedActivities.filter(a => a.status === 'requested');

        const partnerAddress = partnerActivities[0].partner_address;
        const office = partnerActivities[0].office;

        // Fetch distance from office using cached lat/lon from media_partners
        let distanceInfo = null;
        try {
          const params = new URLSearchParams({
            person_id: partnerId,
            office: office
          });
          const distanceResponse = await fetch(`${API_BASE_URL}/api/ui/phase7/partner-distance?${params}`);
          if (distanceResponse.ok) {
            distanceInfo = await distanceResponse.json();
          }
        } catch (err) {
          console.error('Failed to fetch distance:', err);
        }

        // Fetch approved makes from partner-intelligence endpoint
        let approvedMakes = [];
        let intelligenceData = null;
        try {
          const intelligenceParams = new URLSearchParams({
            person_id: partnerId,
            office: office
          });
          const intelligenceResponse = await fetch(`${API_BASE_URL}/api/ui/phase7/partner-intelligence?${intelligenceParams}`);
          if (intelligenceResponse.ok) {
            intelligenceData = await intelligenceResponse.json();
            approvedMakes = intelligenceData.approved_makes || [];
          }
        } catch (err) {
          console.error('Failed to fetch partner intelligence:', err);
        }

        // Build context object with timeline
        const context = {
          person_id: partnerId,
          partner_name: partnerName,
          office: office,
          region: partnerActivities[0].region || 'N/A',
          partner_address: partnerAddress || 'N/A',
          distance_info: distanceInfo,
          approved_makes: intelligenceData?.approved_makes || approvedMakes,
          budget_status: intelligenceData?.budget_status || {},
          current_quarter: intelligenceData?.current_quarter || null,
          publication_by_make: intelligenceData?.publication_by_make || {},
          stats: intelligenceData?.stats || {},
          current_loans: currentLoans.map(loan => ({
            vin: loan.vin,
            make: loan.make,
            model: loan.model,
            start_date: loan.start_date,
            end_date: loan.end_date,
            status: loan.status
          })),
          recommended_loans: recommendedLoans.map(loan => ({
            vin: loan.vin,
            make: loan.make,
            model: loan.model,
            start_date: loan.start_date,
            end_date: loan.end_date,
            status: loan.status
          })),
          requested_loans: requestedLoans.map(loan => ({
            vin: loan.vin,
            make: loan.make,
            model: loan.model,
            start_date: loan.start_date,
            end_date: loan.end_date,
            status: loan.status
          })),
          timeline: sortedActivities
        };

        setPartnerContext(context);
      } else {
        // Partner has no activities - still show context with basic info
        let distanceInfo = partnerDistances[partnerId] || null;
        let approvedMakes = [];
        let intelligenceData = null;

        // Fetch approved makes
        try {
          const intelligenceParams = new URLSearchParams({
            person_id: partnerId,
            office: partnerOffice
          });
          const intelligenceResponse = await fetch(`${API_BASE_URL}/api/ui/phase7/partner-intelligence?${intelligenceParams}`);
          if (intelligenceResponse.ok) {
            intelligenceData = await intelligenceResponse.json();
            approvedMakes = intelligenceData.approved_makes || [];
          }
        } catch (err) {
          console.error('Failed to fetch partner intelligence:', err);
        }

        const context = {
          person_id: partnerId,
          partner_name: partnerName,
          office: partnerOffice,
          region: 'N/A',
          partner_address: partnerInfo?.address || 'N/A',
          distance_info: distanceInfo,
          approved_makes: intelligenceData?.approved_makes || approvedMakes,
          budget_status: intelligenceData?.budget_status || {},
          current_quarter: intelligenceData?.current_quarter || null,
          publication_by_make: intelligenceData?.publication_by_make || {},
          stats: intelligenceData?.stats || {},
          current_loans: [],
          recommended_loans: [],
          timeline: []
        };

        setPartnerContext(context);
      }
    } catch (error) {
      console.error('Error in handlePartnerClick:', error);
      setPartnerContext(null);
    } finally {
      setLoadingPartnerContext(false);
    }
  };

  const closeSidePanel = () => {
    setSelectedVin(null);
    setVehicleContext(null);
    setSelectedPartnerId(null);
    setPartnerContext(null);
    setChainingOpportunities(null);
  };

  // Helper function for tier badge colors
  const getTierBadgeColor = (rank) => {
    // Handle both numeric (1,2,3,4) and letter-based (A, A+, B, C, D) ranks
    const normalizedRank = typeof rank === 'string' ? rank.toUpperCase().trim() : rank;

    // Check for A+ (premium tier) - GREEN background with DARK GREEN border
    if (normalizedRank === 'A+') {
      return 'bg-green-100 text-green-800 border-green-600'
    }

    // Check for A variants (A, etc) - GREEN (best tier)
    if (normalizedRank === 1 || normalizedRank === 'TA' || normalizedRank === 'A' ||
        (typeof normalizedRank === 'string' && normalizedRank.startsWith('A'))) {
      return 'bg-green-100 text-green-800 border-green-300'
    }

    switch(normalizedRank) {
      case 2:
      case 'TB':
      case 'B':
        return 'bg-blue-100 text-blue-800 border-blue-300'
      case 3:
      case 'TC':
      case 'C':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300'
      case 4:
      case 'TD':
      case 'D':
        return 'bg-gray-100 text-gray-800 border-gray-300'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  };

  const formatActivityDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = parseLocalDate(dateStr);
    if (!date || isNaN(date.getTime())) return 'Invalid Date';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const formatFullDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = parseLocalDate(dateStr);
    if (!date || isNaN(date.getTime())) return 'Invalid Date';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const getActivityColor = (activity, locationColor) => {
    // Use location-based color if provided (for vehicle view)
    if (locationColor && viewMode === 'vehicle') {
      switch (locationColor) {
        case 'green': return 'bg-gradient-to-br from-green-500 to-green-600 border-2 border-green-700';
        case 'yellow': return 'bg-gradient-to-br from-yellow-400 to-yellow-500 border-2 border-yellow-600';
        case 'red': return 'bg-gradient-to-br from-red-500 to-red-600 border-2 border-red-700';
        case 'gray': return 'bg-gradient-to-br from-gray-400 to-gray-500 border-2 border-gray-600';
      }
    }

    // Default status-based colors
    switch (activity.status) {
      case 'completed': return 'bg-gradient-to-br from-gray-400 to-gray-500 border-2 border-gray-600';
      case 'active': return 'bg-gradient-to-br from-blue-500 to-blue-600 border-2 border-blue-700';
      case 'planned':
        // Optimizer/Chain Builder recommendation: solid green border
        return 'bg-gradient-to-br from-green-400 to-green-500 border-2 border-green-600';
      case 'manual':
        // Manual Chain Builder pick: dashed green border to distinguish
        return 'bg-gradient-to-br from-green-400 to-green-500 border-2 border-dashed border-green-600';
      case 'requested':
        // Sent to FMS, awaiting approval: magenta/pink
        return 'bg-gradient-to-br from-pink-500 to-pink-600 border-2 border-pink-700';
      case 'unavailable':
        // Lifecycle unavailability (not in service, turn-in, etc)
        return 'bg-gradient-to-br from-orange-400 to-orange-500 border-2 border-orange-600';
      default: return 'bg-gradient-to-br from-gray-300 to-gray-400 border-2 border-gray-500';
    }
  };

  const getActivityLabel = (status) => {
    switch (status) {
      case 'completed': return 'Past';
      case 'active': return 'Active';
      case 'planned': return 'Proposed (AI)';
      case 'manual': return 'Proposed (Manual)';
      case 'requested': return 'Requested (FMS)';
      default: return status;
    }
  };

  // Determine vehicle location based on activity
  const getVehicleLocation = (activity) => {
    // Get distance info if available
    const distanceInfo = partnerDistances[activity.person_id];

    // If active, vehicle is with the partner
    if (activity.status === 'active') {
      const locationType = distanceInfo?.location_type || 'unknown';
      const distance = distanceInfo?.distance_miles;

      if (locationType === 'local') {
        return {
          type: 'local',
          label: `🏠 Local (${distance || '?'} mi)`,
          badge: '🏠',
          color: null  // Don't override bar color, just show badge
        };
      } else if (locationType === 'remote') {
        return {
          type: 'remote',
          label: `✈️ Remote (${distance || '?'} mi)`,
          badge: '✈️',
          color: null  // Don't override bar color, just show badge
        };
      }
      return {
        type: 'partner',
        label: `📍 With ${activity.partner_name}`,
        badge: '📍',
        color: null  // Don't override bar color
      };
    }

    // If planned, vehicle will be picked up
    if (activity.status === 'planned') {
      const locationType = distanceInfo?.location_type || 'unknown';
      const distance = distanceInfo?.distance_miles;

      if (locationType === 'local') {
        return {
          type: 'local-planned',
          label: `📅 Local (${distance || '?'} mi)`,
          badge: '🏠',
          color: null  // Don't override bar color, just show badge
        };
      } else if (locationType === 'remote') {
        return {
          type: 'remote-planned',
          label: `📅 Remote (${distance || '?'} mi)`,
          badge: '✈️',
          color: null  // Don't override bar color, just show badge
        };
      }
      // If we don't have distance info, don't return a color - let it use default green for 'planned'
      return null;
    }

    // If completed, vehicle should be back at office
    if (activity.status === 'completed') {
      return {
        type: 'office',
        label: '🏢 At Office',
        badge: '🏢',
        color: null  // Don't override - completed should always be grey
      };
    }

    return null;
  };

  // Detect chaining opportunity (vehicle could go to next partner instead of returning to office)
  const detectChainingOpportunity = (activities, currentIdx) => {
    if (currentIdx >= activities.length - 1) return false;

    const current = activities[currentIdx];
    const next = activities[currentIdx + 1];

    // Check if current activity ends and next starts within 3 days (potential chain)
    const currentEnd = new Date(current.end_date);
    const nextStart = new Date(next.start_date);
    const daysDiff = (nextStart - currentEnd) / (1000 * 60 * 60 * 24);

    return daysDiff >= 0 && daysDiff <= 3 && current.status !== 'completed';
  };

  // Generate days in the current view range
  const getDaysInView = () => {
    if (!viewStartDate || !viewEndDate) return [];
    const days = [];
    const current = new Date(viewStartDate);
    const end = new Date(viewEndDate);

    while (current <= end) {
      days.push(new Date(current));
      current.setDate(current.getDate() + 1);
    }
    return days;
  };

  const daysInView = getDaysInView();

  // Calculate bar position and width for Gantt chart
  const getBarStyle = (activity) => {
    if (!viewStartDate || !viewEndDate) return { left: 0, width: 0 };

    const rangeStart = new Date(viewStartDate);
    rangeStart.setHours(0, 0, 0, 0); // Reset to midnight to match parseLocalDate behavior
    const rangeEnd = new Date(viewEndDate);
    rangeEnd.setHours(0, 0, 0, 0); // Reset to midnight

    const activityStart = parseLocalDate(activity.start_date);
    const activityEnd = parseLocalDate(activity.end_date);

    // Clamp to view range boundaries
    const startDate = activityStart < rangeStart ? rangeStart : activityStart;
    const endDate = activityEnd > rangeEnd ? rangeEnd : activityEnd;

    // Calculate position as percentage based on days from range start
    const totalDays = daysInView.length;
    const startDayOffset = Math.floor((startDate - rangeStart) / (1000 * 60 * 60 * 24));
    const endDayOffset = Math.floor((endDate - rangeStart) / (1000 * 60 * 60 * 24));

    // Center bars on start/end dates (0.5 offset to bisect the day squares)
    const left = ((startDayOffset + 0.5) / totalDays) * 100;
    const width = ((endDayOffset - startDayOffset) / totalDays) * 100;

    return { left: `${left}%`, width: `${width}%` };
  };

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header - Compact */}
      <div className="bg-white border-b px-6 py-2">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <h1 className="!text-base font-semibold text-gray-900">📅 Calendar</h1>
            <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 border border-blue-200">
              📍 {selectedOffice}
            </span>
            <p className="text-xs text-gray-500">Vehicle activity timeline</p>
          </div>

          {/* View Mode Toggle and What-If Mode */}
          <div className="flex gap-3 items-center">
            {/* Reload Button */}
            <button
              onClick={() => loadActivities()}
              disabled={isLoading}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm text-blue-600 hover:bg-blue-50 disabled:opacity-50"
              title="Reload calendar data"
            >
              {isLoading ? 'Loading...' : '🔄 Reload'}
            </button>

            <div className="flex bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setViewMode('vehicle')}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  viewMode === 'vehicle'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                🚗 By Vehicle
              </button>
              <button
                onClick={() => setViewMode('partner')}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  viewMode === 'partner'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                👤 By Media Partner
              </button>
            </div>

            {/* What-If Mode Toggle */}
            <button
              onClick={() => {
                setWhatIfMode(!whatIfMode);
                if (whatIfMode) {
                  setScenarioChanges({});
                }
              }}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                whatIfMode
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {whatIfMode ? '✓ What-If Mode' : '🔄 What-If Mode'}
            </button>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white border-b px-6 py-2">
        <div className="flex flex-wrap gap-3 items-end">
          <div className="w-40">
            <label className="block text-xs font-medium text-gray-700 mb-1">Office</label>
            <select
              value={selectedOffice}
              onChange={(e) => handleOfficeChange(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              {offices.map(office => (
                <option key={office} value={office}>{office}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Month</label>
            <div className="flex gap-1">
              <button
                onClick={slideBackward}
                className="px-1.5 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50 text-xs flex-shrink-0"
                title="Go back 7 days"
              >
                ←
              </button>
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => handleMonthChange(e.target.value)}
                className="w-28 border border-gray-300 rounded-md px-1 py-1.5 text-xs"
              />
              <button
                onClick={slideForward}
                className="px-1.5 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50 text-xs flex-shrink-0"
                title="Go forward 7 days"
              >
                →
              </button>
            </div>
          </div>

          <div className="relative multi-select-dropdown w-48">
            <label className="block text-xs font-medium text-gray-700 mb-1">Vehicles</label>
            <button
              onClick={() => {
                setShowVehicleDropdown(!showVehicleDropdown);
                if (showVehicleDropdown) setVehicleSearchQuery('');
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-left bg-white hover:bg-gray-50 flex justify-between items-center"
            >
              <span>{selectedVehicles.length > 0 ? `${selectedVehicles.length} selected` : 'All'}</span>
              <span>▼</span>
            </button>
            {showVehicleDropdown && (
              <div className="absolute z-50 mt-1 min-w-max bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                <div className="p-2 border-b sticky top-0 bg-white">
                  <button
                    onClick={() => setSelectedVehicles([])}
                    className="text-xs text-blue-600 hover:text-blue-800 block mb-2 w-full text-left"
                  >
                    Clear All
                  </button>
                  <input
                    type="text"
                    placeholder="Search vehicles..."
                    value={vehicleSearchQuery}
                    onChange={(e) => setVehicleSearchQuery(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                {allVehicles.filter(vehicle => {
                  if (vehicleSearchQuery === '') return true;
                  const searchLower = vehicleSearchQuery.toLowerCase();
                  return (
                    vehicle.make.toLowerCase().includes(searchLower) ||
                    vehicle.model.toLowerCase().includes(searchLower) ||
                    vehicle.vin.toLowerCase().includes(searchLower)
                  );
                }).map(vehicle => (
                  <label
                    key={vehicle.vin}
                    className="flex items-center px-2 py-1.5 hover:bg-gray-50 cursor-pointer text-xs whitespace-nowrap"
                  >
                    <input
                      type="checkbox"
                      checked={selectedVehicles.includes(vehicle.vin)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedVehicles([...selectedVehicles, vehicle.vin]);
                        } else {
                          setSelectedVehicles(selectedVehicles.filter(vin => vin !== vehicle.vin));
                        }
                      }}
                      className="mr-2"
                    />
                    <span>
                      {vehicle.make} {vehicle.model}
                      <span className="text-gray-500 ml-1">(...{vehicle.vin.slice(-5)})</span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="relative multi-select-dropdown w-40">
            <label className="block text-xs font-medium text-gray-700 mb-1">Make</label>
            <button
              onClick={() => setShowMakeDropdown(!showMakeDropdown)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-left bg-white hover:bg-gray-50 flex justify-between items-center"
            >
              <span>{selectedMakes.length > 0 ? `${selectedMakes.length} selected` : 'All'}</span>
              <span>▼</span>
            </button>
            {showMakeDropdown && (
              <div className="absolute z-50 mt-1 w-48 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                <div className="p-2 border-b sticky top-0 bg-white">
                  <button
                    onClick={() => setSelectedMakes([])}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Clear All
                  </button>
                </div>
                {uniqueMakes.map(make => (
                  <label
                    key={make}
                    className="flex items-center px-2 py-1.5 hover:bg-gray-50 cursor-pointer text-xs"
                  >
                    <input
                      type="checkbox"
                      checked={selectedMakes.includes(make)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedMakes([...selectedMakes, make]);
                        } else {
                          setSelectedMakes(selectedMakes.filter(m => m !== make));
                        }
                      }}
                      className="mr-2"
                    />
                    <span>{make}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="relative multi-select-dropdown w-32">
            <label className="block text-xs font-medium text-gray-700 mb-1">Tier</label>
            <button
              onClick={() => setShowTierDropdown(!showTierDropdown)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-left bg-white hover:bg-gray-50 flex justify-between items-center"
            >
              <span>{selectedTiers.length > 0 ? `${selectedTiers.length} selected` : 'All'}</span>
              <span>▼</span>
            </button>
            {showTierDropdown && (
              <div className="absolute z-50 mt-1 w-40 bg-white border border-gray-300 rounded-md shadow-lg">
                <div className="p-2 border-b sticky top-0 bg-white">
                  <button
                    onClick={() => setSelectedTiers([])}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Clear All
                  </button>
                </div>
                {['A+', 'A', 'B', 'C'].map(tier => (
                  <label
                    key={tier}
                    className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedTiers.includes(tier)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedTiers([...selectedTiers, tier]);
                        } else {
                          setSelectedTiers(selectedTiers.filter(t => t !== tier));
                        }
                      }}
                      className="mr-2"
                    />
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getTierBadgeColor(tier)}`}>
                      {tier}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="relative multi-select-dropdown w-48">
            <label className="block text-xs font-medium text-gray-700 mb-1">Partners</label>
            <button
              onClick={() => setShowPartnerDropdown(!showPartnerDropdown)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-left bg-white hover:bg-gray-50 flex justify-between items-center"
            >
              <span>{selectedPartners.length > 0 ? `${selectedPartners.length} selected` : 'All'}</span>
              <span>▼</span>
            </button>
            {showPartnerDropdown && (
              <div className="absolute z-50 mt-1 w-96 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                <div className="p-2 border-b sticky top-0 bg-white space-y-2">
                  <input
                    type="text"
                    placeholder="Type to search partners..."
                    value={partnerFilter}
                    onChange={(e) => setPartnerFilter(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                  />
                  <button
                    onClick={() => setSelectedPartners([])}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Clear All
                  </button>
                </div>
                {allPartners
                  .filter(p => p.name.toLowerCase().includes(partnerFilter.toLowerCase()))
                  .sort((a, b) => {
                    // Sort by last name (last word in name)
                    const getLastName = (name) => name.trim().split(/\s+/).pop();
                    return getLastName(a.name).localeCompare(getLastName(b.name));
                  })
                  .map(partner => (
                  <label
                    key={partner.person_id}
                    className="flex items-center px-2 py-1.5 hover:bg-gray-50 cursor-pointer text-xs"
                  >
                    <input
                      type="checkbox"
                      checked={selectedPartners.includes(partner.person_id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedPartners([...selectedPartners, partner.person_id]);
                        } else {
                          setSelectedPartners(selectedPartners.filter(id => id !== partner.person_id));
                        }
                      }}
                      className="mr-2"
                    />
                    <span className="flex-1 truncate">{formatPartnerName(partner.name, 'lastFirst')}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="w-32">
            <label className="block text-xs font-medium text-gray-700 mb-1">Activity</label>
            <select
              value={activityFilter}
              onChange={(e) => setActivityFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="all">All</option>
              <option value="with-activity">With</option>
              <option value="no-activity">None</option>
            </select>
          </div>

          <div className="w-32">
            <label className="block text-xs font-medium text-gray-700 mb-1">Sort</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="make">Make</option>
              <option value="model">Model</option>
              <option value="vin">VIN</option>
            </select>
          </div>

          <div className="w-32">
            <label className="block text-xs font-medium text-gray-700 mb-1">Order</label>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="asc">A → Z</option>
              <option value="desc">Z → A</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={clearAllFilters}
              className="px-3 py-1.5 bg-red-50 border border-red-300 text-red-700 rounded-md hover:bg-red-100 text-xs font-medium"
            >
              Clear All
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-6 mt-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-gray-400 rounded"></div>
            <span className="text-gray-600">Past</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-blue-500 rounded"></div>
            <span className="text-gray-600">Active</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-400 rounded border-2 border-green-600"></div>
            <span className="text-gray-600">🤖 Proposed (AI)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-400 rounded border-2 border-dashed border-green-600"></div>
            <span className="text-gray-600">Proposed (Manual)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-pink-500 rounded border-2 border-pink-700"></div>
            <span className="text-gray-600">📤 Requested (FMS)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-orange-400 rounded"></div>
            <span className="text-gray-600">Unavailable</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg">📍</span>
            <span className="text-gray-600">Current Location</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg">⛓️</span>
            <span className="text-gray-600">Chaining Opportunity</span>
          </div>
        </div>
      </div>

      {/* Gantt Chart Content - Scrollable Container */}
      <div className="px-6 pb-6 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            Error: {error}
          </div>
        ) : displayData.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border p-12 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p className="mt-2 text-sm text-gray-500">No activity found</p>
            <p className="text-xs text-gray-400 mt-1">Try adjusting your filters or select a different month</p>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm border">
            {/* Gantt Chart Header - Sticky */}
            <div className="flex border-b-2 bg-gray-50 sticky top-0 z-10 overflow-x-auto shadow-md">
              {/* Row label column */}
              <div className="w-64 flex-shrink-0 px-4 py-4 border-r font-medium text-sm text-gray-700 bg-gray-50">
                {viewMode === 'vehicle' ? 'Vehicle' : 'Media Partner'}
              </div>
              {/* Days column */}
              <div className="flex-1 flex">
                {daysInView.map((date, idx) => {
                  const dayOfWeek = date.getDay();
                  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                  const dayNum = date.getDate();
                  const monthName = date.toLocaleDateString('en-US', { month: 'short' });

                  return (
                    <div
                      key={idx}
                      className={`flex-1 text-center text-xs py-4 border-r ${
                        isWeekend ? 'bg-blue-100 text-blue-800 font-semibold' : 'bg-gray-50 text-gray-600'
                      }`}
                    >
                      <div>{monthName} {dayNum}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Gantt Chart Rows */}
            <div className="divide-y divide-gray-300 overflow-x-auto">
              {displayData.map((item) => {
                // Calculate how many rows we need based on overlapping activities
                const filteredActs = item.activities.filter(activity => activityOverlapsMonth(activity));

                // Detect overlaps and assign row positions
                const activitiesWithRows = filteredActs.map((activity, idx) => {
                  // Check if this activity overlaps with any previous activity
                  let rowIndex = 0;
                  const actStart = parseLocalDate(activity.start_date);
                  const actEnd = parseLocalDate(activity.end_date);

                  for (let i = 0; i < idx; i++) {
                    const prevAct = filteredActs[i];
                    const prevStart = parseLocalDate(prevAct.start_date);
                    const prevEnd = parseLocalDate(prevAct.end_date);

                    // Check if dates overlap
                    if (actStart <= prevEnd && actEnd >= prevStart) {
                      rowIndex = Math.max(rowIndex, (filteredActs[i].rowIndex || 0) + 1);
                    }
                  }

                  activity.rowIndex = rowIndex;
                  return activity;
                });

                const maxRows = Math.max(1, ...activitiesWithRows.map(a => (a.rowIndex || 0) + 1));
                const rowHeight = maxRows * 32; // 32px per row (h-8)
                const totalHeight = rowHeight + 40; // Add padding

                return (
                <div key={viewMode === 'vehicle' ? item.vin : item.person_id} className="flex hover:bg-gray-50" style={{ minHeight: `${totalHeight}px` }}>
                  {/* Row info */}
                  <div className="w-64 flex-shrink-0 px-4 py-3 border-r flex items-start min-h-full">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (viewMode === 'vehicle') {
                          handleActivityClick(item.vin);
                        } else {
                          handlePartnerClick(item.person_id, item.partner_name);
                        }
                      }}
                      className="text-left w-full group"
                    >
                      {viewMode === 'vehicle' ? (
                        <div className="w-full">
                          <h3 className="font-semibold text-sm text-gray-900 group-hover:text-blue-600">
                            {item.make} {item.model}
                          </h3>
                          <a
                            href={`https://fms.driveshop.com/vehicles/list_activities/${item.vehicle_id || item.vin}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-xs font-mono text-blue-600 hover:text-blue-800 hover:underline"
                            title="Open in FMS"
                          >
                            {item.vin}
                          </a>
                          {item.expected_turn_in_date && (
                            <p className="text-xs text-orange-600 mt-1">
                              Expected Turn-In: {formatFullDate(item.expected_turn_in_date)}
                            </p>
                          )}
                        </div>
                      ) : (
                        <>
                          <h3 className="font-semibold text-sm text-gray-900 group-hover:text-blue-600">
                            {formatPartnerName(item.partner_name, 'lastFirst')}
                          </h3>
                          {partnerDistances[item.person_id] && (
                            <div className="flex items-center gap-1 mt-1">
                              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                                partnerDistances[item.person_id].location_type === 'local'
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}>
                                {partnerDistances[item.person_id].location_type === 'local' ? '🏠' : '✈️'}
                              </span>
                              <span className="text-xs text-gray-600">
                                {partnerDistances[item.person_id].distance_miles} mi
                              </span>
                            </div>
                          )}
                        </>
                      )}
                    </button>
                  </div>

                  {/* Timeline bars */}
                  <div className="flex-1 relative">
                    {/* Day grid with weekend backgrounds */}
                    <div className="absolute inset-0 flex">
                      {daysInView.map((date, idx) => {
                        const dayOfWeek = date.getDay();
                        const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

                        return (
                          <div
                            key={idx}
                            className={`flex-1 border-r border-gray-300 ${
                              isWeekend ? 'bg-blue-50' : ''
                            }`}
                          ></div>
                        );
                      })}
                    </div>

                    {/* Activity bars */}
                    {activitiesWithRows.map((activity, idx) => {
                        const barStyle = getBarStyle(activity);
                        const label = viewMode === 'vehicle' ? activity.partner_name : `${activity.make} ${activity.model}`;
                        const vinSuffix = activity.vin ? activity.vin.slice(-6) : '';
                        const location = getVehicleLocation(activity);
                        const hasChaining = viewMode === 'vehicle' && detectChainingOpportunity(item.activities, item.activities.indexOf(activity));
                        const topOffset = 16 + (activity.rowIndex * 32); // Start at 16px from top, then 32px per row

                        const color = getActivityColor(activity, location?.color);

                        return (
                          <div
                            key={idx}
                            className={`absolute h-7 ${color} ${hasChaining ? 'ring-2 ring-yellow-400 ring-offset-1' : ''} rounded-lg shadow-lg hover:shadow-xl hover:z-20 transition-all flex items-center text-white text-xs font-semibold px-2 overflow-hidden group`}
                            style={{ left: barStyle.left, width: barStyle.width, minWidth: '20px', top: `${topOffset}px` }}
                            title={`${label}\nVIN: ...${vinSuffix}\n${formatActivityDate(activity.start_date)} - ${formatActivityDate(activity.end_date)}\n${location ? location.label : ''}${hasChaining ? '\n⛓️ Chaining opportunity!' : ''}`}
                          >
                            {/* Main content - clickable */}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (viewMode === 'vehicle') {
                                  // In vehicle view, bars show partners → open Partner Context
                                  handlePartnerClick(activity.person_id, activity.partner_name);
                                } else {
                                  // In partner view, bars show vehicles → open Vehicle Context
                                  handleActivityClick(activity.vin);
                                }
                              }}
                              className="flex items-center gap-1 flex-1 cursor-pointer"
                            >
                              {activity.status === 'planned' && <span className="text-xs">🤖</span>}
                              {activity.status === 'manual' && <span className="text-xs">✋</span>}
                              {activity.status === 'requested' && <span className="text-xs">📤</span>}
                              {location?.badge && <span className="text-sm">{location.badge}</span>}
                              {hasChaining && <span>⛓️</span>}
                              <span className="truncate">{label}</span>
                            </button>

                            {/* Hover actions - only for editable statuses */}
                            {(activity.status === 'planned' || activity.status === 'manual' || activity.status === 'requested') && activity.assignment_id && (
                              <div className="hidden group-hover:flex items-center gap-0.5 ml-1">
                                {/* Request button - only for green bars */}
                                {(activity.status === 'planned' || activity.status === 'manual') && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      requestAssignment(activity.assignment_id);
                                    }}
                                    className="bg-white text-pink-600 hover:bg-pink-100 rounded px-1 py-0.5 text-[10px] font-bold shadow-sm"
                                    title="Send to FMS"
                                  >
                                    📤
                                  </button>
                                )}
                                {/* Unrequest button - only for magenta bars */}
                                {activity.status === 'requested' && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      unrequestAssignment(activity.assignment_id);
                                    }}
                                    className="bg-white text-green-600 hover:bg-green-100 rounded px-1 py-0.5 text-[10px] font-bold shadow-sm"
                                    title="Change back to recommendation"
                                  >
                                    ↩️
                                  </button>
                                )}
                                {/* Delete button - for all non-blue bars */}
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    deleteAssignment(activity.assignment_id, activity.status);
                                  }}
                                  className="bg-white text-red-600 hover:bg-red-100 rounded px-1 py-0.5 text-[10px] font-bold shadow-sm"
                                  title="Delete"
                                >
                                  ✕
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                  </div>
                </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Vehicle Context Side Panel (Enhanced) */}
      {selectedVin && (
        <div className="fixed right-0 top-0 z-40 h-full">
          <div className="bg-white w-[700px] h-full shadow-2xl overflow-y-auto border-l border-gray-200">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-900">Vehicle Context</h2>
              <button
                onClick={closeSidePanel}
                className="text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6">
              {loadingVehicleContext ? (
                <div className="flex items-center justify-center py-12">
                  <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
              ) : vehicleContext ? (
                <div className="space-y-6">
                  {/* Vehicle Info with Intelligence */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Vehicle Details</h3>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">VIN:</span>
                        <a
                          href={`https://fms.driveshop.com/vehicles/list_activities/${vehicleContext.vehicle_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-mono font-medium text-blue-600 hover:text-blue-800 hover:underline"
                          title="Open in FMS"
                        >
                          {vehicleContext.vin}
                        </a>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Make:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.make}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Model:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.model}</span>
                      </div>
                      {vehicleContext.vehicle_intelligence && (
                        <>
                          {vehicleContext.vehicle_intelligence.year && vehicleContext.vehicle_intelligence.year !== 'N/A' && (
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-gray-600">Year:</span>
                              <span className="text-sm font-medium text-gray-900">{vehicleContext.vehicle_intelligence.year}</span>
                            </div>
                          )}
                          {vehicleContext.vehicle_intelligence.tier && vehicleContext.vehicle_intelligence.tier !== 'N/A' && (
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-gray-600">Tier:</span>
                              <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                                vehicleContext.vehicle_intelligence.tier === 'A' ? 'bg-green-100 text-green-800' :
                                vehicleContext.vehicle_intelligence.tier === 'B' ? 'bg-blue-100 text-blue-800' :
                                vehicleContext.vehicle_intelligence.tier === 'C' ? 'bg-yellow-100 text-yellow-800' :
                                'bg-gray-100 text-gray-800'
                              }`}>
                                {vehicleContext.vehicle_intelligence.tier}
                              </span>
                            </div>
                          )}
                          {vehicleContext.vehicle_intelligence.trim && vehicleContext.vehicle_intelligence.trim !== 'N/A' && (
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-gray-600">Trim:</span>
                              <span className="text-sm font-medium text-gray-900">{vehicleContext.vehicle_intelligence.trim}</span>
                            </div>
                          )}
                        </>
                      )}
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Office:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.office}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Mileage:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.mileage}</span>
                      </div>
                      {vehicleContext.last_known_location && (
                        <div className="border-t pt-2 mt-2">
                          <div className="flex items-start">
                            <svg className="w-4 h-4 text-blue-600 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                            </svg>
                            <div className="flex-1">
                              <p className="text-xs text-gray-500 font-medium">Last Known Location</p>
                              <p className="text-sm text-gray-900 mt-0.5">{vehicleContext.last_known_location}</p>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Build Chain Button */}
                      <div className="border-t pt-3 mt-3">
                        <button
                          onClick={() => {
                            console.log('Build Chain button clicked', vehicleContext);
                            if (onBuildChainForVehicle) {
                              onBuildChainForVehicle({
                                vin: vehicleContext.vin,
                                make: vehicleContext.make,
                                model: vehicleContext.model,
                                year: vehicleContext.vehicle_intelligence?.year || vehicleContext.year,
                                office: vehicleContext.office
                              });
                            } else {
                              console.error('onBuildChainForVehicle callback not provided');
                            }
                          }}
                          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors text-sm"
                        >
                          ⛓️ Build Chain for This Vehicle
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Review History */}
                  <VehicleReviewHistory vin={vehicleContext.vin} office={selectedOffice} />

                  {/* Budget Impact */}
                  {vehicleContext.budget_impact && Object.keys(vehicleContext.budget_impact).length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2 flex items-center justify-between">
                        <span>Budget Impact</span>
                        <span className="text-xs font-normal text-gray-400">{vehicleContext.budget_impact.quarter}</span>
                      </h3>
                      <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                        <div className="grid grid-cols-3 gap-4">
                          <div className="text-center">
                            <p className="text-xs text-gray-500 mb-1">Used</p>
                            <p className="text-lg font-bold text-gray-900">
                              ${(vehicleContext.budget_impact.office_budget_current || 0).toLocaleString()}
                            </p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-gray-500 mb-1">Total Budget</p>
                            <p className="text-lg font-bold text-gray-900">
                              ${(vehicleContext.budget_impact.office_budget_total || 0).toLocaleString()}
                            </p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-gray-500 mb-1">% Used</p>
                            <p className={`text-lg font-bold ${
                              vehicleContext.budget_impact.percent_used >= 75 ? 'text-red-600' :
                              vehicleContext.budget_impact.percent_used >= 40 ? 'text-amber-600' :
                              'text-green-600'
                            }`}>
                              {vehicleContext.budget_impact.percent_used}%
                            </p>
                          </div>
                        </div>
                        <div className="border-t pt-3">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-sm text-gray-600">Cost per Loan:</span>
                            <span className="text-sm font-semibold text-gray-900">
                              ${(vehicleContext.budget_impact.cost_per_loan || 0).toLocaleString()}
                            </span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-sm text-gray-600">Remaining Budget:</span>
                            <span className="text-sm font-semibold text-gray-900">
                              ${(vehicleContext.budget_impact.remaining_budget || 0).toLocaleString()}
                            </span>
                          </div>
                          {vehicleContext.budget_impact.impact_if_loaned > 0 && (
                            <div className="mt-2 pt-2 border-t">
                              <p className="text-xs text-gray-500">
                                Loaning this vehicle will use <span className="font-semibold text-gray-900">{vehicleContext.budget_impact.impact_if_loaned}%</span> of remaining budget
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Publication Performance by Partner */}
                  {vehicleContext.publication_by_partner && Object.keys(vehicleContext.publication_by_partner).length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Publication Performance by Partner</h3>
                      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                        <div className="overflow-x-auto">
                          <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Partner</th>
                                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Total</th>
                                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Published</th>
                                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Rate</th>
                              </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                              {Object.entries(vehicleContext.publication_by_partner)
                                .sort(([,a], [,b]) => b.total - a.total)
                                .slice(0, 10)
                                .map(([partnerName, stats]) => (
                                  <tr key={partnerName} className="hover:bg-gray-50">
                                    <td className="px-4 py-2 text-sm text-gray-900">{partnerName}</td>
                                    <td className="px-4 py-2 text-sm text-center text-gray-700">{stats.total}</td>
                                    <td className="px-4 py-2 text-sm text-center text-blue-600 font-medium">{stats.published}</td>
                                    <td className="px-4 py-2 text-center">
                                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                        stats.rate >= 80 ? 'bg-green-100 text-green-800' :
                                        stats.rate >= 50 ? 'bg-amber-100 text-amber-800' :
                                        'bg-red-100 text-red-800'
                                      }`}>
                                        {stats.rate}%
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Current Activity */}
                  {vehicleContext.current_activity && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Current Activity</h3>
                      <div className="bg-blue-50 border-2 border-blue-400 rounded-lg p-4">
                        <div className="flex items-start">
                          <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                          </svg>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-blue-900">📍 {vehicleContext.current_activity.partner_name}</p>
                            <p className="text-xs text-blue-700 mt-1">
                              {formatActivityDate(vehicleContext.current_activity.start_date)} - {formatActivityDate(vehicleContext.current_activity.end_date)}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Activity Chain Context */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">Activity Chain Context</h3>
                    <div className="space-y-3">
                      {/* Coming Off Of (Previous Activity Expanded) */}
                      <div>
                        <h4 className="text-xs font-medium text-gray-400 uppercase mb-2">Coming Off Of</h4>
                        {vehicleContext.previous_activity_expanded ? (
                          <div className="bg-gradient-to-br from-gray-50 to-gray-100 border-2 border-gray-300 rounded-lg p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex-1">
                                <p className="text-sm font-semibold text-gray-900">
                                  {vehicleContext.previous_activity_expanded.partner_name || 'Unknown Partner'}
                                </p>
                                <p className="text-xs text-gray-600 mt-0.5">
                                  {vehicleContext.previous_activity_expanded.partner_office}
                                </p>
                              </div>
                              {vehicleContext.previous_activity_expanded.gap_days !== undefined && (
                                <div className="ml-3 text-right">
                                  <p className={`text-xs font-semibold ${
                                    vehicleContext.previous_activity_expanded.gap_days > 7 ? 'text-red-600' :
                                    vehicleContext.previous_activity_expanded.gap_days > 3 ? 'text-amber-600' :
                                    'text-green-600'
                                  }`}>
                                    {vehicleContext.previous_activity_expanded.gap_days} days idle
                                  </p>
                                </div>
                              )}
                            </div>
                            <div className="space-y-1">
                              <p className="text-xs text-gray-600">
                                📅 {formatActivityDate(vehicleContext.previous_activity_expanded.start_date)} - {formatActivityDate(vehicleContext.previous_activity_expanded.end_date)}
                              </p>
                              {vehicleContext.previous_activity_expanded.partner_address && (
                                <p className="text-xs text-gray-500">
                                  📍 {vehicleContext.previous_activity_expanded.partner_address}
                                </p>
                              )}
                              {vehicleContext.previous_activity_expanded.published !== undefined && (
                                <p className="text-xs">
                                  {vehicleContext.previous_activity_expanded.published ? (
                                    <span className="text-green-600 font-medium">✓ Published</span>
                                  ) : (
                                    <span className="text-gray-500">Not Published</span>
                                  )}
                                </p>
                              )}
                            </div>
                          </div>
                        ) : (
                          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center border-2 border-dashed border-gray-300">
                            No previous activity
                          </div>
                        )}
                      </div>

                      {/* Going To (Next Activity Expanded) */}
                      <div>
                        <h4 className="text-xs font-medium text-gray-400 uppercase mb-2">Going To</h4>
                        {vehicleContext.next_activity_expanded ? (
                          <div className="bg-gradient-to-br from-blue-50 to-blue-100 border-2 border-blue-400 rounded-lg p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex-1">
                                <p className="text-sm font-semibold text-blue-900">
                                  {vehicleContext.next_activity_expanded.partner_name || 'Unknown Partner'}
                                </p>
                                <p className="text-xs text-blue-700 mt-0.5">
                                  {vehicleContext.next_activity_expanded.partner_office}
                                </p>
                              </div>
                              {vehicleContext.next_activity_expanded.days_until !== undefined && (
                                <div className="ml-3 text-right">
                                  <p className="text-xs font-semibold text-blue-700">
                                    in {vehicleContext.next_activity_expanded.days_until} days
                                  </p>
                                </div>
                              )}
                            </div>
                            <div className="space-y-1">
                              <p className="text-xs text-blue-700">
                                📅 {formatActivityDate(vehicleContext.next_activity_expanded.start_date)} - {formatActivityDate(vehicleContext.next_activity_expanded.end_date || 'TBD')}
                              </p>
                              {vehicleContext.next_activity_expanded.partner_address && (
                                <p className="text-xs text-blue-600">
                                  📍 {vehicleContext.next_activity_expanded.partner_address}
                                </p>
                              )}
                            </div>
                          </div>
                        ) : (
                          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center border-2 border-dashed border-gray-300">
                            No upcoming activity
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Activity Timeline */}
                  {vehicleContext.timeline && vehicleContext.timeline.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Activity Timeline</h3>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="space-y-2">
                          {vehicleContext.timeline.map((activity, idx) => {
                            // Determine if this activity is past, current, or future
                            const now = new Date();
                            const startDate = new Date(activity.start_date);
                            const endDate = activity.end_date ? new Date(activity.end_date) : null;

                            const isPast = endDate && endDate < now;
                            const isCurrent = startDate <= now && (!endDate || endDate >= now);

                            return (
                              <div key={idx} className={`flex items-center text-sm ${isCurrent ? 'font-medium text-blue-900' : 'text-gray-700'}`}>
                                <div className={`w-2 h-2 rounded-full mr-2 flex-shrink-0 ${
                                  isPast ? 'bg-gray-400' :
                                  isCurrent ? 'bg-blue-500' :
                                  'bg-blue-400'
                                }`}></div>
                                <div className="flex-1 min-w-0">
                                  <p className="truncate text-xs">{activity.partner_name || 'Unknown Partner'}</p>
                                  <p className="text-xs text-gray-500">
                                    {formatActivityDate(activity.start_date)} - {formatActivityDate(activity.end_date)}
                                  </p>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Next Best Chains */}
                  {vehicleContext.current_activity && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
                        ⛓️ Next Best Chains
                        <span className="text-xs font-normal text-gray-400">(within 50 mi)</span>
                      </h3>
                      {loadingChains ? (
                        <div className="flex items-center justify-center py-8">
                          <svg className="animate-spin h-6 w-6 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                        </div>
                      ) : chainingOpportunities?.success && chainingOpportunities.nearby_partners?.length > 0 ? (
                        <div className="bg-gradient-to-br from-yellow-50 to-amber-50 border border-yellow-200 rounded-lg p-4">
                          <div className="mb-3">
                            <p className="text-xs text-gray-600 mb-1">
                              Currently with: <span className="font-medium text-gray-900">{chainingOpportunities.current_partner.name}</span>
                            </p>
                            <p className="text-xs text-gray-500">
                              Nearby partners approved for <span className="font-medium">{chainingOpportunities.vehicle_make}</span>:
                            </p>
                          </div>
                          <div className="space-y-2">
                            {chainingOpportunities.nearby_partners.map((partner, idx) => (
                              <div key={idx} className="bg-white rounded-lg p-3 shadow-sm border border-yellow-200 hover:border-yellow-400 transition-colors">
                                <div className="flex items-start justify-between">
                                  <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-gray-900 truncate">{partner.name}</p>
                                    <p className="text-xs text-gray-500 mt-0.5">{partner.region || 'N/A'}</p>
                                    {partner.address && (
                                      <p className="text-xs text-gray-400 mt-1 truncate">{partner.address}</p>
                                    )}
                                  </div>
                                  <div className="ml-3 flex-shrink-0 text-right">
                                    <p className="text-sm font-semibold text-yellow-700">{partner.distance_miles} mi</p>
                                    <p className="text-xs text-gray-500">away</p>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                          <div className="mt-3 pt-3 border-t border-yellow-200">
                            <p className="text-xs text-gray-500 italic">
                              💡 Tip: Chain this vehicle to a nearby partner to reduce deadhead miles
                            </p>
                          </div>
                        </div>
                      ) : chainingOpportunities?.success && chainingOpportunities.nearby_partners?.length === 0 ? (
                        <div className="bg-gray-50 rounded-lg p-4 text-center">
                          <p className="text-sm text-gray-500">No nearby partners within 50 miles</p>
                          <p className="text-xs text-gray-400 mt-1">approved for {chainingOpportunities.vehicle_make}</p>
                        </div>
                      ) : !chainingOpportunities?.success && chainingOpportunities?.message ? (
                        <div className="bg-gray-50 rounded-lg p-4 text-center">
                          <p className="text-sm text-gray-500">{chainingOpportunities.message}</p>
                        </div>
                      ) : (
                        <div className="bg-gray-50 rounded-lg p-4 text-center">
                          <p className="text-sm text-gray-500">Chaining opportunities unavailable</p>
                          <p className="text-xs text-gray-400 mt-1">Vehicle must have active loan to calculate chains</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <p>Unable to load vehicle context</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Media Partner Context Side Panel */}
      {selectedPartnerId && (
        <div className="fixed right-0 top-0 z-40 h-full">
          <div className="bg-white w-[700px] h-full shadow-2xl overflow-y-auto border-l border-gray-200">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-900">Media Partner Context</h2>
              <button
                onClick={closeSidePanel}
                className="text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6">
              {loadingPartnerContext ? (
                <div className="flex items-center justify-center py-12">
                  <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
              ) : partnerContext ? (
                <div className="space-y-6">
                  {/* Media Partner Info */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Media Partner Details</h3>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Name:</span>
                        <span className="text-sm font-medium text-gray-900">{partnerContext.partner_name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Media ID:</span>
                        <span className="text-sm font-mono font-medium text-gray-900">{partnerContext.person_id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Office:</span>
                        <span className="text-sm font-medium text-gray-900">{partnerContext.office}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Region:</span>
                        <span className="text-sm font-medium text-gray-900">{partnerContext.region}</span>
                      </div>
                      {partnerContext.distance_info && partnerContext.distance_info.success && (
                        <div className="flex justify-between items-center border-t pt-2 mt-2">
                          <span className="text-sm text-gray-600">Distance:</span>
                          <div className="flex items-center gap-2">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              partnerContext.distance_info.location_type === 'local'
                                ? 'bg-green-100 text-green-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}>
                              {partnerContext.distance_info.location_type === 'local' ? '🏠 Local' : '✈️ Remote'}
                            </span>
                            <span className="text-sm font-medium text-gray-900">
                              {partnerContext.distance_info.distance_miles} mi
                            </span>
                          </div>
                        </div>
                      )}
                      {partnerContext.partner_address && partnerContext.partner_address !== 'N/A' && (
                        <div className="border-t pt-2 mt-2">
                          <div className="flex items-start">
                            <svg className="w-4 h-4 text-blue-600 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                            </svg>
                            <div className="flex-1">
                              <p className="text-xs text-gray-500 font-medium">Address</p>
                              <p className="text-sm text-gray-900 mt-0.5">{partnerContext.partner_address}</p>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Build Chain Button */}
                      <div className="border-t pt-3 mt-3">
                        <button
                          onClick={() => {
                            console.log('Build Chain button clicked for partner', partnerContext);
                            if (onBuildChainForPartner) {
                              onBuildChainForPartner({
                                person_id: partnerContext.person_id,
                                name: partnerContext.partner_name,
                                office: partnerContext.office
                              });
                            } else {
                              console.error('onBuildChainForPartner callback not provided');
                            }
                          }}
                          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors text-sm"
                        >
                          ⛓️ Build Chain for This Partner
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Approved Makes & Budget Status - New Table Design */}
                  {partnerContext.approved_makes && partnerContext.approved_makes.length > 0 && (
                    <div>
                      <div className="flex items-center justify-between mb-3 border-l-4 border-indigo-500 pl-3">
                        <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wide">
                          Approved Makes & Budget Status
                        </h3>
                        <span className="text-xs text-gray-500">Current Quarter: {partnerContext.current_quarter || 'Q4 2025'}</span>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Make</th>
                              <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Tier</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Office Budget ({partnerContext.current_quarter || 'Q4'})</th>
                              <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">%</th>
                              <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Cost/Loan</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Partner Usage</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-gray-200">
                            {[...partnerContext.approved_makes].sort((a, b) => a.make.localeCompare(b.make)).map((item, idx) => {
                              const makeUpper = item.make.toUpperCase();
                              const budget = partnerContext.budget_status?.[makeUpper];
                              const percentUsed = budget?.percent_used || null;
                              const loanCount = item.loan_count || 0;
                              const totalCost = item.total_spend || (loanCount * (item.media_cost || 400));
                              
                              // Color code budget percentage
                              let percentColor = 'text-gray-500';
                              if (percentUsed !== null) {
                                if (percentUsed < 40) percentColor = 'text-green-600 font-semibold';
                                else if (percentUsed < 75) percentColor = 'text-amber-600 font-semibold';
                                else percentColor = 'text-red-600 font-semibold';
                              }
                              
                              return (
                                <tr key={item.make} className={`${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'} hover:bg-blue-50 transition-colors`}>
                                  <td className="px-4 py-2 text-sm text-gray-900">{item.make}</td>
                                  <td className="px-4 py-2 text-center">
                                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${getTierBadgeColor(item.rank)}`}>
                                      {item.rank}
                                    </span>
                                  </td>
                                  <td className="px-4 py-2 text-sm">
                                    {budget ? (
                                      <span>
                                        <span className="text-green-400 font-medium">${budget.current.toLocaleString()}</span>
                                        <span className="text-gray-600"> / </span>
                                        <span className="text-green-700 font-semibold">${budget.budget.toLocaleString()}</span>
                                      </span>
                                    ) : (
                                      <span className="text-gray-500">-</span>
                                    )}
                                  </td>
                                  <td className={`px-4 py-2 text-sm text-center ${percentColor}`}>
                                    {percentUsed !== null ? `${Math.round(percentUsed)}%` : '-'}
                                  </td>
                                  <td className="px-4 py-2 text-sm text-center text-gray-600">
                                    ${Math.round(item.media_cost || 400).toLocaleString()}
                                  </td>
                                  <td className="px-4 py-2 text-sm text-gray-600">
                                    {loanCount} loan{loanCount !== 1 ? 's' : ''} • ${Math.round(totalCost).toLocaleString()}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Publication Performance - New 3-Column Design */}
                  {partnerContext.stats && (
                    <div>
                      <div className="border-l-4 border-purple-500 pl-3 mb-3">
                        <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wide">Publication Performance</h3>
                      </div>
                      <div className="grid grid-cols-3 gap-4 bg-gray-50 rounded-lg p-4 mb-4">
                        <div className="text-center">
                          <div className="text-sm text-gray-600 mb-1">Total Loans</div>
                          <div className="text-2xl font-semibold text-gray-900">
                            {partnerContext.stats.total_loans || 0}
                          </div>
                        </div>
                        <div className="text-center border-l border-r border-gray-200">
                          <div className="text-sm text-gray-600 mb-1">Published</div>
                          <div className="text-2xl font-semibold text-blue-600">
                            {Math.round((partnerContext.stats.total_loans || 0) * (partnerContext.stats.publication_rate || 0))}
                          </div>
                        </div>
                        <div className="text-center">
                          <div className="text-sm text-gray-600 mb-1">Publication Rate</div>
                          <div className={`text-2xl font-semibold ${
                            (partnerContext.stats.publication_rate || 0) >= 0.75 ? 'text-green-600' :
                            (partnerContext.stats.publication_rate || 0) >= 0.50 ? 'text-amber-600' :
                            'text-red-600'
                          }`}>
                            {((partnerContext.stats.publication_rate || 0) * 100).toFixed(0)}%
                          </div>
                        </div>
                      </div>
                      
                      {/* Per-make breakdown */}
                      {partnerContext.publication_by_make && Object.keys(partnerContext.publication_by_make).length > 0 && (
                        <div className="bg-white rounded-lg border border-gray-200 p-3">
                          <p className="text-xs text-gray-500 font-medium mb-2">By Make (24-month):</p>
                          <div className="space-y-1.5">
                            {Object.entries(partnerContext.publication_by_make)
                              .sort(([, a], [, b]) => (b.rate || 0) - (a.rate || 0))
                              .map(([make, data]) => (
                                <div key={make} className="flex justify-between items-center text-xs bg-gray-50 rounded px-3 py-2">
                                  <span className="font-medium text-gray-700">{make}</span>
                                  <div className="flex items-center gap-2">
                                    {data.has_data && data.rate !== null ? (
                                      <>
                                        <span className={`font-bold ${
                                          data.rate >= 0.7 ? 'text-green-600' :
                                          data.rate >= 0.5 ? 'text-amber-600' :
                                          'text-red-600'
                                        }`}>
                                          {Math.round(data.rate * 100)}%
                                        </span>
                                        <span className="text-gray-400">
                                          ({data.published}/{data.total})
                                        </span>
                                      </>
                                    ) : (
                                      <span className="text-gray-400 italic">No data</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Partner Review History */}
                  <PartnerReviewHistory personId={partnerContext.person_id} office={selectedOffice} />

                  {/* Current Loans - Compact Design */}
                  <div>
                    <div className="border-l-4 border-blue-500 pl-3 mb-3">
                      <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wide">
                        Current Loan{partnerContext.current_loans?.length > 1 ? 's' : ''} 
                        {partnerContext.current_loans?.length > 0 && (
                          <span className="ml-2 text-xs font-normal text-gray-400">({partnerContext.current_loans.length})</span>
                        )}
                      </h3>
                    </div>
                    {partnerContext.current_loans && partnerContext.current_loans.length > 0 ? (
                      <div className="bg-blue-50 border-l-4 border-blue-500 rounded-lg p-4 space-y-2">
                        {partnerContext.current_loans.map((loan, idx) => (
                          <div key={idx} className="text-sm">
                            <div className="font-medium text-gray-900">
                              🚗 {loan.make} {loan.model}
                            </div>
                            <div className="text-xs text-gray-600 mt-1">
                              {formatActivityDate(loan.start_date)} - {formatActivityDate(loan.end_date)} • VIN: <a href="#" className="text-blue-600 hover:text-blue-800 font-mono">{loan.vin ? loan.vin.slice(-8) : 'N/A'}</a>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-6 text-gray-400 bg-gray-50 rounded-lg border border-gray-200">
                        <p className="text-sm">No active loans</p>
                      </div>
                    )}
                  </div>

                  {/* Recommended Loans - Table Format */}
                  <div>
                    <div className="border-l-4 border-green-500 pl-3 mb-3">
                      <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wide">
                        Recommended Loan{partnerContext.recommended_loans?.length > 1 ? 's' : ''} 
                        {partnerContext.recommended_loans?.length > 0 && (
                          <span className="ml-2 text-xs font-normal text-gray-400">({partnerContext.recommended_loans.length})</span>
                        )}
                      </h3>
                    </div>
                    {partnerContext.recommended_loans && partnerContext.recommended_loans.length > 0 ? (
                      <div className="bg-green-50 rounded-lg border-l-4 border-green-500 overflow-hidden">
                        <table className="min-w-full divide-y divide-green-200">
                          <tbody className="divide-y divide-green-200">
                            {partnerContext.recommended_loans.map((loan, idx) => {
                              // Generate a dummy score based on status
                              const score = loan.status === 'manual' ? 85 : 82
                              const scoreColor = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-amber-600' : 'text-gray-600'
                              
                              return (
                                <tr key={idx} className="hover:bg-green-100 transition-colors">
                                  <td className="px-4 py-2 text-sm font-medium text-gray-900">
                                    {loan.make} {loan.model}
                                  </td>
                                  <td className="px-4 py-2 text-xs text-gray-600">
                                    {formatActivityDate(loan.start_date)} - {formatActivityDate(loan.end_date)}
                                  </td>
                                  <td className="px-4 py-2 text-xs text-right">
                                    VIN: <a href="#" className="text-blue-600 hover:text-blue-800 font-mono">{loan.vin ? loan.vin.slice(-8) : 'N/A'}</a>
                                    <span className={`ml-2 font-semibold ${scoreColor}`}>Score: {score}</span>
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-center py-6 text-gray-400 bg-gray-50 rounded-lg border border-gray-200">
                        <p className="text-sm">No planned loans yet</p>
                        <p className="text-xs mt-1">Run the optimizer to get recommendations</p>
                      </div>
                    )}
                  </div>

                  {/* Requested Loans - Table Format (Magenta/Pink) */}
                  {partnerContext.requested_loans && partnerContext.requested_loans.length > 0 && (
                    <div>
                      <div className="border-l-4 border-pink-500 pl-3 mb-3">
                        <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wide">
                          Requested Loan{partnerContext.requested_loans.length > 1 ? 's' : ''} 
                          <span className="ml-2 text-xs font-normal text-gray-400">({partnerContext.requested_loans.length})</span>
                        </h3>
                      </div>
                      <div className="bg-pink-50 rounded-lg border-l-4 border-pink-500 overflow-hidden">
                        <table className="min-w-full divide-y divide-pink-200">
                          <tbody className="divide-y divide-pink-200">
                            {partnerContext.requested_loans.map((loan, idx) => (
                              <tr key={idx} className="hover:bg-pink-100 transition-colors">
                                <td className="px-4 py-2 text-sm font-medium text-gray-900">
                                  {loan.make} {loan.model}
                                </td>
                                <td className="px-4 py-2 text-xs text-gray-600">
                                  {formatActivityDate(loan.start_date)} - {formatActivityDate(loan.end_date)}
                                </td>
                                <td className="px-4 py-2 text-xs text-right">
                                  VIN: <a href="#" className="text-blue-600 hover:text-blue-800 font-mono">{loan.vin ? loan.vin.slice(-8) : 'N/A'}</a>
                                  <span className="ml-2 text-xs font-semibold text-pink-600">⏳ Pending Approval</span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Activity Timeline - Collapsible */}
                  <div>
                    <div
                      className="flex items-center justify-between cursor-pointer hover:bg-gray-50 rounded-lg p-2 -mx-2 transition-colors"
                      onClick={() => setShowPartnerTimeline(!showPartnerTimeline)}
                    >
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
                        Activity Timeline
                      </h3>
                      <svg
                        className={`w-4 h-4 text-gray-500 transition-transform ${showPartnerTimeline ? 'rotate-90' : ''}`}
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>

                    {showPartnerTimeline && (
                      <div className="space-y-2 mt-2">
                        {partnerContext.timeline.map((act, idx) => (
                          <div key={idx} className="flex items-center text-xs bg-gray-50 rounded p-2">
                            <span className={`inline-block w-2 h-2 rounded-full mr-2 ${
                              act.status === 'active' ? 'bg-blue-500' :
                              act.status === 'planned' ? 'bg-green-500' :
                              'bg-gray-400'
                            }`}></span>
                            <span className="flex-1 font-medium text-gray-900">{act.make} {act.model}</span>
                            <span className="text-gray-500">{formatActivityDate(act.start_date)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <p>Unable to load media partner context</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Calendar;
