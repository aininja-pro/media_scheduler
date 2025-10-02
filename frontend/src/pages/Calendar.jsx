import React, { useState, useEffect } from 'react';

function Calendar() {
  const [selectedOffice, setSelectedOffice] = useState('Los Angeles');
  const [selectedMonth, setSelectedMonth] = useState('');
  const [activities, setActivities] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

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

  // Apply filters
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

  const handleActivityClick = (vin) => {
    setSelectedVin(vin);
    fetchVehicleContext(vin);
  };

  const closeSidePanel = () => {
    setSelectedVin(null);
    setVehicleContext(null);
  };

  const formatActivityDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
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

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">📅 Calendar View</h1>
        <p className="text-sm text-gray-600 mt-1">Vehicle activity timeline - past, current, and planned</p>
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
        <div className="flex gap-6 mt-4 text-sm">
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
        </div>
      </div>

      {/* Timeline Content */}
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
        ) : filteredVins.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border p-12 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p className="mt-2 text-sm text-gray-500">No activity found</p>
            <p className="text-xs text-gray-400 mt-1">Try adjusting your filters or select a different month</p>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
            <div className="divide-y divide-gray-200">
              {filteredVins.map((vehicle) => (
                <div key={vehicle.vin} className="p-4 hover:bg-gray-50">
                  {/* Vehicle Header */}
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {vehicle.make} {vehicle.model}
                      </h3>
                      <p className="text-xs text-gray-500 font-mono">{vehicle.vin}</p>
                    </div>
                    <button
                      onClick={() => handleActivityClick(vehicle.vin)}
                      className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      View Details →
                    </button>
                  </div>

                  {/* Timeline */}
                  <div className="space-y-2">
                    {vehicle.activities
                      .sort((a, b) => new Date(a.start_date) - new Date(b.start_date))
                      .map((activity, idx) => (
                        <div key={idx} className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${getActivityColor(activity.status)}`}></div>
                          <div className="flex-1 flex items-center justify-between text-sm">
                            <div className="flex items-center gap-3">
                              <span className="text-gray-600">
                                {formatActivityDate(activity.start_date)} - {formatActivityDate(activity.end_date)}
                              </span>
                              <span className="font-medium text-gray-900">{activity.partner_name}</span>
                              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                activity.status === 'completed' ? 'bg-gray-100 text-gray-700' :
                                activity.status === 'active' ? 'bg-blue-100 text-blue-700' :
                                'bg-green-100 text-green-700'
                              }`}>
                                {getActivityLabel(activity.status)}
                              </span>
                              {activity.published && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                  Published
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
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

                  {/* Previous Activity */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Previous Activity</h3>
                    {vehicleContext.previous_activity ? (
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <div className="flex items-start">
                          <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                          </svg>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-blue-900">{vehicleContext.previous_activity.activity_type}</p>
                            <p className="text-xs text-blue-700 mt-1">
                              {formatActivityDate(vehicleContext.previous_activity.start_date)}
                              {vehicleContext.previous_activity.end_date && ` - ${formatActivityDate(vehicleContext.previous_activity.end_date)}`}
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
                            <p className="text-sm font-medium text-green-900">{vehicleContext.next_activity.activity_type}</p>
                            <p className="text-xs text-green-700 mt-1">
                              {formatActivityDate(vehicleContext.next_activity.start_date)}
                              {vehicleContext.next_activity.end_date && ` - ${formatActivityDate(vehicleContext.next_activity.end_date)}`}
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
