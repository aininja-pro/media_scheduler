import React, { useState, useEffect } from 'react';

function Optimizer({ sharedOffice, onOfficeChange }) {
  // Use shared office from parent, fallback to 'Los Angeles' if not provided
  const selectedOffice = sharedOffice || 'Los Angeles';
  const setSelectedOffice = (office) => {
    if (onOfficeChange) {
      onOfficeChange(office);
    }
  };
  const [weekStart, setWeekStart] = useState('');
  const [minDays, setMinDays] = useState(7);
  const [isLoading, setIsLoading] = useState(false);

  // State for metrics
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState('');
  const [runResult, setRunResult] = useState(null);
  const [assignmentFilter, setAssignmentFilter] = useState('');
  const [selectedDay, setSelectedDay] = useState(null); // null = show all days
  const [loadingStage, setLoadingStage] = useState('');

  // Policy state (sliders)
  const [rankWeight, setRankWeight] = useState(1.0);
  const [geoMatch, setGeoMatch] = useState(100);
  const [pubRate, setPubRate] = useState(150);
  const [historyBonus, setHistoryBonus] = useState(50);
  const [tierCapPenalty, setTierCapPenalty] = useState(800);
  const [fairnessBase, setFairnessBase] = useState(200);
  const [fairnessStepUp, setFairnessStepUp] = useState(400);
  const [budgetPenalty, setBudgetPenalty] = useState(3);
  const [cooldownDays, setCooldownDays] = useState(30);
  const [enforceBudgetHard, setEnforceBudgetHard] = useState(false);
  const [maxPerPartnerPerDay, setMaxPerPartnerPerDay] = useState(1);
  const [maxPerPartnerPerWeek, setMaxPerPartnerPerWeek] = useState(2);
  const [preferNormalDays, setPreferNormalDays] = useState(false);

  // Vehicle context state
  const [selectedVin, setSelectedVin] = useState(null);
  const [vehicleContext, setVehicleContext] = useState(null);
  const [loadingVehicleContext, setLoadingVehicleContext] = useState(false);
  const [hoveredVin, setHoveredVin] = useState(null);
  const [hoverContext, setHoverContext] = useState(null);

  // Daily capacity settings
  const [dailyCapacities, setDailyCapacities] = useState({
    mon: 15,
    tue: 15,
    wed: 15,
    thu: 15,
    fri: 15,
    sat: 0,
    sun: 0
  });

  // Capacity editing state
  const [editingDay, setEditingDay] = useState(null);
  const [editValue, setEditValue] = useState(0);

  // Load offices from database
  const [offices, setOffices] = useState([]);

  // Get current Monday as default
  const getCurrentMonday = () => {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    const monday = new Date(today);
    monday.setDate(today.getDate() + daysToMonday);
    return monday.toISOString().split('T')[0];
  };

  // Track if data was loaded from cache
  const [dataSource, setDataSource] = useState(null); // 'cache' or 'fresh'

  // Initialize from sessionStorage on mount
  useEffect(() => {
    const savedOffice = sessionStorage.getItem('optimizer_office');
    const savedWeekStart = sessionStorage.getItem('optimizer_week_start');
    const savedMinDays = sessionStorage.getItem('optimizer_min_days');
    const savedMetrics = sessionStorage.getItem('optimizer_metrics');
    const savedRunResult = sessionStorage.getItem('optimizer_run_result');

    if (savedOffice) setSelectedOffice(savedOffice);
    if (savedWeekStart) {
      setWeekStart(savedWeekStart);
    } else {
      setWeekStart(getCurrentMonday());
    }
    if (savedMinDays) setMinDays(parseInt(savedMinDays));

    if (savedMetrics) {
      setMetrics(JSON.parse(savedMetrics));
      setDataSource('cache');
    }
    if (savedRunResult) {
      setRunResult(JSON.parse(savedRunResult));
    }
  }, []);

  // Load offices from database
  useEffect(() => {
    const loadOffices = async () => {
      try {
        const response = await fetch('http://localhost:8081/api/offices');
        const data = await response.json();
        if (data && data.length > 0) {
          setOffices(data.map(office => office.name));
          // Set default office if current selection is not in the list
          if (!data.find(o => o.name === selectedOffice)) {
            setSelectedOffice(data[0].name);
          }
        }
      } catch (err) {
        console.error('Failed to load offices:', err);
        // Fallback to hardcoded list if API fails
        setOffices(['Los Angeles', 'Atlanta', 'Chicago', 'Dallas', 'Denver', 'Detroit', 'Miami', 'Phoenix', 'San Francisco', 'Seattle']);
      }
    };
    loadOffices();
  }, []);

  // Load office-specific capacity defaults when office changes
  useEffect(() => {
    const loadOfficeCapacityDefaults = async () => {
      if (!selectedOffice) return;

      try {
        const response = await fetch(`http://localhost:8081/api/ui/phase7/office-default-capacity?office=${encodeURIComponent(selectedOffice)}`);
        if (!response.ok) {
          console.error('Failed to load office capacity defaults');
          return;
        }
        const data = await response.json();
        if (data.daily_capacities) {
          console.log(`Loaded capacity defaults for ${selectedOffice}:`, data.daily_capacities);
          setDailyCapacities(data.daily_capacities);
        }
      } catch (err) {
        console.error('Error loading office capacity defaults:', err);
      }
    };

    loadOfficeCapacityDefaults();
  }, [selectedOffice]);

  // Manual load function (no longer auto-loads)
  const loadOfficeData = async () => {
    if (!selectedOffice || !weekStart) {
      return;
    }

    setIsLoading(true);
    setError('');
    setLoadingStage('loading-vehicles');

    // Clear old assignments and selection when loading new data
    setRunResult(null);
    setSelectedDay(null);
    setAssignmentFilter('');
    sessionStorage.removeItem('optimizer_run_result');

    console.log(`Loading metrics for ${selectedOffice} week of ${weekStart}`);

    try {
      // Simulate progress through different stages for visual feedback
      await new Promise(resolve => setTimeout(resolve, 100));
      setLoadingStage('loading-partners');

      await new Promise(resolve => setTimeout(resolve, 100));
      setLoadingStage('loading-brands');

      await new Promise(resolve => setTimeout(resolve, 100));
      setLoadingStage('loading-availability');

      const params = new URLSearchParams({
        office: selectedOffice,
        week_start: weekStart,
        min_days: minDays
      });

      setLoadingStage('calculating-metrics');
      const response = await fetch(`http://localhost:8081/api/ui/phase7/overview?${params}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to load metrics');
      }

      console.log('Metrics loaded:', data);
      setMetrics(data);
      setDataSource('fresh');

      // Save to sessionStorage
      sessionStorage.setItem('optimizer_office', selectedOffice);
      sessionStorage.setItem('optimizer_week_start', weekStart);
      sessionStorage.setItem('optimizer_min_days', minDays.toString());
      sessionStorage.setItem('optimizer_metrics', JSON.stringify(data));
    } catch (err) {
      setError(err.message);
      setMetrics(null);
    } finally {
      setIsLoading(false);
      setLoadingStage('');
    }
  };

  // Clear cached data and reset to defaults
  const clearCachedData = () => {
    sessionStorage.removeItem('optimizer_office');
    sessionStorage.removeItem('optimizer_week_start');
    sessionStorage.removeItem('optimizer_min_days');
    sessionStorage.removeItem('optimizer_metrics');
    sessionStorage.removeItem('optimizer_run_result');

    setMetrics(null);
    setRunResult(null);
    setDataSource(null);
    setSelectedDay(null);
    setAssignmentFilter('');
    setError('');
  };

  const formatWeekRange = () => {
    if (!weekStart) return '';
    const start = new Date(weekStart);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    return `${start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
  };

  // Helper functions to display slider values
  const getPartnerQualityLabel = (weight) => {
    if (weight <= 0.3) return 'All Tiers (A+/A/B/C/D)';
    if (weight <= 0.8) return 'B+ and Better';
    if (weight <= 1.2) return 'A Tier and Better';
    if (weight <= 1.6) return 'A+ and A Only';
    return 'A+ Only';
  };

  const getLocalPriorityLabel = (value) => {
    // Higher value = MORE local (inverse of weight)
    if (value === 0) return 'Any Distance';
    const effectiveMiles = Math.round(300 - (value * 1.5)); // 200 = 0 miles (very local), 0 = 300 miles (far)
    if (effectiveMiles <= 50) return 'Very Local (<50 mi)';
    if (effectiveMiles <= 150) return `Regional (~${effectiveMiles} mi)`;
    return `Wide Area (~${effectiveMiles}+ mi)`;
  };

  const getPublicationRateLabel = (value) => {
    if (value === 0) return 'All Partners (0%)';
    const percentage = Math.round((value / 300) * 100);
    return `${percentage}%+ Publication Rate`;
  };

  const getEngagementLabel = (value) => {
    if (value < 45) return 'Re-engage Dormant Partners';
    if (value > 55) return 'Maintain Active Partners';
    return 'Balanced Mix';
  };

  const getWeekdayCapacity = () => {
    if (!metrics?.capacity) return 0;
    return ['mon', 'tue', 'wed', 'thu', 'fri']
      .reduce((sum, day) => sum + (metrics.capacity[day]?.slots || 0), 0);
  };

  const formatBudgetValue = () => {
    if (!metrics) return '--';
    const budget = 268000; // Example budget
    const used = 265800; // Example used
    const pct = ((used / budget) * 100).toFixed(0);
    return `$${(used/1000).toFixed(0)}k / $${(budget/1000).toFixed(0)}k (${pct}% used)`;
  };

  // Fetch vehicle context on hover/click
  const fetchVehicleContext = async (vin) => {
    if (vehicleContext && vehicleContext.vin === vin) {
      return; // Already loaded
    }

    setLoadingVehicleContext(true);
    try {
      const response = await fetch(`http://localhost:8081/api/ui/phase7/vehicle-context/${vin}`);
      if (!response.ok) {
        throw new Error('Failed to fetch vehicle context');
      }
      const data = await response.json();
      setVehicleContext(data);
    } catch (err) {
      console.error('Error fetching vehicle context:', err);
      setVehicleContext(null);
    } finally {
      setLoadingVehicleContext(false);
    }
  };

  // Fetch hover preview data
  const fetchHoverContext = async (vin) => {
    if (hoverContext && hoverContext.vin === vin) {
      return; // Already loaded
    }

    try {
      const response = await fetch(`http://localhost:8081/api/ui/phase7/vehicle-context/${vin}`);
      if (!response.ok) {
        throw new Error('Failed to fetch vehicle context');
      }
      const data = await response.json();
      setHoverContext(data);
    } catch (err) {
      console.error('Error fetching hover context:', err);
      setHoverContext(null);
    }
  };

  const handleVinHover = (vin) => {
    setHoveredVin(vin);
    fetchHoverContext(vin);
  };

  const handleVinLeave = () => {
    setHoveredVin(null);
    setHoverContext(null);
  };

  const handleVinClick = (vin) => {
    setSelectedVin(vin);
    fetchVehicleContext(vin);
    setHoveredVin(null); // Close hover tooltip when opening side panel
  };

  const closeSidePanel = () => {
    setSelectedVin(null);
    setVehicleContext(null);
  };

  const formatActivityDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const [progressStage, setProgressStage] = useState('');

  // Capacity editing handlers
  const handleCapacityEdit = (dayKey, currentValue) => {
    setEditingDay(dayKey);
    setEditValue(currentValue);
  };

  const saveCapacityEdit = () => {
    if (editingDay) {
      setDailyCapacities({
        ...dailyCapacities,
        [editingDay]: editValue
      });
    }
    setEditingDay(null);
  };

  const cancelCapacityEdit = () => {
    setEditingDay(null);
  };

  const runOptimizer = async () => {
    setIsLoading(true);
    setError('');
    setProgressStage('initializing');

    try {
      // Simulate progress stages with brief delays for visual feedback
      setProgressStage('loading-data');
      await new Promise(resolve => setTimeout(resolve, 200));

      setProgressStage('building-triples');
      await new Promise(resolve => setTimeout(resolve, 200));

      setProgressStage('applying-constraints');
      await new Promise(resolve => setTimeout(resolve, 200));

      setProgressStage('solving');

      // Use Phase 7 run endpoint
      const requestBody = {
        office: selectedOffice,
        week_start: weekStart,
        seed: 42,
        rank_weight: rankWeight,  // Partner Quality slider value
        geo_match: geoMatch,  // Local Priority slider value
        pub_rate: pubRate,  // Publishing Success slider value
        engagement_priority: historyBonus,  // Engagement Priority slider value
        max_per_partner_per_day: maxPerPartnerPerDay,  // Max vehicles per partner per day
        max_per_partner_per_week: maxPerPartnerPerWeek,  // Max vehicles per partner per week
        prefer_normal_days: preferNormalDays,  // Prioritize Partner Normal Days toggle
        daily_capacities: dailyCapacities  // Daily capacity overrides from UI
      };

      console.log('Sending daily_capacities to optimizer:', dailyCapacities);
      console.log('Full request body:', requestBody);

      const response = await fetch('http://localhost:8081/api/ui/phase7/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });

      setProgressStage('processing-results');
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to run optimizer');
      }

      // Store the full response
      setRunResult(data);
      console.log('Full runResult:', data);
      console.log('Run result:', data);

      // Save run result to sessionStorage
      sessionStorage.setItem('optimizer_run_result', JSON.stringify(data));

    } catch (err) {
      setError(err.message);
      setRunResult(null);
    } finally {
      setIsLoading(false);
      setProgressStage('');
    }
  };

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Progress Modal */}
      {isLoading && progressStage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-2xl p-8 max-w-md w-full mx-4">
            <div className="text-center">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Optimizing Schedule</h2>

              {/* Spinner */}
              <div className="mb-6">
                <svg className="animate-spin h-12 w-12 text-blue-600 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>

              {/* Progress stages */}
              <div className="space-y-3 text-left">
                <div className={`flex items-center ${progressStage === 'initializing' ? 'text-blue-600 font-medium' : progressStage > 'initializing' ? 'text-green-600' : 'text-gray-400'}`}>
                  <svg className="w-5 h-5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                    {progressStage > 'initializing' ? (
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    ) : (
                      <circle cx="10" cy="10" r="3" />
                    )}
                  </svg>
                  Initializing optimizer...
                </div>

                <div className={`flex items-center ${progressStage === 'loading-data' ? 'text-blue-600 font-medium' : progressStage > 'loading-data' ? 'text-green-600' : 'text-gray-400'}`}>
                  <svg className="w-5 h-5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                    {progressStage > 'loading-data' ? (
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    ) : (
                      <circle cx="10" cy="10" r="3" />
                    )}
                  </svg>
                  Loading vehicles and partners...
                </div>

                <div className={`flex items-center ${progressStage === 'building-triples' ? 'text-blue-600 font-medium' : progressStage > 'building-triples' ? 'text-green-600' : 'text-gray-400'}`}>
                  <svg className="w-5 h-5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                    {progressStage > 'building-triples' ? (
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    ) : (
                      <circle cx="10" cy="10" r="3" />
                    )}
                  </svg>
                  Building feasible schedules...
                </div>

                <div className={`flex items-center ${progressStage === 'applying-constraints' ? 'text-blue-600 font-medium' : progressStage > 'applying-constraints' ? 'text-green-600' : 'text-gray-400'}`}>
                  <svg className="w-5 h-5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                    {progressStage > 'applying-constraints' ? (
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    ) : (
                      <circle cx="10" cy="10" r="3" />
                    )}
                  </svg>
                  Applying cooldown and constraints...
                </div>

                <div className={`flex items-center ${progressStage === 'solving' ? 'text-blue-600 font-medium' : progressStage > 'solving' ? 'text-green-600' : 'text-gray-400'}`}>
                  <svg className="w-5 h-5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                    {progressStage > 'solving' ? (
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    ) : (
                      <circle cx="10" cy="10" r="3" />
                    )}
                  </svg>
                  Running OR-Tools solver...
                </div>

                <div className={`flex items-center ${progressStage === 'processing-results' ? 'text-blue-600 font-medium' : progressStage > 'processing-results' ? 'text-green-600' : 'text-gray-400'}`}>
                  <svg className="w-5 h-5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                    {progressStage > 'processing-results' ? (
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    ) : (
                      <circle cx="10" cy="10" r="3" />
                    )}
                  </svg>
                  Processing results...
                </div>
              </div>

              <div className="mt-6 text-sm text-gray-500">
                Finding optimal assignments for {metrics.vehicles.available} vehicles...
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading Indicator for Office/Week Changes */}
      {isLoading && loadingStage && !progressStage && (
        <div className="fixed inset-0 bg-black bg-opacity-30 z-40 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Loading Office Data</h3>

              {/* Spinner */}
              <div className="mb-4">
                <svg className="animate-spin h-10 w-10 text-blue-600 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>

              {/* Loading stage text */}
              <div className="text-sm text-gray-600">
                {loadingStage === 'loading-vehicles' && 'Loading vehicles...'}
                {loadingStage === 'loading-partners' && 'Loading media partners...'}
                {loadingStage === 'loading-brands' && 'Loading approved brands...'}
                {loadingStage === 'loading-availability' && 'Checking availability...'}
                {loadingStage === 'calculating-metrics' && 'Calculating metrics...'}
              </div>

              <div className="mt-3 text-xs text-gray-500">
                {selectedOffice} • Week of {weekStart && new Date(weekStart + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Compact Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">Schedule Optimizer</h1>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600">Office</label>
              <select
                value={selectedOffice}
                onChange={(e) => setSelectedOffice(e.target.value)}
                className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {offices.map(office => (
                  <option key={office} value={office}>{office} ({office.slice(0,3).toUpperCase()})</option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600">Week Starting</label>
              <input
                type="date"
                value={weekStart}
                onChange={(e) => setWeekStart(e.target.value)}
                className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600">Min Available Days</label>
              <input
                type="number"
                min="1"
                max="14"
                value={minDays}
                onChange={(e) => setMinDays(parseInt(e.target.value) || 7)}
                className="w-16 border border-gray-300 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={loadOfficeData}
                disabled={isLoading}
                className={`px-4 py-1.5 rounded text-sm font-medium ${
                  isLoading
                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed opacity-50'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {isLoading && loadingStage ? 'Loading...' : 'Load Data'}
              </button>

              {dataSource === 'cache' && (
                <span className="inline-flex items-center rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                  📦 Cached Data
                </span>
              )}
              {dataSource === 'fresh' && (
                <span className="inline-flex items-center rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
                  ✓ Fresh Data
                </span>
              )}

              {metrics && (
                <button
                  onClick={clearCachedData}
                  className="text-xs text-gray-500 hover:text-gray-700 underline"
                  title="Clear cached data and reset"
                >
                  Clear
                </button>
              )}

              <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                Seed: 42
              </span>

              <button
                onClick={runOptimizer}
                disabled={isLoading || !metrics}
                className={`px-6 py-1.5 rounded text-sm font-medium ${
                  isLoading || !metrics
                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed opacity-50'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
                title={!metrics ? 'Load office data first' : ''}
              >
                {isLoading && progressStage ? 'Running...' : 'Run Optimizer'}
              </button>

              {/* Optional status chips */}
              {runResult?.status && (
                <span className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                  {runResult.status}
                </span>
              )}
              {runResult?.assignments && (
                <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                  Assignments: {runResult.assignments.length}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Error display */}
        {error && (
          <div className="mt-2 text-sm text-red-600">
            {error}
          </div>
        )}
      </div>

      {/* Metrics Bar */}
      {metrics && (
        <div className="bg-white border-b px-6 py-3">
          <div className="grid grid-cols-6 gap-4">
            <div className="flex flex-col">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Vehicles</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-semibold text-gray-900">{metrics.vehicles.available}</span>
                <span className="text-sm text-gray-500">/ {metrics.vehicles.total} available</span>
              </div>
            </div>

            <div className="flex flex-col">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Partners</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-semibold text-gray-900">{metrics.partners.eligible}</span>
                <span className="text-sm text-gray-500">/ {metrics.partners.total} eligible</span>
              </div>
            </div>

            <div className="flex flex-col">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Available Brands</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-semibold text-gray-900">{metrics.makes_in_scope}</span>
                <span className="text-sm text-gray-500">unique makes</span>
              </div>
            </div>

            <div className="flex flex-col">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Week Capacity</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-semibold text-gray-900">{getWeekdayCapacity()}</span>
                <span className="text-sm text-gray-500">slots</span>
              </div>
            </div>

            <div className="flex flex-col">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Possible Schedules</div>
              <div className="flex items-baseline gap-1">
                <span className="text-sm text-gray-500">{metrics.feasible_triples_pre_cooldown.toLocaleString()}</span>
                <span className="text-sm text-gray-500">→ Ready:</span>
                <span className="text-2xl font-semibold text-gray-900">{metrics.feasible_triples_post_cooldown.toLocaleString()}</span>
                <span className="text-sm text-red-600">(-{metrics.cooldown_removed_triples.toLocaleString()})</span>
              </div>
            </div>

            <div className="flex flex-col">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                Budget ({metrics.budget_status?.year} {metrics.budget_status?.current_quarter})
              </div>
              {metrics.budget_status?.quarter_totals ? (
                <div className="flex items-baseline gap-1">
                  <span className="text-sm text-gray-500">
                    ${(metrics.budget_status.quarter_totals.used / 1000).toFixed(1)}k
                  </span>
                  <span className="text-sm text-gray-500">/</span>
                  <span className={`text-2xl font-semibold ${
                    metrics.budget_status.quarter_totals.used > metrics.budget_status.quarter_totals.budget
                      ? 'text-red-600'
                      : 'text-gray-900'
                  }`}>
                    ${(metrics.budget_status.quarter_totals.budget / 1000).toFixed(0)}k
                  </span>
                  <span className="text-sm text-gray-500">
                    ({((metrics.budget_status.quarter_totals.used / metrics.budget_status.quarter_totals.budget) * 100).toFixed(0)}% used)
                  </span>
                </div>
              ) : (
                <div className="text-sm text-gray-500">No budget data</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex h-full">
        {/* Left Panel - Schedule Settings */}
        <div className="w-80 bg-white border-r p-6 overflow-y-auto">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Schedule Settings</h2>

          <div className="space-y-6">
            {/* Schedule Priorities Section */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-4">Schedule Priorities</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium text-gray-700">Partner Quality</label>
                    <span className="text-xs font-semibold text-blue-600">{getPartnerQualityLabel(rankWeight)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={rankWeight}
                    onChange={(e) => setRankWeight(parseFloat(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-1 px-1">
                    <span>All Tiers</span>
                    <span>B+</span>
                    <span>A</span>
                    <span>A+</span>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium text-gray-700">Local Priority</label>
                    <span className="text-xs font-semibold text-blue-600">{getLocalPriorityLabel(geoMatch)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="200"
                    step="10"
                    value={geoMatch}
                    onChange={(e) => setGeoMatch(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-1 px-1">
                    <span>Any Distance</span>
                    <span>~200 mi</span>
                    <span>~100 mi</span>
                    <span>Very Local</span>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium text-gray-700">Publication Rate</label>
                    <span className="text-xs font-semibold text-blue-600">{getPublicationRateLabel(pubRate)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="300"
                    step="30"
                    value={pubRate}
                    onChange={(e) => setPubRate(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-1 px-1">
                    <span>0%</span>
                    <span>25%</span>
                    <span>50%</span>
                    <span>75%</span>
                    <span>100%</span>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium text-gray-700">Engagement Priority</label>
                    <span className="text-xs font-semibold text-blue-600">{getEngagementLabel(historyBonus)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={historyBonus}
                    onChange={(e) => setHistoryBonus(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-1 px-1">
                    <span>Dormant</span>
                    <span>Balanced</span>
                    <span>Active</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Business Rules Section */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-4">Business Rules</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span>Partner Limits</span>
                  <span className="text-green-600">✓ Active</span>
                </div>
                <div className="flex justify-between">
                  <span>Fair Distribution</span>
                  <span className="text-green-600">✓ Active</span>
                </div>
                <div className="flex justify-between">
                  <span>Budget Tracking</span>
                  <span className="text-green-600">✓ Active</span>
                </div>
                <div className="flex justify-between">
                  <span>Cooldown Period</span>
                  <span className="text-gray-700">30 days</span>
                </div>
                <div className="pt-2 border-t border-gray-200">
                  <label className="text-sm text-gray-600 mb-2 block">Max Vehicles per Partner per Day</label>
                  <select
                    value={maxPerPartnerPerDay}
                    onChange={(e) => setMaxPerPartnerPerDay(parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="1">1 (Recommended)</option>
                    <option value="2">2</option>
                    <option value="3">3</option>
                    <option value="0">Unlimited</option>
                  </select>
                  <div className="text-xs text-gray-500 mt-1">
                    Limits how many vehicles can start on the same day for one partner
                  </div>
                </div>
                <div className="pt-2 border-t border-gray-200">
                  <label className="text-sm text-gray-600 mb-2 block">Max Vehicles per Partner per Week</label>
                  <select
                    value={maxPerPartnerPerWeek}
                    onChange={(e) => setMaxPerPartnerPerWeek(parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="1">1</option>
                    <option value="2">2 (Recommended)</option>
                    <option value="3">3</option>
                    <option value="4">4</option>
                    <option value="5">5</option>
                    <option value="0">Unlimited</option>
                  </select>
                  <div className="text-xs text-gray-500 mt-1">
                    Limits total vehicles assigned to one partner during the entire week
                  </div>
                </div>
                <div className="pt-2 border-t border-gray-200">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={preferNormalDays}
                      onChange={(e) => setPreferNormalDays(e.target.checked)}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <span className="ml-2 text-sm text-gray-700">Prioritize Partner Normal Days</span>
                  </label>
                  <div className="text-xs text-gray-500 mt-1 ml-6">
                    Favor scheduling partners on their historically preferred day of week
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Center Panel - Week Overview */}
        <div className="flex-1 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">
            Week Overview: {metrics ? formatWeekRange() : 'Select week'}
          </h2>
          <p className="text-sm text-gray-500 mb-4">Daily Capacity</p>

          {metrics ? (
            <div>
              {/* Capacity Controls */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <label className="text-sm font-medium text-gray-700">
                      Weekly Total:
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="350"
                      value={Object.values(dailyCapacities).reduce((a, b) => a + b, 0)}
                      onChange={(e) => {
                        const newTotal = Math.max(0, Math.min(350, parseInt(e.target.value) || 0));
                        // Distribute evenly across weekdays only
                        const perDay = Math.floor(newTotal / 5);
                        const remainder = newTotal % 5;
                        setDailyCapacities({
                          mon: perDay + (remainder > 0 ? 1 : 0),
                          tue: perDay + (remainder > 1 ? 1 : 0),
                          wed: perDay + (remainder > 2 ? 1 : 0),
                          thu: perDay + (remainder > 3 ? 1 : 0),
                          fri: perDay + (remainder > 4 ? 1 : 0),
                          sat: 0,
                          sun: 0
                        });
                      }}
                      className="w-24 px-3 py-2 border border-gray-300 rounded-md text-sm font-semibold text-center focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    <span className="text-sm text-gray-600">slots</span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        // Reset to office defaults (loaded from API)
                        const loadOfficeDefaults = async () => {
                          try {
                            const response = await fetch(`http://localhost:8081/api/ui/phase7/office-default-capacity?office=${encodeURIComponent(selectedOffice)}`);
                            if (response.ok) {
                              const data = await response.json();
                              if (data.daily_capacities) {
                                setDailyCapacities(data.daily_capacities);
                              }
                            }
                          } catch (err) {
                            console.error('Error loading defaults:', err);
                          }
                        };
                        loadOfficeDefaults();
                      }}
                      className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                      Reset to Defaults
                    </button>
                  </div>
                </div>

                {/* Individual Day Inputs */}
                <div className="grid grid-cols-7 gap-2">
                  {[
                    { key: 'mon', label: 'Mon' },
                    { key: 'tue', label: 'Tue' },
                    { key: 'wed', label: 'Wed' },
                    { key: 'thu', label: 'Thu' },
                    { key: 'fri', label: 'Fri' },
                    { key: 'sat', label: 'Sat' },
                    { key: 'sun', label: 'Sun' }
                  ].map((day) => (
                    <div key={day.key} className="flex flex-col">
                      <label className="text-xs font-medium text-gray-600 mb-1 text-center">
                        {day.label}
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="50"
                        value={dailyCapacities[day.key]}
                        onChange={(e) => {
                          const value = Math.max(0, Math.min(50, parseInt(e.target.value) || 0));
                          setDailyCapacities({
                            ...dailyCapacities,
                            [day.key]: value
                          });
                        }}
                        className="w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm font-semibold text-center focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                  ))}
                </div>

                <p className="mt-3 text-xs text-gray-600">
                  Set weekly total to distribute evenly across weekdays, or edit individual days. Changes apply when you run the optimizer.
                </p>
              </div>

              {/* Day Tiles Grid */}
              <div className="grid grid-cols-7 gap-3 mb-8">
                {[
                  { key: 'mon', label: 'Mon', dayOffset: 0 },
                  { key: 'tue', label: 'Tue', dayOffset: 1 },
                  { key: 'wed', label: 'Wed', dayOffset: 2 },
                  { key: 'thu', label: 'Thu', dayOffset: 3 },
                  { key: 'fri', label: 'Fri', dayOffset: 4 },
                  { key: 'sat', label: 'Sat', dayOffset: 5 },
                  { key: 'sun', label: 'Sun', dayOffset: 6 }
                ].map((day) => {
                  const capacity = metrics.capacity[day.key];

                  // Use dailyCapacities state (user-edited values) instead of backend metrics
                  const totalSlots = dailyCapacities[day.key];
                  const enabled = totalSlots > 0;

                  // Calculate actual date
                  const weekStartDate = new Date(weekStart + 'T00:00:00');
                  const dayDate = new Date(weekStartDate);
                  dayDate.setDate(weekStartDate.getDate() + day.dayOffset);
                  const dayNumber = dayDate.getDate();

                  // Calculate usage if assignments exist
                  let usedSlots = 0;
                  if (runResult?.starts_by_day) {
                    usedSlots = runResult.starts_by_day[day.key] || 0;
                  }
                  const isFull = usedSlots >= totalSlots && totalSlots > 0;
                  const isNearCapacity = usedSlots > totalSlots * 0.8 && !isFull && totalSlots > 0;

                  const isSelected = selectedDay === day.key;
                  const isEditing = editingDay === day.key;

                  return (
                    <div
                      key={day.key}
                      className={[
                        "rounded-lg border p-3 text-center transition-all relative",
                        isEditing ? "ring-2 ring-purple-500 border-purple-500 bg-purple-50" :
                        enabled ? "cursor-pointer hover:shadow-md" : "cursor-not-allowed",
                        isSelected && !isEditing
                          ? "ring-2 ring-blue-500 border-blue-500 bg-blue-50 shadow-lg"
                          : isFull && !isEditing
                            ? "border-green-400 bg-green-100"
                            : isNearCapacity && !isEditing
                              ? "border-yellow-400 bg-yellow-50 hover:border-yellow-500"
                              : enabled && !isEditing
                                ? "border-emerald-200 bg-emerald-50 hover:border-emerald-300"
                                : !isEditing ? "border-rose-200 bg-rose-50" : ""
                      ].join(" ")}
                    >
                      {isSelected && !isEditing && (
                        <div className="absolute -left-2 top-1/2 -translate-y-1/2 text-blue-500 font-bold">
                          ▸
                        </div>
                      )}

                      {/* Edit Button */}
                      {!isEditing && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCapacityEdit(day.key, dailyCapacities[day.key]);
                          }}
                          className="absolute top-2 right-2 p-1 hover:bg-white/80 rounded transition-colors"
                          title="Edit capacity"
                        >
                          <svg className="w-3 h-3 text-gray-400 hover:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                          </svg>
                        </button>
                      )}

                      <div
                        onClick={(e) => {
                          if (!isEditing && enabled) {
                            setSelectedDay(isSelected ? null : day.key);
                          }
                        }}
                        className={!isEditing ? "cursor-pointer" : ""}
                      >
                        <div className="text-sm text-slate-600 font-medium">
                          {day.label} {dayNumber}
                        </div>

                        {isEditing ? (
                          <div className="mt-2 space-y-2">
                            <input
                              type="number"
                              min="0"
                              max="50"
                              value={editValue}
                              onChange={(e) => setEditValue(Math.max(0, Math.min(50, parseInt(e.target.value) || 0)))}
                              onClick={(e) => e.stopPropagation()}
                              className="w-full px-2 py-1 text-center text-lg font-semibold border border-purple-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-500"
                              autoFocus
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  saveCapacityEdit();
                                } else if (e.key === 'Escape') {
                                  cancelCapacityEdit();
                                }
                              }}
                            />
                            <div className="flex gap-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  saveCapacityEdit();
                                }}
                                className="flex-1 px-2 py-1 text-xs font-medium text-white bg-purple-600 hover:bg-purple-700 rounded"
                              >
                                ✓
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  cancelCapacityEdit();
                                }}
                                className="flex-1 px-2 py-1 text-xs font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded"
                              >
                                ✕
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className={[
                              "text-2xl font-semibold leading-tight mt-1",
                              isFull ? "text-green-700" :
                              isNearCapacity ? "text-yellow-700" :
                              enabled ? "text-emerald-700" : "text-rose-700"
                            ].join(" ")}>
                              {runResult ? (
                                enabled ? (
                                  <span>{usedSlots}/{totalSlots}</span>
                                ) : (
                                  <span className="line-through">{totalSlots}</span>
                                )
                              ) : (
                                enabled ? totalSlots : <span className="line-through">{totalSlots}</span>
                              )}
                            </div>
                            <div className="text-xs text-slate-500 mt-1">
                              {isFull ? 'Full' :
                               capacity?.notes ? (
                                capacity.notes === 'blackout' ? 'Blackout' :
                                capacity.notes.includes('Default') ? 'Default' :
                                capacity.notes
                              ) : runResult && enabled ? `${Math.round((usedSlots/totalSlots)*100)}% used` : 'Available'}
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Assignments Table or Placeholder */}
              {runResult?.assignments && runResult.assignments.length > 0 ? (
                <div className="bg-white rounded-lg shadow-sm border">
                  <div className="p-4 border-b">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900">
                        Assignments {selectedDay && (() => {
                          const dayMap = { mon: 0, tue: 1, wed: 2, thu: 3, fri: 4, sat: 5, sun: 6 };
                          const weekStartDate = new Date(weekStart + 'T00:00:00');
                          const selectedDate = new Date(weekStartDate);
                          selectedDate.setDate(weekStartDate.getDate() + dayMap[selectedDay]);
                          return `- ${selectedDate.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}`;
                        })()}
                      </h3>
                      <div className="flex items-center gap-4">
                        {selectedDay && (
                          <button
                            onClick={() => setSelectedDay(null)}
                            className="text-xs text-blue-600 hover:text-blue-700 underline"
                          >
                            Show all days
                          </button>
                        )}
                        {runResult?.starts_by_day && (
                          <span className="text-sm text-gray-600">
                            Mon {runResult.starts_by_day.mon} •
                            Tue {runResult.starts_by_day.tue} •
                            Wed {runResult.starts_by_day.wed} •
                            Thu {runResult.starts_by_day.thu} •
                            Fri {runResult.starts_by_day.fri}
                            {(runResult.starts_by_day.sat > 0 || runResult.starts_by_day.sun > 0) &&
                              ` • Sat ${runResult.starts_by_day.sat} • Sun ${runResult.starts_by_day.sun}`}
                          </span>
                        )}
                        <input
                          type="text"
                          placeholder="Filter VIN or partner..."
                          value={assignmentFilter}
                          onChange={(e) => setAssignmentFilter(e.target.value)}
                          className="px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Start</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">VIN</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Partner</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Make</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {runResult.assignments
                          .filter(a => {
                            // Filter by selected day
                            if (selectedDay) {
                              const assignmentDate = new Date(a.start_day + 'T00:00:00');
                              const dayOfWeek = assignmentDate.getDay();
                              // JavaScript: 0=Sunday, 1=Monday, 2=Tuesday, etc.
                              const dayMap = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
                              if (dayOfWeek !== dayMap[selectedDay]) return false;
                            }

                            // Filter by search text
                            if (!assignmentFilter) return true;
                            const filter = assignmentFilter.toLowerCase();
                            return a.vin?.toLowerCase().includes(filter) ||
                                   a.partner_name?.toLowerCase().includes(filter) ||
                                   a.person_id?.toString().includes(filter);
                          })
                          .sort((a, b) => {
                            // Sort by start_day asc, then score desc
                            if (a.start_day !== b.start_day) {
                              return a.start_day < b.start_day ? -1 : 1;
                            }
                            return b.score - a.score;
                          })
                          .map((assignment, idx) => (
                            <tr key={`${assignment.vin}-${assignment.person_id}`} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {new Date(assignment.start_day + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900 relative">
                                <button
                                  onClick={() => handleVinClick(assignment.vin)}
                                  onMouseEnter={() => handleVinHover(assignment.vin)}
                                  onMouseLeave={handleVinLeave}
                                  className="text-blue-600 hover:text-blue-800 hover:underline cursor-pointer focus:outline-none"
                                >
                                  {assignment.vin}
                                </button>

                                {/* Hover Tooltip */}
                                {hoveredVin === assignment.vin && hoverContext && (
                                  <div className="absolute z-50 left-0 top-full mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-xl p-4">
                                    <div className="space-y-2">
                                      <div className="flex justify-between items-start">
                                        <div>
                                          <p className="text-sm font-semibold text-gray-900">{hoverContext.make} {hoverContext.model}</p>
                                          <p className="text-xs text-gray-500">{hoverContext.office}</p>
                                        </div>
                                        <span className="text-xs text-gray-400 italic">{hoverContext.mileage}</span>
                                      </div>

                                      <div className="border-t pt-2 space-y-1">
                                        <div className="text-xs">
                                          <span className="font-medium text-gray-700">Previous:</span>
                                          <span className="text-gray-600 ml-1">
                                            {hoverContext.previous_activity
                                              ? `${hoverContext.previous_activity.activity_type} (${formatActivityDate(hoverContext.previous_activity.start_date)})`
                                              : 'None'}
                                          </span>
                                        </div>
                                        <div className="text-xs">
                                          <span className="font-medium text-gray-700">Next:</span>
                                          <span className="text-gray-600 ml-1">
                                            {hoverContext.next_activity
                                              ? `${hoverContext.next_activity.activity_type} (${formatActivityDate(hoverContext.next_activity.start_date)})`
                                              : 'None'}
                                          </span>
                                        </div>
                                      </div>

                                      <div className="border-t pt-2">
                                        <p className="text-xs text-blue-600 font-medium">Click for full timeline →</p>
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {assignment.partner_name || `Partner ${assignment.person_id}`}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{assignment.make}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{assignment.model}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{assignment.score}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : runResult ? (
                <div className="bg-white rounded-lg shadow-sm border p-12">
                  <div className="text-center">
                    <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p className="mt-2 text-sm text-gray-500">No assignments returned</p>
                    <p className="text-xs text-gray-400 mt-1">The optimizer did not produce any assignments for this configuration</p>
                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-lg shadow-sm border p-12">
                  <div className="text-center">
                    <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="mt-2 text-sm text-gray-500">Schedule View</p>
                    <p className="text-xs text-gray-400 mt-1">Run the optimizer to see assignments</p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border p-12">
              <div className="text-center">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="mt-2 text-sm text-gray-500">Schedule View Coming Soon</p>
                <p className="text-xs text-gray-400 mt-1">This area will display the optimized schedule with vehicle-partner assignments</p>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel - Audit & Reports */}
        <div className="w-80 bg-white border-l p-6 overflow-y-auto">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Audit & Reports</h2>

          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Fairness Metrics</h3>
              <div className="bg-gray-50 rounded p-3">
                {runResult?.fairness_summary ? (
                  <div className="space-y-3 text-sm">
                    {/* Basic Stats */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Partners Used:</span>
                        <span className="font-medium text-gray-900">{runResult.fairness_summary.partners_assigned || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Max per Partner:</span>
                        <span className="font-medium text-gray-900">{runResult.fairness_summary.max_per_partner || 0}</span>
                      </div>
                      {runResult.fairness_summary.num_partners !== undefined && (
                        <div className="flex justify-between">
                          <span className="text-gray-600">Multiple Vehicles:</span>
                          <span className="font-medium text-gray-900">{runResult.fairness_summary.partners_with_multiple || 0}</span>
                        </div>
                      )}
                    </div>

                    {/* Gini Coefficient */}
                    <div className="border-t pt-2">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-medium text-gray-500 uppercase">Gini Coefficient</span>
                        <span className="text-sm font-semibold text-gray-900">
                          {runResult.fairness_summary.gini_coefficient !== undefined
                            ? runResult.fairness_summary.gini_coefficient.toFixed(2)
                            : (runResult.fairness_summary.gini || 0).toFixed(2)}
                        </span>
                      </div>
                      <div className="flex items-center">
                        <div className="flex-1 bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              (runResult.fairness_summary.gini_coefficient || runResult.fairness_summary.gini || 0) < 0.3
                                ? 'bg-green-500'
                                : (runResult.fairness_summary.gini_coefficient || runResult.fairness_summary.gini || 0) < 0.5
                                  ? 'bg-yellow-500'
                                  : 'bg-orange-500'
                            }`}
                            style={{ width: `${((runResult.fairness_summary.gini_coefficient || runResult.fairness_summary.gini || 0) * 100)}%` }}
                          ></div>
                        </div>
                      </div>
                      <div className="flex justify-between text-xs text-gray-400 mt-1">
                        <span>Equal</span>
                        <span>Concentrated</span>
                      </div>
                      <p className="text-xs text-gray-500 mt-2">
                        {(runResult.fairness_summary.gini_coefficient || runResult.fairness_summary.gini || 0) < 0.3
                          ? '✓ Well distributed'
                          : (runResult.fairness_summary.gini_coefficient || runResult.fairness_summary.gini || 0) < 0.5
                            ? '⚠ Moderate concentration'
                            : '⚠ High concentration'}
                      </p>
                    </div>

                    {/* Additional Metrics if available */}
                    {(runResult.fairness_summary.hhi !== undefined ||
                      runResult.fairness_summary.top_5_share !== undefined ||
                      runResult.fairness_summary.top_1_share !== undefined) && (
                      <div className="border-t pt-2 space-y-1">
                        <p className="text-xs font-medium text-gray-500 uppercase mb-1.5">Concentration</p>
                        {runResult.fairness_summary.hhi !== undefined && (
                          <div className="flex justify-between text-xs">
                            <span className="text-gray-600">HHI Index:</span>
                            <span className="font-medium text-gray-900">{(runResult.fairness_summary.hhi * 10000).toFixed(0)}</span>
                          </div>
                        )}
                        {runResult.fairness_summary.top_1_share !== undefined && (
                          <div className="flex justify-between text-xs">
                            <span className="text-gray-600">Top Partner:</span>
                            <span className="font-medium text-gray-900">{(runResult.fairness_summary.top_1_share * 100).toFixed(0)}%</span>
                          </div>
                        )}
                        {runResult.fairness_summary.top_5_share !== undefined && (
                          <div className="flex justify-between text-xs">
                            <span className="text-gray-600">Top 5 Partners:</span>
                            <span className="font-medium text-gray-900">{(runResult.fairness_summary.top_5_share * 100).toFixed(0)}%</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-gray-400">Run optimizer to see metrics</div>
                )}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Cap Violations</h3>
              <div className="bg-gray-50 rounded p-3">
                {runResult?.cap_summary ? (
                  <div className="space-y-2 text-sm">
                    {runResult.cap_summary.violations && runResult.cap_summary.violations.length > 0 ? (
                      <>
                        {runResult.cap_summary.violations.map((violation, idx) => (
                          <div key={idx} className="text-red-600">
                            {violation.tier}: {violation.count} (cap: {violation.cap})
                          </div>
                        ))}
                        <div className="text-xs text-gray-500">
                          Penalty: {runResult.cap_summary.total_penalty || 0}
                        </div>
                      </>
                    ) : (
                      <div className="text-green-600">✓ No cap violations</div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-gray-400">Run optimizer to see metrics</div>
                )}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Budget Status</h3>
              <div className="bg-gray-50 rounded p-3">
                {runResult?.budget_summary ? (
                  <div className="space-y-3 text-sm">
                    {runResult.budget_summary.fleets && Object.entries(runResult.budget_summary.fleets).map(([fleet, data]) => (
                      <div key={fleet}>
                        <div className="flex justify-between items-center">
                          <span className="font-medium text-gray-900">{fleet}:</span>
                          <div className="flex items-center gap-1">
                            <span className={data.current > data.budget ? 'text-red-600 font-medium' : 'text-green-600 font-medium'}>
                              ${data.current?.toLocaleString()}
                            </span>
                            <span className="text-gray-400">/</span>
                            <span className={data.current > data.budget ? 'text-red-600 font-medium' : 'text-green-700 font-semibold'}>
                              ${data.budget?.toLocaleString()}
                            </span>
                          </div>
                        </div>
                        {data.planned > 0 && (
                          <div className="flex justify-end items-center text-xs text-gray-500 mt-0.5">
                            <span>+${data.planned?.toLocaleString()} this run → </span>
                            <span className={data.projected > data.budget ? 'text-red-600 font-medium ml-1' : 'text-blue-600 font-medium ml-1'}>
                              ${data.projected?.toLocaleString()} projected
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                    {runResult.budget_summary.total && (
                      <div className="border-t pt-2 mt-2">
                        <div className="flex justify-between items-center font-semibold">
                          <span className="text-gray-900">Total:</span>
                          <div className="flex items-center gap-1">
                            <span className={runResult.budget_summary.total.current > runResult.budget_summary.total.budget ? 'text-red-600' : 'text-green-600'}>
                              ${runResult.budget_summary.total.current?.toLocaleString()}
                            </span>
                            <span className="text-gray-400">/</span>
                            <span className={runResult.budget_summary.total.current > runResult.budget_summary.total.budget ? 'text-red-600' : 'text-green-700'}>
                              ${runResult.budget_summary.total.budget?.toLocaleString()}
                            </span>
                          </div>
                        </div>
                        {runResult.budget_summary.total.planned > 0 && (
                          <div className="flex justify-end items-center text-xs text-gray-500 mt-0.5">
                            <span>+${runResult.budget_summary.total.planned?.toLocaleString()} this run → </span>
                            <span className={runResult.budget_summary.total.projected > runResult.budget_summary.total.budget ? 'text-red-600 font-semibold ml-1' : 'text-blue-600 font-semibold ml-1'}>
                              ${runResult.budget_summary.total.projected?.toLocaleString()} projected
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-gray-400">Run optimizer to see metrics</div>
                )}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Objective Breakdown</h3>
              <div className="bg-gray-50 rounded p-3">
                {runResult?.objective_breakdown ? (
                  <div className="space-y-3 text-sm">
                    {/* Positive Score */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Raw Score:</span>
                        <span className="font-medium text-green-600">+{runResult.objective_breakdown.raw_score?.toLocaleString() || 0}</span>
                      </div>
                      <p className="text-xs text-gray-500">Points from good matches (quality, location, publication rate)</p>
                    </div>

                    {/* Penalties */}
                    <div className="border-t pt-2 space-y-1.5">
                      <p className="text-xs font-medium text-gray-500 uppercase">Penalties</p>

                      {runResult.objective_breakdown.cap_penalty > 0 && (
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-600">Tier Cap Violations:</span>
                          <span className="font-medium text-red-600">-{runResult.objective_breakdown.cap_penalty?.toLocaleString()}</span>
                        </div>
                      )}

                      {runResult.objective_breakdown.fairness_penalty > 0 && (
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-600">Fairness Concentration:</span>
                          <span className="font-medium text-red-600">-{runResult.objective_breakdown.fairness_penalty?.toLocaleString()}</span>
                        </div>
                      )}

                      {runResult.objective_breakdown.budget_penalty > 0 && (
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-600">Budget Overages:</span>
                          <span className="font-medium text-red-600">-{runResult.objective_breakdown.budget_penalty?.toLocaleString()}</span>
                        </div>
                      )}

                      {runResult.objective_breakdown.total_penalties === 0 && (
                        <div className="text-xs text-green-600">✓ No penalties applied</div>
                      )}

                      {runResult.objective_breakdown.total_penalties > 0 && (
                        <div className="flex justify-between text-xs font-medium border-t pt-1 mt-1">
                          <span className="text-gray-700">Total Penalties:</span>
                          <span className="text-red-600">-{runResult.objective_breakdown.total_penalties?.toLocaleString()}</span>
                        </div>
                      )}
                    </div>

                    {/* Net Score */}
                    <div className="border-t pt-2">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-gray-700">Net Score:</span>
                        <span className="text-lg font-bold text-blue-600">{runResult.objective_breakdown.net_score?.toLocaleString() || 0}</span>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">Final optimized score</p>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-gray-400">Run optimizer to see breakdown</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Vehicle Context Side Panel */}
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
                            {vehicleContext.previous_activity.type === 'loan' && vehicleContext.previous_activity.published && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 mt-2">
                                Published
                              </span>
                            )}
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

                  {/* Timeline */}
                  {vehicleContext.timeline && vehicleContext.timeline.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Activity Timeline</h3>
                      <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
                        <div className="space-y-3">
                          {vehicleContext.timeline.slice(0, 10).map((item, idx) => (
                            <div key={idx} className="flex items-start text-xs">
                              <div className="flex-shrink-0 w-2 h-2 bg-gray-400 rounded-full mt-1.5 mr-3"></div>
                              <div className="flex-1">
                                <p className="font-medium text-gray-900">{item.activity_type}</p>
                                <p className="text-gray-600">
                                  {formatActivityDate(item.start_date)}
                                  {item.end_date && ` - ${formatActivityDate(item.end_date)}`}
                                </p>
                                {item.type === 'loan' && item.published && (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 mt-1">
                                    Published
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
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

export default Optimizer;