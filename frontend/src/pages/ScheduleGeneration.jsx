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
      const progressUpdates = [
        { delay: 500, stage: 2, message: 'Building vehicle availability grid...' },
        { delay: 2000, stage: 3, message: 'Computing cooldown periods and constraints...' },
        { delay: 4000, stage: 4, message: 'Generating feasible vehicle-partner pairings...' },
        { delay: 6000, stage: 5, message: 'Scoring candidate assignments...' },
        { delay: 8000, stage: 6, message: 'Optimizing final schedule...' }
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
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${(progressStage / 6) * 100}%` }}
                />
              </div>

              {/* Current Stage Message */}
              <p className="text-sm text-gray-600">{progressMessage}</p>

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
                  <span>{progressStage >= 6 ? '✓' : '○'}</span>
                  <span>Optimizing schedule</span>
                </div>
              </div>
            </div>

            <p className="text-xs text-gray-500 italic">
              This process typically takes 10-20 seconds depending on data volume.
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

              {expandedSections.assignments && scheduleData.assignments && (
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

                  {/* Assignment Table */}
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">VIN</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Partner</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Make</th>
                          <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Score</th>
                          <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Tier Usage</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rationale</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {scheduleData.assignments.slice(0, 50).map((assignment, index) => (
                          <tr key={`${assignment.vin}-${assignment.person_id}`} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                            <td className="px-4 py-3 text-sm font-mono text-gray-900">
                              {assignment.vin.slice(-8)}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900">
                              <div className="font-medium">{assignment.partner_name || `Partner ${assignment.person_id}`}</div>
                              <div className="text-xs text-gray-500">ID: {assignment.person_id}</div>
                            </td>
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">{assignment.make}</td>
                            <td className="px-4 py-3 text-sm text-center">
                              <span className="font-semibold text-blue-600">{assignment.score}</span>
                            </td>
                            <td className="px-4 py-3 text-sm text-center">
                              <span className="text-gray-600">{assignment.tier_usage || 0}/{assignment.tier_cap || '∞'}</span>
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <div className="flex flex-wrap gap-1">
                                {assignment.rank_weight > 0 && (
                                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                    {assignment.rank} Rank (+{assignment.rank_weight})
                                  </span>
                                )}
                                {assignment.geo_bonus > 0 && (
                                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                    Geo Match (+{assignment.geo_bonus})
                                  </span>
                                )}
                                {assignment.history_bonus > 0 && (
                                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                    Pub History (+{assignment.history_bonus})
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