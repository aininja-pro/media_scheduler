import React, { useState, useEffect } from 'react';

function Optimizer() {
  // State for controls
  const [selectedOffice, setSelectedOffice] = useState('Los Angeles');
  const [weekStart, setWeekStart] = useState('');
  const [minDays, setMinDays] = useState(7);
  const [isLoading, setIsLoading] = useState(false);

  // State for metrics
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState('');
  const [runResult, setRunResult] = useState(null);
  const [assignmentFilter, setAssignmentFilter] = useState('');
  const [selectedDay, setSelectedDay] = useState(null); // null = show all days

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

  const offices = ['Los Angeles', 'Atlanta', 'Chicago', 'Dallas', 'Denver', 'Detroit', 'Miami', 'Phoenix', 'San Francisco', 'Seattle'];

  // Get current Monday as default
  const getCurrentMonday = () => {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    const monday = new Date(today);
    monday.setDate(today.getDate() + daysToMonday);
    return monday.toISOString().split('T')[0];
  };

  useEffect(() => {
    setWeekStart(getCurrentMonday());
  }, []);

  // Auto-load on component mount and when parameters change
  useEffect(() => {
    const loadMetrics = async () => {
      if (!selectedOffice || !weekStart) {
        return;
      }

      setIsLoading(true);
      setError('');

      console.log(`Loading metrics for ${selectedOffice} week of ${weekStart}`);

      try {
        const params = new URLSearchParams({
          office: selectedOffice,
          week_start: weekStart,
          min_days: minDays
        });

        const response = await fetch(`http://localhost:8081/api/ui/phase7/overview?${params}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Failed to load metrics');
        }

        console.log('Metrics loaded:', data);
        setMetrics(data);
      } catch (err) {
        setError(err.message);
        setMetrics(null);
      } finally {
        setIsLoading(false);
      }
    };

    loadMetrics();
  }, [selectedOffice, weekStart, minDays]);

  const formatWeekRange = () => {
    if (!weekStart) return '';
    const start = new Date(weekStart);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    return `${start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
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

  const [progressStage, setProgressStage] = useState('');

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
      const response = await fetch('http://localhost:8081/api/ui/phase7/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          office: selectedOffice,
          week_start: weekStart,
          seed: 42
        })
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
              <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                Seed: 42
              </span>
              <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                Data: live
              </span>
              <button
                onClick={runOptimizer}
                disabled={isLoading}
                className={`px-6 py-1.5 rounded text-sm font-medium ${
                  isLoading
                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed opacity-50'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {isLoading ? 'Running...' : 'Run Optimizer'}
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
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Budget (2025 Q3)</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-semibold text-gray-900">$38k</span>
                <span className="text-sm text-gray-500">/ $268k (86% used)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex h-full">
        {/* Left Panel - Policy Configuration */}
        <div className="w-80 bg-white border-r p-6 overflow-y-auto">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Policy Configuration</h2>

          <div className="space-y-6">
            {/* Scoring Weights Section */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-4">Scoring Weights</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">Rank Importance</label>
                    <span className="text-sm font-medium">{rankWeight.toFixed(1)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">Low</span>
                    <input
                      type="range"
                      min="0"
                      max="2"
                      step="0.1"
                      value={rankWeight}
                      onChange={(e) => setRankWeight(parseFloat(e.target.value))}
                      className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                    <span className="text-xs text-gray-400">High</span>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">Geographic Match</label>
                    <span className="text-sm font-medium">{geoMatch}</span>
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
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">Publication Rate</label>
                    <span className="text-sm font-medium">{pubRate}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="300"
                    step="10"
                    value={pubRate}
                    onChange={(e) => setPubRate(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">History Bonus</label>
                    <span className="text-sm font-medium">{historyBonus}</span>
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
                </div>
              </div>
            </div>

            {/* Constraint Penalties Section */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-4">Constraint Penalties</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">Tier Cap Penalty</label>
                    <span className="text-sm font-medium">{tierCapPenalty}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1600"
                    step="100"
                    value={tierCapPenalty}
                    onChange={(e) => setTierCapPenalty(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">Fairness Base</label>
                    <span className="text-sm font-medium">{fairnessBase}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="400"
                    step="50"
                    value={fairnessBase}
                    onChange={(e) => setFairnessBase(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">Fairness Step-up</label>
                    <span className="text-sm font-medium">{fairnessStepUp}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="800"
                    step="100"
                    value={fairnessStepUp}
                    onChange={(e) => setFairnessStepUp(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">Budget Penalty (per $)</label>
                    <span className="text-sm font-medium">{budgetPenalty}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    step="1"
                    value={budgetPenalty}
                    onChange={(e) => setBudgetPenalty(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                </div>
              </div>
            </div>

            {/* Hard Constraints Section */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-4">Hard Constraints</h3>
              <div className="space-y-3">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={enforceBudgetHard}
                    onChange={(e) => setEnforceBudgetHard(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-600">Enforce Budget as Hard Constraint</span>
                </label>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm text-gray-600">Cooldown Days</label>
                    <span className="text-sm font-medium">{cooldownDays}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="60"
                    step="5"
                    value={cooldownDays}
                    onChange={(e) => setCooldownDays(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
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
          <p className="text-sm text-gray-500 mb-6">Daily Capacity</p>

          {metrics ? (
            <div>
              {/* Day Tiles Grid */}
              <div className="grid grid-cols-7 gap-3 mb-8">
                {[
                  { key: 'mon', label: 'Mon' },
                  { key: 'tue', label: 'Tue' },
                  { key: 'wed', label: 'Wed' },
                  { key: 'thu', label: 'Thu' },
                  { key: 'fri', label: 'Fri' },
                  { key: 'sat', label: 'Sat' },
                  { key: 'sun', label: 'Sun' }
                ].map((day) => {
                  const capacity = metrics.capacity[day.key];
                  const enabled = (capacity?.slots ?? 0) > 0;

                  const isSelected = selectedDay === day.key;

                  return (
                    <div
                      key={day.key}
                      onClick={() => {
                        // Toggle selection: click same day to unselect, or select new day
                        setSelectedDay(isSelected ? null : day.key);
                      }}
                      className={[
                        "rounded-lg border p-3 text-center transition-all hover:shadow-md",
                        enabled ? "cursor-pointer" : "cursor-not-allowed",
                        isSelected
                          ? "ring-2 ring-blue-500 border-blue-400 bg-blue-50"
                          : enabled
                            ? "border-emerald-200 bg-emerald-50 hover:border-emerald-300"
                            : "border-rose-200 bg-rose-50 hover:border-rose-300"
                      ].join(" ")}
                      title={capacity?.notes || ""}
                    >
                      <div className="text-sm text-slate-500 font-medium">{day.label}</div>
                      <div className={[
                        "text-2xl font-semibold leading-tight mt-1",
                        enabled ? "text-emerald-700" : "text-rose-700"
                      ].join(" ")}>
                        {capacity?.slots ?? 0}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {capacity?.notes ? (
                          capacity.notes === 'blackout' ? 'Blackout' :
                          capacity.notes.includes('Default') ? 'Default' :
                          capacity.notes
                        ) : 'Available'}
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
                        Assignments {selectedDay && `- ${selectedDay.charAt(0).toUpperCase() + selectedDay.slice(1)}`}
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
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">{assignment.vin}</td>
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
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Partners Assigned:</span>
                      <span className="font-medium">{runResult.fairness_summary.partners_assigned}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Max per Partner:</span>
                      <span className="font-medium">{runResult.fairness_summary.max_per_partner}</span>
                    </div>
                    {runResult.fairness_summary.gini && (
                      <div className="text-xs text-gray-500">
                        Distribution Score: {runResult.fairness_summary.gini < 0.2 ? '✓ Balanced' : '⚠ Concentrated'}
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
                  <div className="space-y-2 text-sm">
                    {runResult.budget_summary.fleets && Object.entries(runResult.budget_summary.fleets).map(([fleet, data]) => (
                      <div key={fleet} className="flex justify-between">
                        <span>{fleet}:</span>
                        <span className={data.used > data.budget ? 'text-red-600 font-medium' : 'text-green-600'}>
                          ${data.used?.toLocaleString()} / ${data.budget?.toLocaleString()}
                        </span>
                      </div>
                    ))}
                    {runResult.budget_summary.total && (
                      <div className="border-t pt-1 flex justify-between font-medium">
                        <span>Total:</span>
                        <span>
                          ${runResult.budget_summary.total.used?.toLocaleString()} / ${runResult.budget_summary.total.budget?.toLocaleString()}
                        </span>
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
              <div className="bg-gray-50 rounded p-3 text-sm text-gray-600">
                Will show score components and penalties
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Optimizer;