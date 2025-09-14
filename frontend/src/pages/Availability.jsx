import { useState, useEffect } from 'react'

function Availability() {
  const [selectedOffice, setSelectedOffice] = useState('Los Angeles')
  const [weekStart, setWeekStart] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [availabilityData, setAvailabilityData] = useState(null)
  const [offices, setOffices] = useState(['Los Angeles', 'Detroit', 'San Francisco', 'Dallas', 'Miami']) // Fallback list
  const [error, setError] = useState('')
  const [showZeroPartnersOnly, setShowZeroPartnersOnly] = useState(false)
  const [selectedCell, setSelectedCell] = useState(null)
  const [partnerDetails, setPartnerDetails] = useState(null)
  const [isLoadingPartners, setIsLoadingPartners] = useState(false)

  // Get current Monday as default
  const getCurrentMonday = () => {
    const today = new Date()
    const dayOfWeek = today.getDay()
    const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek // Handle Sunday (0) specially
    const monday = new Date(today)
    monday.setDate(today.getDate() + daysToMonday)
    return monday.toISOString().split('T')[0]
  }

  useEffect(() => {
    setWeekStart(getCurrentMonday())
    fetchOffices()
  }, [])

  const fetchOffices = async () => {
    try {
      const response = await fetch('http://localhost:8081/api/etl/offices')
      if (response.ok) {
        const result = await response.json()
        setOffices(result.offices)
        if (result.offices.length > 0 && !result.offices.includes(selectedOffice)) {
          setSelectedOffice(result.offices[0])
        }
      }
    } catch (error) {
      console.warn('Failed to fetch offices, using fallback list')
    }
  }

  const fetchAvailability = async () => {
    if (!selectedOffice || !weekStart) {
      setError('Please select an office and week start date')
      return
    }

    setIsLoading(true)
    setError('')
    setAvailabilityData(null)

    try {
      const url = `http://localhost:8081/api/etl/availability?office=${encodeURIComponent(selectedOffice)}&week_start=${weekStart}`
      const response = await fetch(url)

      if (response.ok) {
        const data = await response.json()
        setAvailabilityData(data)
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Failed to fetch availability data')
      }
    } catch (error) {
      setError(`Network error: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (dateStr) => {
    const date = new Date(dateStr + 'T00:00:00')
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    })
  }

  const getAvailabilitySymbol = (isAvailable) => {
    return isAvailable ? '✅' : '❌'
  }

  const fetchPartnerDetails = async (vin, day) => {
    setIsLoadingPartners(true)
    setPartnerDetails(null)

    try {
      const url = `http://localhost:8081/api/etl/eligible_partners?vin=${encodeURIComponent(vin)}&day=${day}`
      const response = await fetch(url)

      if (response.ok) {
        const data = await response.json()
        setPartnerDetails(data)
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Failed to fetch partner details')
      }
    } catch (error) {
      setError(`Network error: ${error.message}`)
    } finally {
      setIsLoadingPartners(false)
    }
  }

  const handleCellClick = (vin, dayIndex) => {
    const day = availabilityData.days[dayIndex]
    setSelectedCell({ vin, day, dayIndex })
    fetchPartnerDetails(vin, day)
  }

  const closeModal = () => {
    setSelectedCell(null)
    setPartnerDetails(null)
  }

  // Filter rows based on zero partners toggle
  const getFilteredRows = () => {
    if (!availabilityData) return []

    if (showZeroPartnersOnly) {
      return availabilityData.rows.filter(row =>
        row.eligible_partner_counts && row.eligible_partner_counts.some(count => count === 0)
      )
    }

    return availabilityData.rows
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Vehicle Availability Grid</h1>
        <p className="text-gray-600">View which vehicles are available for scheduling by office and week</p>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Office
            </label>
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
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Week Start (Monday)
            </label>
            <input
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <button
              onClick={fetchAvailability}
              disabled={isLoading}
              className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Loading...' : 'Load Availability'}
            </button>
          </div>

          <div className="flex items-center">
            <input
              id="zero-partners-filter"
              type="checkbox"
              checked={showZeroPartnersOnly}
              onChange={(e) => setShowZeroPartnersOnly(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor="zero-partners-filter" className="ml-2 block text-sm text-gray-700">
              Show only VINs with zero eligible partners
            </label>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Results */}
      {availabilityData && (
        <>
          {/* Summary Bar */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-blue-600">
                  {availabilityData.summary.vehicle_count}
                </div>
                <div className="text-sm text-gray-600">Total Vehicles</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-600">
                  {availabilityData.summary.available_today}
                </div>
                <div className="text-sm text-gray-600">Available Monday</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-purple-600">
                  {(availabilityData.summary.availability_rate_today * 100).toFixed(1)}%
                </div>
                <div className="text-sm text-gray-600">Monday Rate</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-gray-700">
                  {availabilityData.office}
                </div>
                <div className="text-sm text-gray-600">Office</div>
              </div>
            </div>
          </div>

          {/* Availability Grid */}
          {getFilteredRows().length > 0 ? (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200">
              <div className="p-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">
                  Availability Grid - Week of {formatDate(availabilityData.week_start)}
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  ✅ = Available, ❌ = Unavailable (due to service, loan, or lifecycle constraints)
                  <br />
                  Click any cell to see eligible partners for that VIN and day
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[120px]">
                        VIN
                      </th>
                      {availabilityData.days.map((day, index) => (
                        <th key={day} className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[80px]">
                          <div>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][index]}</div>
                          <div className="text-[10px] font-normal mt-1">
                            {formatDate(day).split(', ')[1]}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {getFilteredRows().map((row, index) => (
                      <tr key={row.vin} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">
                          {row.vin.slice(-8)} {/* Show last 8 characters of VIN */}
                        </td>
                        {row.availability.map((isAvailable, dayIndex) => {
                          const partnerCount = row.eligible_partner_counts ? row.eligible_partner_counts[dayIndex] : 0;
                          const hasZeroPartners = partnerCount === 0;

                          return (
                            <td
                              key={dayIndex}
                              className={`px-2 py-3 text-center cursor-pointer hover:bg-gray-100 ${
                                hasZeroPartners ? 'bg-red-50 border border-red-200' : ''
                              }`}
                              onClick={() => handleCellClick(row.vin, dayIndex)}
                            >
                              <div className="flex flex-col items-center space-y-1">
                                <span className={`text-lg ${isAvailable ? 'text-green-600' : 'text-red-500'}`}>
                                  {getAvailabilitySymbol(isAvailable)}
                                </span>
                                <span
                                  className={`text-xs px-2 py-1 rounded-full font-medium ${
                                    hasZeroPartners
                                      ? 'bg-red-100 text-red-800'
                                      : partnerCount > 0
                                        ? 'bg-blue-100 text-blue-800'
                                        : 'bg-gray-100 text-gray-600'
                                  }`}
                                >
                                  {partnerCount}
                                </span>
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Daily Summary */}
              <div className="p-4 border-t border-gray-200 bg-gray-50">
                <div className="text-sm font-medium text-gray-700 mb-2">Available by Day:</div>
                <div className="grid grid-cols-7 gap-2 text-center text-sm">
                  {availabilityData.summary.available_by_day.map((count, index) => (
                    <div key={index} className="bg-white rounded px-2 py-1">
                      <div className="font-semibold text-blue-600">{count}</div>
                      <div className="text-xs text-gray-500">
                        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][index]}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
              <div className="text-gray-500">
                <div className="text-lg font-medium mb-2">No vehicles found</div>
                <div className="text-sm">
                  No vehicles found for office "{availabilityData.office}" during the selected week.
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Partner Details Modal */}
      {selectedCell && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Partner Eligibility</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    VIN: {selectedCell.vin.slice(-8)} • {formatDate(selectedCell.day)}
                  </p>
                </div>
                <button
                  onClick={closeModal}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {isLoadingPartners ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="text-gray-600 mt-2">Loading partner details...</p>
                </div>
              ) : partnerDetails ? (
                <div className="space-y-6">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="font-medium text-gray-700">Make:</span> {partnerDetails.make}
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Office:</span> {partnerDetails.office}
                      </div>
                    </div>
                  </div>

                  {/* Eligible Partners */}
                  {partnerDetails.eligible && partnerDetails.eligible.length > 0 && (
                    <div>
                      <h4 className="text-md font-medium text-green-800 mb-3">
                        ✅ Eligible Partners ({partnerDetails.eligible.length})
                      </h4>
                      <div className="space-y-2">
                        {partnerDetails.eligible.map((partner, index) => (
                          <div key={index} className="bg-green-50 border border-green-200 rounded-lg p-3">
                            <div className="flex justify-between items-start">
                              <div>
                                <div className="font-medium text-green-900">{partner.name}</div>
                                <div className="text-sm text-green-700">ID: {partner.partner_id}</div>
                              </div>
                              <div className="text-xs text-green-600">
                                {partner.why.join(', ')}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Blocked Partners */}
                  {partnerDetails.blocked && partnerDetails.blocked.length > 0 && (
                    <div>
                      <h4 className="text-md font-medium text-red-800 mb-3">
                        ❌ Blocked Partners ({partnerDetails.blocked.length})
                      </h4>
                      <div className="space-y-2">
                        {partnerDetails.blocked.map((partner, index) => (
                          <div key={index} className="bg-red-50 border border-red-200 rounded-lg p-3">
                            <div className="flex justify-between items-start">
                              <div>
                                <div className="font-medium text-red-900">{partner.name}</div>
                                <div className="text-sm text-red-700">ID: {partner.partner_id}</div>
                              </div>
                              <div className="text-xs text-red-600">
                                {partner.why.join(', ')}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* No Partners */}
                  {(!partnerDetails.eligible || partnerDetails.eligible.length === 0) &&
                   (!partnerDetails.blocked || partnerDetails.blocked.length === 0) && (
                    <div className="text-center py-8">
                      <div className="text-gray-500">
                        <div className="text-lg font-medium mb-2">No eligible partners</div>
                        <div className="text-sm">
                          No partners are available for this {partnerDetails.make} vehicle on this day.
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <div className="text-gray-500">Failed to load partner details</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Availability