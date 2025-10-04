import React, { useState, useEffect } from 'react';

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

function Calendar({ sharedOffice }) {
  // Use shared office from parent, default to 'Los Angeles' if not provided
  const [selectedOffice, setSelectedOffice] = useState(sharedOffice || 'Los Angeles');

  // Update selectedOffice when sharedOffice prop changes
  useEffect(() => {
    if (sharedOffice) {
      setSelectedOffice(sharedOffice);
    }
  }, [sharedOffice]);
  const [selectedMonth, setSelectedMonth] = useState('');
  const [activities, setActivities] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // View mode toggle
  const [viewMode, setViewMode] = useState('vehicle'); // 'vehicle' or 'partner'

  // Filters
  const [vinFilter, setVinFilter] = useState('');
  const [makeFilter, setMakeFilter] = useState('');
  const [partnerFilter, setPartnerFilter] = useState('');

  // Vehicle context (reuse existing side panel)
  const [selectedVin, setSelectedVin] = useState(null);
  const [vehicleContext, setVehicleContext] = useState(null);
  const [loadingVehicleContext, setLoadingVehicleContext] = useState(false);

  // Load offices
  const [offices, setOffices] = useState([]);

  useEffect(() => {
    const loadOffices = async () => {
      try {
        const response = await fetch('http://localhost:8081/api/offices');
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

  // Set current month as default
  useEffect(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    setSelectedMonth(`${year}-${month}`);
  }, []);

  // Load activities when office/month changes
  useEffect(() => {
    if (selectedOffice && selectedMonth) {
      loadActivities();
    }
  }, [selectedOffice, selectedMonth]);

  const loadActivities = async () => {
    if (!selectedOffice || !selectedMonth) return;

    setIsLoading(true);
    setError('');

    try {
      const [year, month] = selectedMonth.split('-');
      const startDate = `${year}-${month}-01`;
      const lastDay = new Date(year, month, 0).getDate();
      const endDate = `${year}-${month}-${lastDay}`;

      const params = new URLSearchParams({
        office: selectedOffice,
        start_date: startDate,
        end_date: endDate
      });

      const response = await fetch(`http://localhost:8081/api/calendar/activity?${params}`);
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

  // Group activities by VIN
  const groupedByVin = activities.reduce((acc, activity) => {
    const vin = activity.vin;
    if (!acc[vin]) {
      acc[vin] = {
        vin: vin,
        make: activity.make,
        model: activity.model,
        office: activity.office,
        activities: []
      };
    }
    acc[vin].activities.push(activity);
    return acc;
  }, {});

  // Group activities by Partner
  const groupedByPartner = activities.reduce((acc, activity) => {
    const partnerId = activity.person_id;
    const partnerName = activity.partner_name || `Partner ${partnerId}`;
    if (!acc[partnerId]) {
      acc[partnerId] = {
        person_id: partnerId,
        partner_name: partnerName,
        office: activity.office,
        activities: []
      };
    }
    acc[partnerId].activities.push(activity);
    return acc;
  }, {});

  // Apply filters based on view mode
  const filteredVins = Object.values(groupedByVin).filter(vehicle => {
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
    if (partnerFilter && !partner.partner_name.toLowerCase().includes(partnerFilter.toLowerCase())) return false;
    if (makeFilter) {
      const hasMake = partner.activities.some(a => a.make === makeFilter);
      if (!hasMake) return false;
    }
    if (vinFilter) {
      const hasVin = partner.activities.some(a =>
        a.vin?.toLowerCase().includes(vinFilter.toLowerCase())
      );
      if (!hasVin) return false;
    }
    return true;
  });

  // Choose which data to display based on view mode
  const displayData = viewMode === 'vehicle' ? filteredVins : filteredPartners;

  // Get unique makes for filter
  const uniqueMakes = [...new Set(activities.map(a => a.make).filter(Boolean))].sort();

  // Fetch vehicle context
  const fetchVehicleContext = async (vin) => {
    if (vehicleContext && vehicleContext.vin === vin) return;

    setLoadingVehicleContext(true);
    try {
      const response = await fetch(`http://localhost:8081/api/ui/phase7/vehicle-context/${vin}`);
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
      // Build context from calendar activities data
      const vehicleActivities = activities.filter(a => a.vin === vin);

      if (vehicleActivities.length > 0) {
        const firstActivity = vehicleActivities[0];
        const sortedActivities = [...vehicleActivities].sort((a, b) =>
          new Date(a.start_date) - new Date(b.start_date)
        );

        const now = new Date();
        const previous = sortedActivities.filter(a => new Date(a.end_date) < now).pop();
        const next = sortedActivities.find(a => new Date(a.start_date) > now);
        const current = sortedActivities.find(a => {
          const start = new Date(a.start_date);
          const end = new Date(a.end_date);
          return now >= start && now <= end;
        });

        // Try to get mileage from vehicles table
        let mileage = 'N/A';
        try {
          const vehicleResponse = await fetch(`http://localhost:8081/api/ui/phase7/vehicle-context/${vin}`);
          if (vehicleResponse.ok) {
            const vehicleData = await vehicleResponse.json();
            mileage = vehicleData.mileage || 'N/A';
          }
        } catch (err) {
          console.error('Could not fetch mileage:', err);
        }

        // Build context object with timeline
        const context = {
          vin: vin,
          make: firstActivity.make,
          model: firstActivity.model,
          office: firstActivity.office,
          mileage: mileage,
          last_known_location: current
            ? `With ${current.partner_name}`
            : previous
              ? `Last with ${previous.partner_name}`
              : 'Home Office',
          current_activity: current ? {
            activity_type: current.activity_type || 'Media Loan',
            start_date: current.start_date,
            end_date: current.end_date,
            partner_name: current.partner_name,
            status: current.status
          } : null,
          previous_activity: previous ? {
            activity_type: previous.activity_type || 'Media Loan',
            start_date: previous.start_date,
            end_date: previous.end_date,
            partner_name: previous.partner_name,
            status: previous.status
          } : null,
          next_activity: next ? {
            activity_type: next.activity_type || 'Planned Loan',
            start_date: next.start_date,
            end_date: next.end_date,
            partner_name: next.partner_name,
            status: next.status
          } : null,
          timeline: sortedActivities
        };

        setVehicleContext(context);
      } else {
        await fetchVehicleContext(vin);
      }
    } finally {
      setLoadingVehicleContext(false);
    }
  };

  const closeSidePanel = () => {
    setSelectedVin(null);
    setVehicleContext(null);
  };

  // Parse date string as local date (YYYY-MM-DD)
  const parseLocalDate = (dateStr) => {
    if (!dateStr || typeof dateStr !== 'string') return null;
    try {
      const parts = dateStr.split('-');
      if (parts.length !== 3) return null;
      const [year, month, day] = parts.map(Number);
      if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
      return new Date(year, month - 1, day);
    } catch (e) {
      return null;
    }
  };

  const formatActivityDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = parseLocalDate(dateStr);
    if (!date || isNaN(date.getTime())) return 'Invalid Date';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getActivityColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-gray-400';
      case 'active': return 'bg-blue-500';
      case 'planned': return 'bg-green-400';
      default: return 'bg-gray-300';
    }
  };

  const getActivityLabel = (status) => {
    switch (status) {
      case 'completed': return 'Past';
      case 'active': return 'Active';
      case 'planned': return 'Planned';
      default: return status;
    }
  };

  // Determine vehicle location based on activity
  const getVehicleLocation = (activity) => {
    // If active, vehicle is with the partner
    if (activity.status === 'active') {
      return { type: 'partner', label: `📍 With ${activity.partner_name}` };
    }
    // If planned, vehicle will be picked up
    if (activity.status === 'planned') {
      return { type: 'planned', label: '📅 Scheduled' };
    }
    // If completed, check if it's local (same office) or remote
    if (activity.status === 'completed') {
      return { type: 'office', label: '🏢 At Office' };
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

  // Generate days in the selected month
  const getDaysInMonth = () => {
    if (!selectedMonth) return [];
    const [year, month] = selectedMonth.split('-');
    const numDays = new Date(year, month, 0).getDate();
    const days = [];
    for (let day = 1; day <= numDays; day++) {
      days.push(day);
    }
    return days;
  };

  const daysInMonth = getDaysInMonth();

  // Check if activity overlaps with the selected month
  const activityOverlapsMonth = (activity) => {
    if (!selectedMonth) return false;

    const [year, month] = selectedMonth.split('-');
    const monthStart = new Date(year, month - 1, 1);
    const monthEnd = new Date(year, month, 0, 23, 59, 59); // End of last day of month

    const activityStart = parseLocalDate(activity.start_date);
    const activityEnd = parseLocalDate(activity.end_date);

    // Activity must end after month starts AND start before month ends
    return activityEnd >= monthStart && activityStart <= monthEnd;
  };

  // Calculate bar position and width for Gantt chart
  const getBarStyle = (activity) => {
    if (!selectedMonth) return { left: 0, width: 0 };

    const [year, month] = selectedMonth.split('-');
    const monthStart = new Date(year, month - 1, 1);
    const monthEnd = new Date(year, month, 0, 23, 59, 59); // End of last day of month

    const activityStart = parseLocalDate(activity.start_date);
    const activityEnd = parseLocalDate(activity.end_date);

    // Clamp to month boundaries
    const startDate = activityStart < monthStart ? monthStart : activityStart;
    const endDate = activityEnd > monthEnd ? monthEnd : activityEnd;

    // Calculate position as percentage
    const totalDays = daysInMonth.length;
    const startDay = startDate.getDate();
    const endDay = endDate.getDate();

    const left = ((startDay - 1) / totalDays) * 100;
    const width = ((endDay - startDay + 1) / totalDays) * 100;

    return { left: `${left}%`, width: `${width}%` };
  };

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">📅 Calendar View</h1>
            <p className="text-sm text-gray-600 mt-1">Vehicle activity timeline - past, current, and planned</p>
          </div>

          {/* View Mode Toggle */}
          <div className="flex bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setViewMode('vehicle')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'vehicle'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              🚗 By Vehicle
            </button>
            <button
              onClick={() => setViewMode('partner')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'partner'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              👤 By Partner
            </button>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Office</label>
            <select
              value={selectedOffice}
              onChange={(e) => setSelectedOffice(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-500"
            >
              {offices.map(office => (
                <option key={office} value={office}>{office}</option>
              ))}
            </select>
          </div>

          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Month</label>
            <input
              type="month"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Filter by VIN</label>
            <input
              type="text"
              value={vinFilter}
              onChange={(e) => setVinFilter(e.target.value)}
              placeholder="Search VIN..."
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Make</label>
            <select
              value={makeFilter}
              onChange={(e) => setMakeFilter(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Makes</option>
              {uniqueMakes.map(make => (
                <option key={make} value={make}>{make}</option>
              ))}
            </select>
          </div>

          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Partner</label>
            <input
              type="text"
              value={partnerFilter}
              onChange={(e) => setPartnerFilter(e.target.value)}
              placeholder="Search partner..."
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-500"
            />
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
            <div className="w-4 h-4 bg-green-400 rounded"></div>
            <span className="text-gray-600">Planned</span>
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

      {/* Gantt Chart Content */}
      <div className="p-6">
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
          <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
            {/* Gantt Chart Header */}
            <div className="flex border-b bg-gray-50 sticky top-0 z-10">
              {/* Row label column */}
              <div className="w-64 flex-shrink-0 px-4 py-3 border-r font-medium text-sm text-gray-700">
                {viewMode === 'vehicle' ? 'Vehicle' : 'Partner'}
              </div>
              {/* Days column */}
              <div className="flex-1 flex">
                {daysInMonth.map(day => (
                  <div key={day} className="flex-1 text-center text-xs text-gray-600 py-3 border-r">
                    {day}
                  </div>
                ))}
              </div>
            </div>

            {/* Gantt Chart Rows */}
            <div className="divide-y divide-gray-200">
              {displayData.map((item) => (
                <div key={viewMode === 'vehicle' ? item.vin : item.person_id} className="flex hover:bg-gray-50">
                  {/* Row info */}
                  <div className="w-64 flex-shrink-0 px-4 py-3 border-r">
                    <button
                      onClick={() => viewMode === 'vehicle' && handleActivityClick(item.vin)}
                      className="text-left w-full group"
                    >
                      {viewMode === 'vehicle' ? (
                        <>
                          <h3 className="font-semibold text-sm text-gray-900 group-hover:text-blue-600">
                            {item.make} {item.model}
                          </h3>
                          <p className="text-xs text-gray-500 font-mono">{item.vin}</p>
                        </>
                      ) : (
                        <>
                          <h3 className="font-semibold text-sm text-gray-900 group-hover:text-blue-600">
                            {item.partner_name}
                          </h3>
                          <p className="text-xs text-gray-500">ID: {item.person_id}</p>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Timeline bars */}
                  <div className="flex-1 relative h-16">
                    {/* Day grid */}
                    <div className="absolute inset-0 flex">
                      {daysInMonth.map(day => (
                        <div key={day} className="flex-1 border-r border-gray-100"></div>
                      ))}
                    </div>

                    {/* Activity bars */}
                    {item.activities
                      .filter(activity => activityOverlapsMonth(activity))
                      .map((activity, idx, filteredActivities) => {
                        const barStyle = getBarStyle(activity);
                        const label = viewMode === 'vehicle' ? activity.partner_name : `${activity.make} ${activity.model}`;
                        const location = getVehicleLocation(activity);
                        const hasChaining = viewMode === 'vehicle' && detectChainingOpportunity(item.activities, item.activities.indexOf(activity));
                        return (
                          <button
                            key={idx}
                            onClick={() => viewMode === 'vehicle' && handleActivityClick(item.vin)}
                            className={`absolute top-1/2 -translate-y-1/2 h-8 ${getActivityColor(activity.status)} ${hasChaining ? 'ring-2 ring-yellow-400 ring-offset-1' : ''} rounded shadow-sm hover:shadow-md transition-shadow cursor-pointer flex items-center gap-1 text-white text-xs font-medium px-2 overflow-hidden`}
                            style={{ left: barStyle.left, width: barStyle.width, minWidth: '20px' }}
                            title={`${label}\n${formatActivityDate(activity.start_date)} - ${formatActivityDate(activity.end_date)}\n${location ? location.label : ''}${hasChaining ? '\n⛓️ Chaining opportunity!' : ''}`}
                          >
                            {location && activity.status === 'active' && <span>📍</span>}
                            {hasChaining && <span>⛓️</span>}
                            <span className="truncate">{label}</span>
                          </button>
                        );
                      })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Vehicle Context Side Panel (reuse from Optimizer) */}
      {selectedVin && (
        <div className="fixed right-0 top-0 z-40 h-full">
          <div className="bg-white w-96 h-full shadow-2xl overflow-y-auto border-l border-gray-200">
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
                  {/* Vehicle Info */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Vehicle Details</h3>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">VIN:</span>
                        <span className="text-sm font-mono font-medium text-gray-900">{vehicleContext.vin}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Make:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.make}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Model:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.model}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Office:</span>
                        <span className="text-sm font-medium text-gray-900">{vehicleContext.office}</span>
                      </div>
                      <div className="flex justify-between">
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
                    </div>
                  </div>

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

                  {/* Previous Activity */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Previous Activity</h3>
                    {vehicleContext.previous_activity ? (
                      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <div className="flex items-start">
                          <svg className="w-5 h-5 text-gray-600 mt-0.5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                          </svg>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-gray-900">{vehicleContext.previous_activity.partner_name}</p>
                            <p className="text-xs text-gray-600 mt-1">
                              {formatActivityDate(vehicleContext.previous_activity.start_date)} - {formatActivityDate(vehicleContext.previous_activity.end_date)}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center">
                        No previous activity
                      </div>
                    )}
                  </div>

                  {/* Next Activity */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Next Activity</h3>
                    {vehicleContext.next_activity ? (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                        <div className="flex items-start">
                          <svg className="w-5 h-5 text-green-600 mt-0.5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                          </svg>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-green-900">{vehicleContext.next_activity.partner_name}</p>
                            <p className="text-xs text-green-700 mt-1">
                              {formatActivityDate(vehicleContext.next_activity.start_date)} - {formatActivityDate(vehicleContext.next_activity.end_date)}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-500 text-center">
                        No upcoming activity
                      </div>
                    )}
                  </div>

                  {/* Activity Timeline */}
                  {vehicleContext.timeline && vehicleContext.timeline.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Activity Timeline</h3>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="space-y-2">
                          {vehicleContext.timeline.map((activity, idx) => {
                            const isCurrent = vehicleContext.current_activity && activity.start_date === vehicleContext.current_activity.start_date;
                            return (
                              <div key={idx} className={`flex items-center text-sm ${isCurrent ? 'font-medium text-blue-900' : 'text-gray-700'}`}>
                                <div className={`w-2 h-2 rounded-full mr-2 flex-shrink-0 ${
                                  activity.status === 'completed' ? 'bg-gray-400' :
                                  activity.status === 'active' ? 'bg-blue-500' :
                                  'bg-green-400'
                                }`}></div>
                                <div className="flex-1 min-w-0">
                                  <p className="truncate">{activity.partner_name}</p>
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
    </div>
  );
}

export default Calendar;
