import { useState, useEffect } from 'react'

function PublicationRates() {
  const [publicationData, setPublicationData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [windowMonths, setWindowMonths] = useState(24)
  const [minObserved, setMinObserved] = useState(3)
  const [filterMake, setFilterMake] = useState('')
  const [showSupportedOnly, setShowSupportedOnly] = useState(false)
  const [sortField, setSortField] = useState('loans_total_24m')
  const [sortDirection, setSortDirection] = useState('desc')
  const [makeSortField, setMakeSortField] = useState('total_loans')
  const [makeSortDirection, setMakeSortDirection] = useState('desc')

  useEffect(() => {
    fetchPublicationRates()
  }, [])

  const fetchPublicationRates = async () => {
    setIsLoading(true)
    setError('')
    setPublicationData(null)

    try {
      const params = new URLSearchParams({
        window_months: windowMonths.toString(),
        min_observed: minObserved.toString()
      })

      const response = await fetch(`http://localhost:8081/api/etl/publication_rates?${params}`)

      if (response.ok) {
        const data = await response.json()
        setPublicationData(data)
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Failed to fetch publication rates')
      }
    } catch (error) {
      setError(`Network error: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const handleMakeSort = (field) => {
    if (makeSortField === field) {
      setMakeSortDirection(makeSortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setMakeSortField(field)
      setMakeSortDirection('desc')
    }
  }

  const getSortedMakeStats = () => {
    if (!publicationData) return []

    const makeStats = [...publicationData.summary.by_make]

    makeStats.sort((a, b) => {
      let aVal = a[makeSortField]
      let bVal = b[makeSortField]

      // Handle null values
      if (aVal === null && bVal === null) return 0
      if (aVal === null) return 1  // nulls last
      if (bVal === null) return -1 // nulls last

      // Handle string fields
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase()
        bVal = bVal.toLowerCase()
      }

      if (makeSortDirection === 'asc') {
        return aVal < bVal ? -1 : aVal > bVal ? 1 : 0
      } else {
        return aVal > bVal ? -1 : aVal < bVal ? 1 : 0
      }
    })

    return makeStats
  }

  const getFilteredGrains = () => {
    if (!publicationData) return []

    let filtered = publicationData.grains

    if (filterMake) {
      filtered = filtered.filter(grain =>
        grain.make.toLowerCase().includes(filterMake.toLowerCase())
      )
    }

    if (showSupportedOnly) {
      filtered = filtered.filter(grain => grain.supported)
    }

    // Sort the filtered results
    filtered.sort((a, b) => {
      let aVal = a[sortField]
      let bVal = b[sortField]

      // Handle null values for publication_rate_observed
      if (sortField === 'publication_rate_observed') {
        if (aVal === null && bVal === null) return 0
        if (aVal === null) return 1  // nulls last
        if (bVal === null) return -1 // nulls last
      }

      // Handle string fields
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase()
        bVal = bVal.toLowerCase()
      }

      if (sortDirection === 'asc') {
        return aVal < bVal ? -1 : aVal > bVal ? 1 : 0
      } else {
        return aVal > bVal ? -1 : aVal < bVal ? 1 : 0
      }
    })

    return filtered
  }

  const formatRate = (rate) => {
    if (rate === null || rate === undefined) {
      return <span className="text-gray-500 italic">Insufficient data</span>
    }
    return <span className={rate >= 0.7 ? 'text-green-600' : rate >= 0.5 ? 'text-yellow-600' : 'text-red-600'}>
      {(rate * 100).toFixed(1)}%
    </span>
  }

  const getCoverageColor = (coverage) => {
    if (coverage >= 0.8) return 'text-green-600'
    if (coverage >= 0.5) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Publication Rate Analytics</h2>
        <p className="text-sm text-gray-600">24-month rolling publication rates by partner and vehicle make</p>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Window (Months)
            </label>
            <input
              type="number"
              value={windowMonths}
              onChange={(e) => setWindowMonths(parseInt(e.target.value) || 24)}
              min="1"
              max="60"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Min Observed Loans
            </label>
            <input
              type="number"
              value={minObserved}
              onChange={(e) => setMinObserved(parseInt(e.target.value) || 3)}
              min="1"
              max="20"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Filter by Make
            </label>
            <input
              type="text"
              value={filterMake}
              onChange={(e) => setFilterMake(e.target.value)}
              placeholder="e.g., Toyota"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <button
              onClick={fetchPublicationRates}
              disabled={isLoading}
              className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Computing...' : 'Refresh Rates'}
            </button>
          </div>
        </div>

        <div className="mt-4 flex items-center">
          <input
            id="supported-only"
            type="checkbox"
            checked={showSupportedOnly}
            onChange={(e) => setShowSupportedOnly(e.target.checked)}
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
          />
          <label htmlFor="supported-only" className="ml-2 block text-sm text-gray-700">
            Show only grains with sufficient data (supported)
          </label>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Summary Dashboard */}
      {publicationData && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
              <div className="text-xl font-bold text-blue-600">{publicationData.summary.total_grains.toLocaleString()}</div>
              <div className="text-xs text-gray-600">Total Grains</div>
              <div className="text-xs text-gray-500 mt-1">(partner × make)</div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
              <div className="text-xl font-bold text-green-600">{publicationData.summary.unique_partners}</div>
              <div className="text-xs text-gray-600">Unique Partners</div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
              <div className="text-xl font-bold text-purple-600">{publicationData.summary.total_loans.toLocaleString()}</div>
              <div className="text-xs text-gray-600">Total Loans</div>
              <div className="text-xs text-gray-500 mt-1">24-month window</div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
              <div className={`text-xl font-bold ${getCoverageColor(publicationData.summary.coverage_average)}`}>
                {(publicationData.summary.coverage_average * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-gray-600">Avg Coverage</div>
              <div className="text-xs text-gray-500 mt-1">data completeness</div>
            </div>
          </div>

          {/* Make-Level Summary */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
            <div className="p-4 border-b border-gray-200">
              <h3 className="text-xs font-medium text-gray-900">Publication Rates by Make</h3>
              <p className="text-xs text-gray-600 mt-1">Overall performance across all partners per vehicle make</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleMakeSort('make')}
                    >
                      Make {makeSortField === 'make' && (makeSortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleMakeSort('partner_count')}
                    >
                      Partners {makeSortField === 'partner_count' && (makeSortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleMakeSort('total_loans')}
                    >
                      Total Loans {makeSortField === 'total_loans' && (makeSortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleMakeSort('published_loans')}
                    >
                      Published Loans {makeSortField === 'published_loans' && (makeSortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleMakeSort('overall_rate')}
                    >
                      Publication Rate {makeSortField === 'overall_rate' && (makeSortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {getSortedMakeStats().map((make, index) => (
                    <tr key={make.make} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{make.make}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-600">{make.partner_count}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-600">{make.total_loans.toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-600">{make.published_loans.toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm text-center">{formatRate(make.overall_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Detailed Grains Table */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="p-4 border-b border-gray-200">
              <h3 className="text-xs font-medium text-gray-900">
                Partner-Make Publication Rates ({getFilteredGrains().length.toLocaleString()} grains)
              </h3>
              <p className="text-xs text-gray-600 mt-1">
                Individual partner performance by vehicle make • Window: {publicationData.summary.window_start} to {publicationData.summary.window_end}
              </p>
            </div>

            <div className="overflow-x-auto max-h-96">
              <table className="w-full">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleSort('partner_name')}
                    >
                      Partner Name {sortField === 'partner_name' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleSort('make')}
                    >
                      Make {sortField === 'make' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleSort('loans_total_24m')}
                    >
                      Total Loans {sortField === 'loans_total_24m' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleSort('publications_24m')}
                    >
                      Published {sortField === 'publications_24m' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleSort('publication_rate')}
                    >
                      Pub Rate {sortField === 'publication_rate' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                      onClick={() => handleSort('has_clip_data')}
                    >
                      Has Data {sortField === 'has_clip_data' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {getFilteredGrains().map((grain, index) => (
                    <tr key={`${grain.person_id}-${grain.make}`} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        <div className="font-medium">{grain.partner_name}</div>
                        <div className="text-xs text-gray-500">ID: {grain.person_id}</div>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{grain.make}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-600">{grain.loans_total_24m}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-600">{grain.publications_24m}</td>
                      <td className="px-4 py-3 text-sm text-center">{formatRate(grain.publication_rate)}</td>
                      <td className="px-4 py-3 text-center">
                        {grain.has_clip_data ? (
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            ✓ Yes
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                            No Data
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Data Quality Notice */}
          {publicationData.summary.coverage_average === 0 && (
            <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-yellow-800">
                    Publication Data Not Yet Available
                  </h3>
                  <div className="mt-2 text-sm text-yellow-700">
                    <p>
                      The <code>clips_received</code> field hasn't been backfilled in your loan history data yet.
                      All {publicationData.summary.total_grains.toLocaleString()} partner-make combinations show "Insufficient data"
                      instead of misleading 0% rates.
                    </p>
                    <p className="mt-2">
                      Once you add the SQL column and backfill historical clip tracking, this dashboard will show
                      meaningful publication rates for scheduling optimization.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default PublicationRates