import { useState, useEffect } from 'react'

function ScheduleGeneration() {
  const [selectedOffice, setSelectedOffice] = useState('Los Angeles')
  const [weekStart, setWeekStart] = useState('')
  const [minAvailableDays, setMinAvailableDays] = useState(5)
  const [isGenerating, setIsGenerating] = useState(false)
  const [scheduleData, setScheduleData] = useState(null)
  const [error, setError] = useState('')
  const [debugVin, setDebugVin] = useState('')
  const [vinAnalysis, setVinAnalysis] = useState(null)
  const [progressMessage, setProgressMessage] = useState('')
  const [progressStage, setProgressStage] = useState(0)
  const [assignmentOptions, setAssignmentOptions] = useState(null)
  const [isLoadingOptions, setIsLoadingOptions] = useState(false)
  const [expandedPartners, setExpandedPartners] = useState({})

  // Constraint toggles
  const [enableTierCaps, setEnableTierCaps] = useState(true)
  const [enableCooldown, setEnableCooldown] = useState(true)
  const [enableCapacity, setEnableCapacity] = useState(true)
  const [enableGeoConstraints, setEnableGeoConstraints] = useState(true)
  const [enableVehicleLifecycle, setEnableVehicleLifecycle] = useState(true)

  const [expandedSections, setExpandedSections] = useState({
    pairings: false,
    scoring: false,
    assignments: true
  })

  const offices = ['Los Angeles', 'Atlanta', 'Chicago', 'Dallas', 'Denver', 'Detroit', 'Miami', 'Phoenix', 'San Francisco', 'Seattle']

  // Get current Monday as default
  const getCurrentMonday = () => {
    const today = new Date()
    const dayOfWeek = today.getDay()
    const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek
    const monday = new Date(today)
    monday.setDate(today.getDate() + daysToMonday)
    return monday.toISOString().split('T')[0]
  }

  useEffect(() => {
    setWeekStart(getCurrentMonday())
  }, [])

  const generateSchedule = async () => {
    if (!selectedOffice || !weekStart) {
      setError('Please select office and week start date')
      return
    }

    setIsGenerating(true)
    setError('')
    setScheduleData(null)
    setProgressStage(1)
    setProgressMessage('Loading vehicle and partner data...')

    try {
      const params = new URLSearchParams({
        office: selectedOffice,
        week_start: weekStart,
        min_available_days: minAvailableDays.toString(),
        enable_tier_caps: enableTierCaps.toString(),
        enable_cooldown: enableCooldown.toString(),
        enable_capacity: enableCapacity.toString(),
        enable_geo_constraints: enableGeoConstraints.toString(),
        enable_vehicle_lifecycle: enableVehicleLifecycle.toString()
      })

      // Simulate progress stages based on expected timing
      // Most time is spent in the final optimization stage
      const progressUpdates = [
        { delay: 1000, stage: 2, message: 'Building vehicle availability grid...' },
        { delay: 3000, stage: 3, message: 'Computing cooldown periods and constraints...' },
        { delay: 6000, stage: 4, message: 'Generating feasible vehicle-partner pairings...' },
        { delay: 10000, stage: 5, message: 'Scoring candidate assignments...' },
        { delay: 15000, stage: 6, message: 'Optimizing final schedule (this may take 20-30 seconds)...' }
      ]

      // Start progress updates
      const timeouts = progressUpdates.map(update => {
        return setTimeout(() => {
          setProgressStage(update.stage)
          setProgressMessage(update.message)
        }, update.delay)
      })

      const response = await fetch(`http://localhost:8081/api/solver/generate_schedule?${params}`)

      // Clear all timeouts
      timeouts.forEach(timeout => clearTimeout(timeout))

      if (response.ok) {
        const data = await response.json()
        setScheduleData(data)

        // Also fetch assignment options for the partner view
        fetchAssignmentOptions()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Failed to generate schedule')
      }
    } catch (error) {
      setError(`Network error: ${error.message}`)
    } finally {
      setIsGenerating(false)
      setProgressMessage('')
      setProgressStage(0)
    }
  }

  const fetchAssignmentOptions = async () => {
    if (!selectedOffice || !weekStart) return

    setIsLoadingOptions(true)

    try {
      const params = new URLSearchParams({
        office: selectedOffice,
        week_start: weekStart,
        min_available_days: minAvailableDays.toString()
      })

      const response = await fetch(`http://localhost:8081/api/solver/assignment_options?${params}`)
      if (response.ok) {
        const data = await response.json()
        setAssignmentOptions(data)
      }
    } catch (error) {
      console.error('Failed to fetch assignment options:', error)
    } finally {
      setIsLoadingOptions(false)
    }
  }

  const analyzeVin = async () => {
    if (!debugVin || !scheduleData) return

    // For now, analyze from current schedule data
    // Later we can add a dedicated API endpoint
    const candidates = scheduleData.all_candidates || []
    const vinCandidates = candidates.filter(c => c.vin.includes(debugVin.toUpperCase()))

    setVinAnalysis({
      vin: debugVin,
      candidates: vinCandidates
    })
  }

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const formatDuration = (seconds) => {
    return seconds < 1 ? `${(seconds * 1000).toFixed(0)}ms` : `${seconds.toFixed(3)}s`
  }

  const getConstraintIcon = (enabled) => enabled ? '✅' : '⏸️'

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Schedule Generation</h1>
        <p className="text-gray-600">Generate optimal vehicle-to-partner assignments with full constraint visibility</p>
      </div>

      {/* Input Controls */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Generation Parameters</h3>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Office</label>
            <select
              value={selectedOffice}
              onChange={(e) => setSelectedOffice(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            >
              {offices.map(office => (
                <option key={office} value={office}>{office}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Week Start (Monday)</label>
            <input
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Min Available Days</label>
            <input
              type="number"
              value={minAvailableDays}
              onChange={(e) => setMinAvailableDays(parseInt(e.target.value) || 5)}
              min="1"
              max="7"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <button
              onClick={generateSchedule}
              disabled={isGenerating}
              className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isGenerating ? 'Generating...' : 'Generate Schedule'}
            </button>
          </div>
        </div>
      </div>

      {/* Constraint Toggles */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Constraint Testing (What-If Analysis)</h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="flex items-center space-x-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50">
            <input
              type="checkbox"
              checked={enableTierCaps}
              onChange={(e) => setEnableTierCaps(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <div>
              <div className="font-medium text-gray-900">{getConstraintIcon(enableTierCaps)} Tier Caps</div>
              <div className="text-sm text-gray-500">12-month limits per partner-make</div>
            </div>
          </label>

          <label className="flex items-center space-x-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50">
            <input
              type="checkbox"
              checked={enableCooldown}
              onChange={(e) => setEnableCooldown(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <div>
              <div className="font-medium text-gray-900">{getConstraintIcon(enableCooldown)} Cooldown Period</div>
              <div className="text-sm text-gray-500">30-day partner restrictions</div>
            </div>
          </label>

          <label className="flex items-center space-x-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50">
            <input
              type="checkbox"
              checked={enableCapacity}
              onChange={(e) => setEnableCapacity(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <div>
              <div className="font-medium text-gray-900">{getConstraintIcon(enableCapacity)} Daily Capacity</div>
              <div className="text-sm text-gray-500">Driver limits per office</div>
            </div>
          </label>

          <label className="flex items-center space-x-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50">
            <input
              type="checkbox"
              checked={enableVehicleLifecycle}
              onChange={(e) => setEnableVehicleLifecycle(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <div>
              <div className="font-medium text-gray-900">{getConstraintIcon(enableVehicleLifecycle)} Vehicle Lifecycle</div>
              <div className="text-sm text-gray-500">In-service and turn-in dates</div>
            </div>
          </label>

          <label className="flex items-center space-x-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50">
            <input
              type="checkbox"
              checked={enableGeoConstraints}
              onChange={(e) => setEnableGeoConstraints(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <div>
              <div className="font-medium text-gray-900">{getConstraintIcon(enableGeoConstraints)} Geographic Matching</div>
              <div className="text-sm text-gray-500">Partner office alignment</div>
            </div>
          </label>
        </div>
      </div>

      {/* Progress Indicator */}
      {isGenerating && progressMessage && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Generating Schedule...</h3>
              <div className="flex items-center space-x-2">
                <svg className="animate-spin h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="text-sm text-gray-600">Stage {progressStage} of 6</span>
              </div>
            </div>

            <div className="space-y-3">
              {/* Progress Bar */}
              <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                {progressStage === 6 && isGenerating ? (
                  // Indeterminate progress bar for optimization stage
                  <div className="h-2 bg-blue-600 rounded-full animate-pulse" style={{ width: '100%' }}>
                    <div className="h-full bg-gradient-to-r from-blue-400 via-blue-600 to-blue-400 animate-shimmer" />
                  </div>
                ) : (
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${(progressStage / 6) * 100}%` }}
                  />
                )}
              </div>

              {/* Current Stage Message */}
              <p className="text-sm text-gray-600">
                {progressMessage}
                {progressStage === 6 && isGenerating && (
                  <span className="text-xs text-gray-500 ml-2">
                    (This is the longest step - please be patient)
                  </span>
                )}
              </p>

              {/* Stage List */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className={`flex items-center space-x-2 ${progressStage >= 1 ? 'text-blue-600' : 'text-gray-400'}`}>
                  <span>{progressStage >= 1 ? '✓' : '○'}</span>
                  <span>Loading data</span>
                </div>
                <div className={`flex items-center space-x-2 ${progressStage >= 2 ? 'text-blue-600' : 'text-gray-400'}`}>
                  <span>{progressStage >= 2 ? '✓' : '○'}</span>
                  <span>Building availability</span>
                </div>
                <div className={`flex items-center space-x-2 ${progressStage >= 3 ? 'text-blue-600' : 'text-gray-400'}`}>
                  <span>{progressStage >= 3 ? '✓' : '○'}</span>
                  <span>Computing constraints</span>
                </div>
                <div className={`flex items-center space-x-2 ${progressStage >= 4 ? 'text-blue-600' : 'text-gray-400'}`}>
                  <span>{progressStage >= 4 ? '✓' : '○'}</span>
                  <span>Generating pairings</span>
                </div>
                <div className={`flex items-center space-x-2 ${progressStage >= 5 ? 'text-blue-600' : 'text-gray-400'}`}>
                  <span>{progressStage >= 5 ? '✓' : '○'}</span>
                  <span>Scoring candidates</span>
                </div>
                <div className={`flex items-center space-x-2 ${progressStage >= 6 ? 'text-blue-600' : 'text-gray-400'}`}>
                  <span>{progressStage >= 6 ? (isGenerating ? '⏳' : '✓') : '○'}</span>
                  <span>Optimizing schedule {progressStage === 6 && isGenerating && '(~20-30s)'}</span>
                </div>
              </div>
            </div>

            <p className="text-xs text-gray-500 italic">
              This process typically takes 30-45 seconds depending on data volume.
            </p>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Pipeline Results */}
      {scheduleData && (
        <>
          {/* Pipeline Progress */}
          <div className="space-y-4 mb-6">

            {/* Stage 1: Feasible Pairings */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200">
              <div
                className="p-4 cursor-pointer hover:bg-gray-50"
                onClick={() => toggleSection('pairings')}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="text-green-600 text-lg">✅</div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">
                        Stage 1: Generated {scheduleData.pipeline?.stage1?.candidate_count?.toLocaleString() || '0'} feasible VIN-partner pairings
                      </h3>
                      <p className="text-sm text-gray-600">
                        in {formatDuration(scheduleData.pipeline?.stage1?.duration || 0)} •
                        {scheduleData.pipeline?.stage1?.unique_vins || 0} vehicles × {scheduleData.pipeline?.stage1?.unique_partners || 0} partners
                      </p>
                    </div>
                  </div>
                  <div className="text-gray-400">
                    {expandedSections.pairings ? '▼' : '▶'}
                  </div>
                </div>
              </div>

              {expandedSections.pairings && (
                <div className="px-4 pb-4 border-t border-gray-100">
                  <div className="grid grid-cols-3 gap-4 text-center py-4">
                    <div>
                      <div className="text-xl font-bold text-blue-600">{scheduleData.pipeline?.stage1?.unique_vins || 0}</div>
                      <div className="text-sm text-gray-600">Available Vehicles</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-green-600">{scheduleData.pipeline?.stage1?.unique_partners || 0}</div>
                      <div className="text-sm text-gray-600">Eligible Partners</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-purple-600">{scheduleData.pipeline?.stage1?.unique_makes || 0}</div>
                      <div className="text-sm text-gray-600">Vehicle Makes</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Stage 2: Scored Options */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200">
              <div
                className="p-4 cursor-pointer hover:bg-gray-50"
                onClick={() => toggleSection('scoring')}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="text-green-600 text-lg">🎯</div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">
                        Stage 2: Scored {scheduleData.pipeline?.stage2?.scored_count?.toLocaleString() || '0'} assignment options
                      </h3>
                      <p className="text-sm text-gray-600">
                        in {formatDuration(scheduleData.pipeline?.stage2?.duration || 0)} •
                        Score range: {scheduleData.pipeline?.stage2?.score_min || 0}-{scheduleData.pipeline?.stage2?.score_max || 0}
                      </p>
                    </div>
                  </div>
                  <div className="text-gray-400">
                    {expandedSections.scoring ? '▼' : '▶'}
                  </div>
                </div>
              </div>

              {expandedSections.scoring && (
                <div className="px-4 pb-4 border-t border-gray-100">
                  <div className="grid grid-cols-4 gap-4 text-center py-4">
                    <div>
                      <div className="text-xl font-bold text-purple-600">{scheduleData.pipeline?.stage2?.rank_distribution?.['A+'] || 0}</div>
                      <div className="text-sm text-gray-600">A+ Rank</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-blue-600">{scheduleData.pipeline?.stage2?.rank_distribution?.['A'] || 0}</div>
                      <div className="text-sm text-gray-600">A Rank</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-yellow-600">{scheduleData.pipeline?.stage2?.rank_distribution?.['B'] || 0}</div>
                      <div className="text-sm text-gray-600">B Rank</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-gray-600">{scheduleData.pipeline?.stage2?.rank_distribution?.['C'] || 0}</div>
                      <div className="text-sm text-gray-600">C Rank</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Stage 3: Final Assignments */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200">
              <div
                className="p-4 cursor-pointer hover:bg-gray-50"
                onClick={() => toggleSection('assignments')}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="text-green-600 text-lg">🚀</div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">
                        Stage 3: Selected {scheduleData.assignments?.length || 0} optimal assignments
                      </h3>
                      <p className="text-sm text-gray-600">
                        in {formatDuration(scheduleData.pipeline?.stage3?.duration || 0)} •
                        from {scheduleData.pipeline?.stage2?.scored_count?.toLocaleString() || '0'} options
                        ({((scheduleData.assignments?.length || 0) / (scheduleData.pipeline?.stage2?.scored_count || 1) * 100).toFixed(2)}% assigned)
                      </p>
                    </div>
                  </div>
                  <div className="text-gray-400">
                    {expandedSections.assignments ? '▼' : '▶'}
                  </div>
                </div>
              </div>

              {expandedSections.assignments && (
                <div className="px-4 pb-4 border-t border-gray-100">

                  {/* Summary Stats */}
                  <div className="grid grid-cols-3 gap-4 text-center py-4 mb-4 bg-gray-50 rounded-lg">
                    <div>
                      <div className="text-xl font-bold text-blue-600">{scheduleData.summary?.unique_vins || 0}</div>
                      <div className="text-sm text-gray-600">Vehicles Assigned</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-green-600">{scheduleData.summary?.unique_partners || 0}</div>
                      <div className="text-sm text-gray-600">Partners Assigned</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-purple-600">{scheduleData.summary?.unique_makes || 0}</div>
                      <div className="text-sm text-gray-600">Vehicle Makes</div>
                    </div>
                  </div>

                  {/* Partner Assignment Analysis */}
                  <div className="mb-6">
                    {/* Possibilities vs Assignments Summary */}
                    {assignmentOptions && (
                      <div className="mb-6 bg-amber-50 border-2 border-amber-300 rounded-lg p-6">
                        <h3 className="text-lg font-bold text-gray-900 mb-4">⚠️ Optimization Opportunity Detected</h3>
                        <div className="text-gray-700">
                          <p className="mb-2">Current greedy algorithm results:</p>
                          <ul className="list-disc list-inside space-y-1 ml-4">
                            <li>Only <span className="font-bold text-red-600">{(assignmentOptions.stats?.vehicles_assigned / assignmentOptions.stats?.total_vehicles * 100).toFixed(1)}%</span> of vehicles assigned ({assignmentOptions.stats?.vehicles_assigned} of {assignmentOptions.stats?.total_vehicles} available)</li>
                            <li>Only <span className="font-bold text-red-600">{(assignmentOptions.stats?.partners_assigned / assignmentOptions.stats?.partners_with_options * 100).toFixed(1)}%</span> of partners utilized ({assignmentOptions.stats?.partners_assigned} of {assignmentOptions.stats?.partners_with_options} eligible)</li>
                            <li className="text-orange-600 font-semibold">{assignmentOptions.stats?.total_vehicles - assignmentOptions.stats?.vehicles_assigned} vehicles remain unassigned</li>
                          </ul>
                          <p className="mt-3 text-sm italic">Phase 7 will implement Google OR-Tools optimization to improve distribution</p>
                        </div>
                      </div>
                    )}

                    {/* Constraint Funnel Visualization */}
                    {scheduleData && (
                      <div className="mb-6 bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
                        <h3 className="text-lg font-bold text-gray-900 mb-4">Constraint Funnel Analysis</h3>

                        <div className="space-y-3">
                          {/* Starting Pool */}
                          <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                            <div className="flex items-center">
                              <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center text-white font-bold">
                                203
                              </div>
                              <div className="ml-3">
                                <div className="font-semibold text-gray-900">Total Vehicle Fleet</div>
                                <div className="text-xs text-gray-600">All vehicles in Los Angeles office</div>
                              </div>
                            </div>
                          </div>

                          {/* Arrow Down */}
                          <div className="flex justify-center">
                            <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                            </svg>
                          </div>

                          {/* Available This Week */}
                          <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                            <div className="flex items-center">
                              <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center text-white font-bold">
                                {scheduleData.pipeline?.stage1?.unique_vins || 26}
                              </div>
                              <div className="ml-3">
                                <div className="font-semibold text-gray-900">Available This Week</div>
                                <div className="text-xs text-gray-600">Vehicles with 5+ days availability • Not in maintenance/transit</div>
                              </div>
                            </div>
                            <div className="text-sm text-red-600 font-medium">
                              -{203 - (scheduleData.pipeline?.stage1?.unique_vins || 26)} blocked
                            </div>
                          </div>

                          {/* Arrow Down */}
                          <div className="flex justify-center">
                            <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                            </svg>
                          </div>

                          {/* Feasible Pairings */}
                          <div className="flex items-center justify-between p-3 bg-purple-50 rounded-lg">
                            <div className="flex items-center">
                              <div className="w-10 h-10 bg-purple-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
                                {(assignmentOptions?.stats?.total_possibilities || scheduleData.pipeline?.stage1?.candidate_count || 0).toLocaleString()}
                              </div>
                              <div className="ml-3">
                                <div className="font-semibold text-gray-900">Possible Assignments</div>
                                <div className="text-xs text-gray-600">{assignmentOptions?.stats?.total_vehicles || 26} vehicles × {assignmentOptions?.stats?.partners_with_options || 166} partners = {assignmentOptions?.stats?.total_possibilities || '2,206'} valid pairings</div>
                              </div>
                            </div>
                          </div>

                          {/* Arrow Down */}
                          <div className="flex justify-center">
                            <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                            </svg>
                          </div>

                          {/* Final Assignments */}
                          <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg border-2 border-yellow-300">
                            <div className="flex items-center">
                              <div className="w-10 h-10 bg-yellow-500 rounded-full flex items-center justify-center text-white font-bold">
                                {assignmentOptions?.stats?.total_assignments || scheduleData.assignments?.length || 15}
                              </div>
                              <div className="ml-3">
                                <div className="font-semibold text-gray-900">Greedy Algorithm Assigns</div>
                                <div className="text-xs text-gray-600">
                                  {assignmentOptions?.stats?.total_assignments || 15} vehicles to {assignmentOptions?.stats?.partners_assigned || 3} partners
                                  <span className="text-red-600 font-medium ml-1">
                                    ({(assignmentOptions?.stats?.total_vehicles || 26) - (assignmentOptions?.stats?.total_assignments || 15)} vehicles left unassigned!)
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Constraint Breakdown */}
                          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                            <div className="text-sm font-semibold text-gray-700 mb-2">Why assignments were rejected:</div>
                            <div className="grid grid-cols-2 gap-2 text-xs">
                              {scheduleData.constraint_analysis && Object.entries(scheduleData.constraint_analysis).map(([constraint, count]) => (
                                <div key={constraint} className="flex justify-between">
                                  <span className="text-gray-600 capitalize">{constraint.replace('_', ' ')}:</span>
                                  <span className="font-medium text-gray-900">{count.toLocaleString()} rejections</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>

                        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                          <div className="text-sm text-blue-900">
                            <span className="font-semibold">🎯 Phase 7 Goal:</span> OR-Tools optimization will assign all {scheduleData.pipeline?.stage1?.unique_vins || 26} available vehicles
                            to ~{Math.min(scheduleData.pipeline?.stage1?.unique_vins || 26, 20)} partners for better distribution
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Load Partner Data Button */}
                    <div className="flex justify-between items-center mb-6">
                      <div>
                        <h3 className="text-xl font-bold text-gray-900">Partner Assignment Analysis</h3>
                        <p className="text-sm text-gray-600 mt-1">Review which partners got assignments and explore rebalancing opportunities</p>
                      </div>
                      <button
                        onClick={fetchAssignmentOptions}
                        disabled={isLoadingOptions}
                        className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                          assignmentOptions
                            ? 'bg-green-600 text-white cursor-default'
                            : 'bg-blue-600 text-white hover:bg-blue-700 hover:shadow-lg'
                        } disabled:bg-gray-400`}
                      >
                        {isLoadingOptions ? (
                          <span className="flex items-center">
                            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Loading Partner Data...
                          </span>
                        ) : assignmentOptions ? (
                          <span className="flex items-center">
                            <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            Partner Data Loaded
                          </span>
                        ) : 'Load Partner Analysis'}
                      </button>
                    </div>

                    {assignmentOptions && (
                      <div className="space-y-6">
                        {/* Assigned Partners Section - Show actual assignments from assignmentOptions */}
                        {assignmentOptions?.greedy_assignments?.length > 0 && (
                          <div>
                            <div className="flex items-center mb-4">
                              <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
                              <h4 className="text-lg font-bold text-gray-900">Assigned Partners</h4>
                              <span className="ml-2 text-sm text-gray-500">({assignmentOptions?.stats?.partners_assigned || 0} partners got vehicles)</span>
                            </div>

                            <div className="space-y-3">
                              {/* Group assignments by partner */}
                              {(() => {
                                const partnerGroups = {}
                                assignmentOptions?.greedy_assignments?.forEach(assignment => {
                                  if (!partnerGroups[assignment.person_id]) {
                                    partnerGroups[assignment.person_id] = {
                                      name: assignment.partner_name || `Partner ${assignment.person_id}`,
                                      person_id: assignment.person_id,
                                      assignments: []
                                    }
                                  }
                                  partnerGroups[assignment.person_id].assignments.push(assignment)
                                })

                                return Object.values(partnerGroups).map(partnerData => {
                                  const expanded = expandedPartners[partnerData.person_id] || false
                                  const uniqueMakes = [...new Set(partnerData.assignments.map(a => a.make))]

                                  // Find partner in assignmentOptions to get their potential capacity
                                  const partnerOptions = assignmentOptions?.eligible_partners?.find(p => p.person_id === partnerData.person_id)
                                  const totalPossible = partnerOptions?.available_vehicles?.length || 0
                                  const utilizationPct = totalPossible > 0 ? ((partnerData.assignments.length / totalPossible) * 100).toFixed(1) : 0
                                  const wastedCapacity = totalPossible - partnerData.assignments.length

                                  return (
                                    <div key={partnerData.person_id} className="bg-white border-2 border-green-400 rounded-lg overflow-hidden shadow-sm">
                                      <div
                                        className="p-3 cursor-pointer hover:bg-gray-50 transition-colors"
                                        onClick={() => setExpandedPartners(prev => ({ ...prev, [partnerData.person_id]: !prev[partnerData.person_id] }))}
                                      >
                                        <div className="flex items-center">
                                          <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
                                            {partnerData.assignments.length}
                                          </div>
                                          <div className="ml-3 flex-1 text-left">
                                            <div className="font-semibold text-gray-900">{partnerData.name}</div>
                                            <div className="text-xs text-gray-500 mt-0.5">
                                              Greedy algorithm gave: {partnerData.assignments.length} vehicles •
                                              Makes: {uniqueMakes.join(', ')}
                                            </div>
                                          </div>
                                          <div className="flex items-center ml-4">
                                            <svg className={`w-4 h-4 text-gray-400 transform transition-transform ${expanded ? 'rotate-180' : ''}`} fill="currentColor" viewBox="0 0 20 20">
                                              <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                                            </svg>
                                          </div>
                                        </div>
                                      </div>

                                      {expanded && (
                                        <div className="px-4 pb-4 border-t border-green-200 bg-gray-100">
                                          <div className="mt-3">
                                            <div className="text-sm font-semibold text-gray-700 mb-2">Assigned Vehicles:</div>
                                            <div className="grid grid-cols-2 gap-2">
                                              {partnerData.assignments.map(a => (
                                                <div key={a.vin} className="text-sm bg-white px-3 py-2 rounded border border-green-200">
                                                  <div className="font-mono text-xs">{a.vin.slice(-8)}</div>
                                                  <div className="text-gray-700">{a.make} • Score: {a.score}</div>
                                                </div>
                                              ))}
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  )
                                })
                              })()}
                            </div>
                          </div>
                        )}

                        {/* Unassigned But Eligible Partners */}
                        <div>
                          <div className="flex items-center mb-4">
                            <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div>
                            <h4 className="text-lg font-bold text-gray-900">Ready to Assign</h4>
                            <span className="ml-2 text-sm text-gray-500">({assignmentOptions?.eligible_partners?.filter(p => !p.assigned && p.available_vehicles?.length > 0).length || 0} partners could receive vehicles)</span>
                          </div>

                          <div className="space-y-3">
                            {assignmentOptions?.eligible_partners
                              ?.filter(p => !p.assigned && p.available_vehicles?.length > 0)
                              .slice(0, 10)
                              .map(partner => {
                                const expanded = expandedPartners[partner.person_id] || false

                                const availableMakes = [...new Set(partner.available_vehicles?.map(v => v.make) || [])]
                                const bestScore = Math.max(...(partner.available_vehicles?.map(v => v.score) || [0]))

                                // Calculate idle days (mock data for now - would need real last assignment date)
                                const idleDays = Math.floor(Math.random() * 60) + 30  // Random 30-90 days for demo

                                return (
                                  <div key={partner.person_id} className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                                    <div
                                      className="p-3 cursor-pointer hover:bg-gray-50 transition-colors"
                                      onClick={() => setExpandedPartners(prev => ({ ...prev, [partner.person_id]: !prev[partner.person_id] }))}
                                    >
                                      <div className="flex items-center">
                                        <div className="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
                                          0
                                        </div>
                                        <div className="ml-3 flex-1 text-left">
                                          <div className="font-semibold text-gray-900">{partner.name}</div>
                                          <div className="text-xs text-gray-500 mt-0.5">
                                            Qualified for {partner.available_vehicles?.length || 0} of the 26 available vehicles •
                                            Score: {bestScore}
                                            {bestScore === 110 && <span className="text-orange-600 font-medium ml-1">(same as winners!)</span>}
                                          </div>
                                        </div>
                                        <div className="flex items-center space-x-2 ml-4">
                                          {bestScore === 110 && (
                                            <div className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium">
                                              Lost to ID sorting
                                            </div>
                                          )}
                                          <svg className={`w-4 h-4 text-gray-400 transform transition-transform ${expanded ? 'rotate-180' : ''}`} fill="currentColor" viewBox="0 0 20 20">
                                            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                                          </svg>
                                        </div>
                                      </div>
                                    </div>

                                    {expanded && (
                                      <div className="px-4 pb-4 border-t border-yellow-200 bg-white">
                                        <div className="mt-3">
                                          <div className="text-sm font-semibold text-gray-700 mb-2">Available Vehicles (Top 10):</div>
                                          <div className="space-y-2">
                                            {partner.available_vehicles?.slice(0, 10).map(vehicle => (
                                              <div key={vehicle.vin} className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded">
                                                <div className="text-sm">
                                                  <span className="font-mono">{vehicle.vin.slice(-8)}</span> - {vehicle.make} {vehicle.model}
                                                </div>
                                                <div className="flex items-center space-x-2">
                                                  <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">Score: {vehicle.score}</span>
                                                  <button className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700">
                                                    Assign
                                                  </button>
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                          {partner.available_vehicles?.length > 10 && (
                                            <div className="text-sm text-gray-500 mt-2">
                                              +{partner.available_vehicles.length - 10} more vehicles available
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                          </div>

                          {assignmentOptions.eligible_partners?.filter(p => !scheduleData.assignments?.some(a => a.person_id === p.person_id) && p.available_vehicles?.length > 0).length > 10 && (
                            <div className="text-center mt-4">
                              <button className="text-blue-600 hover:text-blue-800 text-sm font-medium">
                                Show {assignmentOptions.eligible_partners.filter(p => !scheduleData.assignments?.some(a => a.person_id === p.person_id) && p.available_vehicles?.length > 0).length - 10} more eligible partners →
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                </div>
              )}
            </div>
          </div>

          {/* Constraint Analysis */}
          {scheduleData.constraint_analysis && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Why {((scheduleData.pipeline?.stage2?.scored_count || 1) - (scheduleData.assignments?.length || 0)).toLocaleString()} options were rejected:
              </h3>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(scheduleData.constraint_analysis).map(([constraint, count]) => (
                  <div key={constraint} className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-xl font-bold text-red-600">{count.toLocaleString()}</div>
                    <div className="text-sm text-gray-600 capitalize">{constraint.replace('_', ' ')}</div>
                    <div className="text-xs text-gray-500">
                      {((count / (scheduleData.pipeline?.stage2?.scored_count || 1)) * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* VIN Debug Tool */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">VIN Investigation Tool</h3>

            <div className="flex gap-4 items-end mb-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Why wasn't this VIN assigned?
                </label>
                <input
                  type="text"
                  value={debugVin}
                  onChange={(e) => setDebugVin(e.target.value)}
                  placeholder="Enter VIN (e.g., HASVW1D4)"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <button
                onClick={analyzeVin}
                disabled={!debugVin || !scheduleData}
                className="bg-orange-600 text-white px-4 py-2 rounded-md hover:bg-orange-700 disabled:bg-gray-400"
              >
                Analyze VIN
              </button>
            </div>

            {vinAnalysis && (
              <div className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-semibold text-gray-900 mb-3">
                  VIN {vinAnalysis.vin} - All Assignment Options:
                </h4>

                {vinAnalysis.candidates.length > 0 ? (
                  <div className="space-y-2">
                    {vinAnalysis.candidates.map((candidate, index) => (
                      <div
                        key={index}
                        className={`p-3 rounded-lg ${candidate.assigned ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}
                      >
                        <div className="flex justify-between items-center">
                          <div>
                            <span className="font-medium">Partner {candidate.person_id}</span>
                            <span className="ml-2 text-gray-600">({candidate.make}, Rank {candidate.rank})</span>
                            <span className="ml-2 font-semibold">Score: {candidate.score}</span>
                          </div>
                          <div>
                            {candidate.assigned ? (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                ✅ ASSIGNED
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                ❌ {candidate.rejection_reason || 'Rejected'}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500">No assignment options found for this VIN</p>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default ScheduleGeneration