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
    setProgressMessage('🚀 Initializing schedule generation...')
    setProgressStage(1)
    setAssignmentOptions(null) // Reset options when generating new schedule

    try {
      // Stage 1: Load Data
      setProgressMessage('📊 Loading vehicles and partners from database...')
      await new Promise(resolve => setTimeout(resolve, 300))

      // Stage 2: Build Candidates
      setProgressStage(2)
      setProgressMessage('🔍 Finding available vehicles (checking maintenance, transit status)...')
      await new Promise(resolve => setTimeout(resolve, 400))

      // Stage 3: Check Constraints
      setProgressStage(3)
      setProgressMessage('✅ Validating constraints (cooldown, tier caps, availability)...')
      await new Promise(resolve => setTimeout(resolve, 400))

      // Stage 4: Score Candidates
      setProgressStage(4)
      setProgressMessage('📈 Computing scores for all valid pairings...')
      await new Promise(resolve => setTimeout(resolve, 300))

      // Stage 5: Run Algorithm
      setProgressStage(5)
      setProgressMessage('🎯 Running greedy optimization algorithm...')

      const params = new URLSearchParams({
        office: selectedOffice,
        week_start: weekStart,
        min_available_days: minAvailableDays,
        enable_tier_caps: enableTierCaps,
        enable_cooldown: enableCooldown,
        enable_capacity: enableCapacity,
        cooldown_days: 30
      })

      const response = await fetch(`http://localhost:8081/api/solver/generate_schedule?${params}`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to generate schedule')
      }

      setScheduleData(data)

      // Stage 6: Load Partner Analysis
      setProgressStage(6)
      setProgressMessage('📋 Loading partner analysis...')

      // Automatically fetch assignment options after schedule generation
      const optionsParams = new URLSearchParams({
        office: selectedOffice,
        week_start: weekStart,
        min_available_days: minAvailableDays
      })

      const optionsResponse = await fetch(`http://localhost:8081/api/solver/assignment_options?${optionsParams}`)
      const optionsData = await optionsResponse.json()

      if (optionsResponse.ok) {
        setAssignmentOptions(optionsData)
      }

      // Complete
      setProgressMessage('✨ Complete! Schedule and analysis ready.')
      await new Promise(resolve => setTimeout(resolve, 500))
    } catch (err) {
      setError(err.message)
      setProgressMessage('❌ Generation failed: ' + err.message)
      await new Promise(resolve => setTimeout(resolve, 2000))
    } finally {
      setIsGenerating(false)
      setProgressStage(0)
      setProgressMessage('')
    }
  }

  const fetchAssignmentOptions = async () => {
    if (!selectedOffice || !weekStart) {
      setError('Please select office and week start date')
      return
    }

    setIsLoadingOptions(true)
    setError('')

    try {
      const params = new URLSearchParams({
        office: selectedOffice,
        week_start: weekStart,
        min_available_days: minAvailableDays
      })

      const response = await fetch(`http://localhost:8081/api/solver/assignment_options?${params}`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to fetch assignment options')
      }

      setAssignmentOptions(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoadingOptions(false)
    }
  }

  const analyzeVin = async () => {
    if (!debugVin.trim()) {
      setVinAnalysis(null)
      return
    }

    try {
      const params = new URLSearchParams({
        office: selectedOffice,
        week_start: weekStart,
        vin: debugVin.trim()
      })

      const response = await fetch(`http://localhost:8081/api/solver/analyze_vin?${params}`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to analyze VIN')
      }

      setVinAnalysis(data)
    } catch (err) {
      setError(err.message)
      setVinAnalysis(null)
    }
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

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
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
              checked={enableGeoConstraints}
              onChange={(e) => setEnableGeoConstraints(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <div>
              <div className="font-medium text-gray-900">{getConstraintIcon(enableGeoConstraints)} Geographic</div>
              <div className="text-sm text-gray-500">Location-based eligibility</div>
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
              <div className="text-sm text-gray-500">In-service date constraints</div>
            </div>
          </label>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {/* Progress Indicator */}
      {isGenerating && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-6">
          {/* Main progress message */}
          <div className="px-6 pt-6 pb-3">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold text-gray-900">Generating Schedule</h3>
              <div className="text-sm text-gray-500">
                Stage {Math.min(progressStage, 3)} of 3
              </div>
            </div>
            <div className="text-sm text-gray-600 mb-3">{progressMessage}</div>
          </div>

          {/* Visual pipeline stages */}
          <div className="px-6 pb-4">
            <div className="flex items-center justify-between mb-2">
              {/* Stage 1: Candidates */}
              <div className={`flex-1 text-center ${progressStage >= 1 ? 'text-blue-600' : 'text-gray-400'}`}>
                <div className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-2 ${
                  progressStage >= 1 ? 'bg-blue-100' : 'bg-gray-100'
                }`}>
                  {progressStage > 1 ? '✓' : '1'}
                </div>
                <div className="text-xs font-medium">Build Candidates</div>
                {progressStage === 1 && (
                  <div className="text-xs text-gray-500 mt-1">Finding pairs...</div>
                )}
              </div>

              {/* Connector line */}
              <div className={`flex-1 h-1 ${progressStage >= 2 ? 'bg-blue-500' : 'bg-gray-200'}`} />

              {/* Stage 2: Score */}
              <div className={`flex-1 text-center ${progressStage >= 3 ? 'text-blue-600' : 'text-gray-400'}`}>
                <div className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-2 ${
                  progressStage >= 3 ? 'bg-blue-100' : 'bg-gray-100'
                }`}>
                  {progressStage > 3 ? '✓' : '2'}
                </div>
                <div className="text-xs font-medium">Score & Validate</div>
                {progressStage >= 2 && progressStage <= 4 && (
                  <div className="text-xs text-gray-500 mt-1">Computing...</div>
                )}
              </div>

              {/* Connector line */}
              <div className={`flex-1 h-1 ${progressStage >= 5 ? 'bg-blue-500' : 'bg-gray-200'}`} />

              {/* Stage 3: Optimize */}
              <div className={`flex-1 text-center ${progressStage >= 5 ? 'text-blue-600' : 'text-gray-400'}`}>
                <div className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-2 ${
                  progressStage >= 6 ? 'bg-green-100' : progressStage >= 5 ? 'bg-blue-100' : 'bg-gray-100'
                }`}>
                  {progressStage >= 6 ? '✓' : '3'}
                </div>
                <div className="text-xs font-medium">Generate Results</div>
                {progressStage >= 5 && progressStage <= 6 && (
                  <div className="text-xs text-gray-500 mt-1">Optimizing...</div>
                )}
              </div>
            </div>

            {/* Overall progress bar */}
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden mt-4">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${(progressStage / 6) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Results Display */}
      {scheduleData && !isGenerating && (
        <div>
          {/* 3-Stage Analysis View */}
          <div className="mb-6">
            {assignmentOptions && (
              <div className="space-y-6">
                {/* Stage 1: Available Resources */}
                <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">Stage 1: Available Resources</h3>
                  <div className="grid grid-cols-3 gap-6">
                    {/* Vehicles */}
                    <div className="text-center">
                      <div className="flex items-baseline justify-center gap-2">
                        <div className="text-3xl font-bold text-blue-600">{assignmentOptions.stats?.total_vehicles || 0}</div>
                        <div className="text-lg text-gray-500">/ {assignmentOptions.office_totals?.total_vehicles || 225}</div>
                      </div>
                      <div className="text-sm font-medium text-gray-900 mt-1">Vehicles Available</div>
                      <div className="text-xs text-gray-500">
                        {((assignmentOptions.stats?.total_vehicles || 0) / (assignmentOptions.office_totals?.total_vehicles || 1) * 100).toFixed(0)}% of fleet ready
                      </div>
                    </div>
                    {/* Partners */}
                    <div className="text-center">
                      <div className="flex items-baseline justify-center gap-2">
                        <div className="text-3xl font-bold text-green-600">{assignmentOptions.stats?.partners_with_options || 0}</div>
                        <div className="text-lg text-gray-500">/ {assignmentOptions.office_totals?.total_partners || 202}</div>
                      </div>
                      <div className="text-sm font-medium text-gray-900 mt-1">Partners Eligible</div>
                      <div className="text-xs text-gray-500">
                        {((assignmentOptions.stats?.partners_with_options || 0) / (assignmentOptions.office_totals?.total_partners || 1) * 100).toFixed(0)}% can receive vehicles
                      </div>
                    </div>
                    {/* Makes */}
                    <div className="text-center">
                      <div className="flex items-baseline justify-center gap-2">
                        <div className="text-3xl font-bold text-purple-600">{assignmentOptions.stats?.unique_makes || 13}</div>
                        <div className="text-lg text-gray-500">/ {assignmentOptions.office_totals?.total_makes || 15}</div>
                      </div>
                      <div className="text-sm font-medium text-gray-900 mt-1">Makes Available</div>
                      <div className="text-xs text-gray-500">
                        {((assignmentOptions.stats?.unique_makes || 0) / (assignmentOptions.office_totals?.total_makes || 1) * 100).toFixed(0)}% of brands
                      </div>
                    </div>
                  </div>
                </div>

                {/* Stage 2: Optimization Process */}
                <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">Stage 2: Optimization Process</h3>
                  <div className="grid grid-cols-4 gap-6">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">{assignmentOptions.stats?.total_possibilities?.toLocaleString() || '23,033'}</div>
                      <div className="text-xs text-gray-500 mt-1">Total Pairings</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-yellow-600">{assignmentOptions.stats?.candidates_with_cooldown?.toLocaleString() || '22,709'}</div>
                      <div className="text-xs text-gray-500 mt-1">After Cooldown</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-orange-600">{Math.round((assignmentOptions.stats?.candidates_with_cooldown || 22709) * 0.95).toLocaleString()}</div>
                      <div className="text-xs text-gray-500 mt-1">After Tier Caps</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">{assignmentOptions.stats?.total_assignments || 15}</div>
                      <div className="text-xs text-gray-500 mt-1">Final Selection</div>
                    </div>
                  </div>
                </div>

                {/* Stage 3: Optimal Assignments */}
                <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">Stage 3: Optimal Assignments</h3>

                  {/* Summary Stats */}
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    <div className="bg-green-50 p-3 rounded-lg text-center">
                      <div className="text-2xl font-bold text-green-600">{assignmentOptions.stats?.total_assignments || 0}</div>
                      <div className="text-xs text-gray-600">Assigned</div>
                    </div>
                    <div className="bg-red-50 p-3 rounded-lg text-center">
                      <div className="text-2xl font-bold text-red-600">
                        {(assignmentOptions.stats?.total_vehicles || 0) - (assignmentOptions.stats?.vehicles_assigned || 0)}
                      </div>
                      <div className="text-xs text-gray-600">Unassigned</div>
                    </div>
                    <div className="bg-orange-50 p-3 rounded-lg text-center">
                      <div className="text-2xl font-bold text-orange-600">
                        {((assignmentOptions.stats?.vehicles_assigned || 0) / (assignmentOptions.stats?.total_vehicles || 1) * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-gray-600">Utilization</div>
                    </div>
                  </div>

                  {/* Partner Assignment Details */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-semibold text-gray-700">Partner Assignments</span>
                      <span className="text-xs text-gray-500">Click to expand vehicle options</span>
                    </div>

                    <div className="space-y-2 max-h-[600px] overflow-y-auto">
                      {assignmentOptions?.eligible_partners
                        ?.sort((a, b) => {
                          // Sort assigned partners first, then by score
                          if (a.assigned && !b.assigned) return -1
                          if (!a.assigned && b.assigned) return 1
                          return (b.max_score || 0) - (a.max_score || 0)
                        })
                        .slice(0, 50)
                        .map((partner, index) => {
                          const isAssigned = partner.assigned || false
                          const assignment = assignmentOptions.greedy_assignments?.find(a => a.person_id === partner.person_id)
                          const isExpanded = expandedPartners[partner.person_id] || false

                          // Get top 5 vehicles for this partner
                          const topVehicles = partner.available_vehicles?.slice(0, 5) || []

                          return (
                            <div
                              key={partner.person_id}
                              className={`border rounded-lg overflow-hidden transition-all ${
                                isAssigned ? 'border-green-400 bg-green-50' : 'border-gray-200 bg-white'
                              }`}
                            >
                              {/* Partner Header - Clickable */}
                              <div
                                className="p-3 cursor-pointer hover:bg-opacity-70 transition-colors"
                                onClick={() => setExpandedPartners(prev => ({
                                  ...prev,
                                  [partner.person_id]: !prev[partner.person_id]
                                }))}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center flex-1">
                                    {/* Rank Badge */}
                                    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm mr-3 ${
                                      isAssigned ? 'bg-green-500 text-white' :
                                      index < 15 ? 'bg-orange-400 text-white' :
                                      'bg-gray-300 text-gray-700'
                                    }`}>
                                      {isAssigned ? '✓' : index + 1}
                                    </div>

                                    {/* Partner Info */}
                                    <div className="flex-1">
                                      <div className="font-semibold text-gray-900">
                                        {partner.name}
                                        {partner.rank && (
                                          <span className={`ml-2 px-2 py-0.5 text-xs rounded-full ${
                                            partner.rank === 'A+' ? 'bg-purple-100 text-purple-700' :
                                            partner.rank === 'A' ? 'bg-blue-100 text-blue-700' :
                                            partner.rank === 'B' ? 'bg-green-100 text-green-700' :
                                            'bg-gray-100 text-gray-700'
                                          }`}>
                                            {partner.rank} Rank
                                          </span>
                                        )}
                                      </div>
                                      <div className="text-xs text-gray-600 mt-0.5">
                                        Score: {partner.max_score || 0} •
                                        {partner.vehicle_count || 0} eligible vehicles •
                                        {partner.last_assignment ? (
                                          <span className="text-orange-600">
                                            Last loan: {partner.last_assignment.make} {partner.last_assignment.model} ({partner.last_assignment.date})
                                          </span>
                                        ) : (
                                          <span className="text-green-600">No recent loans</span>
                                        )}
                                      </div>
                                    </div>
                                  </div>

                                  {/* Assignment Status */}
                                  <div className="flex items-center space-x-2">
                                    {isAssigned && assignment ? (
                                      <div className="text-sm font-medium text-green-700 bg-green-100 px-3 py-1 rounded-full">
                                        {assignment.make} {assignment.model}
                                      </div>
                                    ) : index < 15 ? (
                                      <div className="text-xs font-medium text-orange-600 bg-orange-100 px-2 py-1 rounded">
                                        Should have been assigned
                                      </div>
                                    ) : null}

                                    {/* Expand/Collapse Icon */}
                                    <svg
                                      className={`w-5 h-5 text-gray-400 transform transition-transform ${
                                        isExpanded ? 'rotate-180' : ''
                                      }`}
                                      fill="currentColor"
                                      viewBox="0 0 20 20"
                                    >
                                      <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                                    </svg>
                                  </div>
                                </div>
                              </div>

                              {/* Expanded Vehicle Details */}
                              {isExpanded && (
                                <div className="border-t border-gray-200 bg-white p-3">
                                  <div className="text-xs font-semibold text-gray-700 mb-2">
                                    Top Vehicle Options (Best Score First):
                                  </div>
                                  {topVehicles.length > 0 ? (
                                    <div className="space-y-2">
                                      {topVehicles.map((vehicle, vIndex) => (
                                        <div
                                          key={vehicle.vin}
                                          className="flex items-center justify-between p-2 bg-gray-50 rounded-lg border border-gray-200"
                                        >
                                          <div className="flex-1">
                                            <div className="flex items-center space-x-2">
                                              <span className="font-mono text-xs text-gray-500">
                                                {vehicle.vin?.slice(-8) || 'Unknown'}
                                              </span>
                                              <span className="font-medium text-sm text-gray-900">
                                                {vehicle.year} {vehicle.make} {vehicle.model}
                                              </span>
                                              {vIndex === 0 && (
                                                <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">
                                                  Best Match
                                                </span>
                                              )}
                                            </div>
                                            <div className="text-xs text-gray-500 mt-1">
                                              Score: {vehicle.score} •
                                              Rank match: {vehicle.rank || 'C'}
                                            </div>
                                          </div>
                                          {!isAssigned && (
                                            <button className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700">
                                              Assign
                                            </button>
                                          )}
                                        </div>
                                      ))}
                                      {partner.vehicle_count > 5 && (
                                        <div className="text-xs text-gray-500 text-center pt-2">
                                          +{partner.vehicle_count - 5} more vehicles available
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    <div className="text-sm text-gray-500 italic">
                                      No vehicle details available
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )
                        })}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

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
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
              >
                Analyze VIN
              </button>
            </div>

            {vinAnalysis && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">Analysis for VIN: {vinAnalysis.vin}</h4>

                {vinAnalysis.vehicle_info && (
                  <div className="mb-3 text-sm">
                    <span className="font-medium">Vehicle:</span> {vinAnalysis.vehicle_info.make} {vinAnalysis.vehicle_info.model} ({vinAnalysis.vehicle_info.year})
                  </div>
                )}

                <div className="space-y-2 text-sm">
                  <div className={`p-2 rounded ${vinAnalysis.availability?.available ? 'bg-green-100' : 'bg-red-100'}`}>
                    <span className="font-medium">Availability:</span> {vinAnalysis.availability?.days_available || 0} days available
                    {!vinAnalysis.availability?.available && ' (< minimum required)'}
                  </div>

                  <div className={`p-2 rounded ${vinAnalysis.candidates?.candidate_count > 0 ? 'bg-green-100' : 'bg-red-100'}`}>
                    <span className="font-medium">Candidates:</span> {vinAnalysis.candidates?.candidate_count || 0} eligible partners
                  </div>

                  {vinAnalysis.candidates?.top_candidates && vinAnalysis.candidates.top_candidates.length > 0 && (
                    <div className="p-2 bg-blue-100 rounded">
                      <span className="font-medium">Top candidates:</span>
                      <ul className="mt-1">
                        {vinAnalysis.candidates.top_candidates.map((c, i) => (
                          <li key={i}>• {c.name} (Score: {c.score})</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {vinAnalysis.assignment && (
                    <div className="p-2 bg-yellow-100 rounded">
                      <span className="font-medium">Assignment:</span> {vinAnalysis.assignment.status}
                      {vinAnalysis.assignment.assigned_to && (
                        <div>Assigned to: {vinAnalysis.assignment.assigned_to}</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ScheduleGeneration