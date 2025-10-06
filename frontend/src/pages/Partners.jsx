import { useState, useEffect, Fragment } from 'react'
import { Listbox, Transition } from '@headlessui/react'

export default function Partners({ office }) {
  const [allPartners, setAllPartners] = useState([])
  const [selectedPartner, setSelectedPartner] = useState(null)
  const [selectedDate, setSelectedDate] = useState('')
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingPartners, setLoadingPartners] = useState(false)
  const [scheduling, setScheduling] = useState(false)
  const [message, setMessage] = useState('')

  // Load all partners on mount
  useEffect(() => {
    if (office) {
      loadAllPartners()
    }
  }, [office])

  // Get Monday of current week as default
  useEffect(() => {
    const today = new Date()
    const monday = new Date(today)
    monday.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1))
    setSelectedDate(monday.toISOString().split('T')[0])
  }, [])

  const loadAllPartners = async () => {
    setLoadingPartners(true)
    try {
      // Fetch all partners for the office (using empty query to get all results)
      const response = await fetch(`http://localhost:8081/ingest/partners/search?office=${encodeURIComponent(office)}&query=`)
      if (response.ok) {
        const data = await response.json()
        // Sort alphabetically
        const sorted = (data.partners || []).sort((a, b) => a.name.localeCompare(b.name))
        setAllPartners(sorted)
      }
    } catch (error) {
      console.error('Error loading partners:', error)
    } finally {
      setLoadingPartners(false)
    }
  }

  const handlePartnerChange = (partner) => {
    setSelectedPartner(partner)
    setCandidates([])
    setMessage('')
  }

  const handleFindVehicles = async () => {
    if (!selectedPartner || !selectedDate) {
      setMessage('Please select a partner and date')
      return
    }

    setLoading(true)
    setMessage('')

    try {
      const response = await fetch(
        `http://localhost:8081/ui/phase7/partner-day-candidates?person_id=${selectedPartner.person_id}&date=${selectedDate}&office=${office}`
      )

      if (response.ok) {
        const data = await response.json()
        if (data.success) {
          setCandidates(data.candidates || [])
          if (data.candidates.length === 0) {
            setMessage(data.message || 'No vehicles available for this date')
          }
        } else {
          setMessage(data.message || 'Error fetching candidates')
        }
      } else {
        setMessage('Error fetching vehicle candidates')
      }
    } catch (error) {
      console.error('Error:', error)
      setMessage('Network error fetching candidates')
    } finally {
      setLoading(false)
    }
  }

  const handleScheduleVehicle = async (candidate) => {
    if (!window.confirm(`Schedule ${candidate.make} ${candidate.model} to ${selectedPartner.name} on ${selectedDate}?`)) {
      return
    }

    setScheduling(true)

    try {
      // Calculate week start (Monday of the week)
      const date = new Date(selectedDate)
      const monday = new Date(date)
      monday.setDate(date.getDate() - date.getDay() + (date.getDay() === 0 ? -6 : 1))
      const weekStart = monday.toISOString().split('T')[0]

      const response = await fetch('http://localhost:8081/api/calendar/schedule-assignment', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vin: candidate.vin,
          person_id: selectedPartner.person_id,
          start_day: selectedDate,
          office: office,
          week_start: weekStart,
          partner_name: selectedPartner.name,
          make: candidate.make,
          model: candidate.model
        })
      })

      const result = await response.json()

      if (result.success) {
        setMessage(`✅ Successfully scheduled ${candidate.make} ${candidate.model} to ${selectedPartner.name}!`)
        // Refresh candidates to remove scheduled vehicle
        handleFindVehicles()
      } else {
        setMessage(`❌ ${result.message}`)
      }
    } catch (error) {
      console.error('Error scheduling:', error)
      setMessage('❌ Network error scheduling assignment')
    } finally {
      setScheduling(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200 mb-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="md:flex md:items-center md:justify-between">
            <div className="flex-1 min-w-0">
              <h2 className="text-3xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
                👥 Partner Scheduling
              </h2>
              <p className="mt-2 text-sm text-gray-600">
                Select a partner and date to find the best available vehicles for scheduling
              </p>
            </div>
            {office && (
              <div className="mt-4 flex md:mt-0 md:ml-4">
                <span className="inline-flex items-center px-4 py-2 rounded-md text-sm font-medium bg-blue-100 text-blue-800">
                  📍 Office: {office}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Office warning */}
        {!office && (
          <div className="rounded-md bg-yellow-50 border border-yellow-200 p-4 mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-yellow-800">
                  Office Required
                </h3>
                <div className="mt-2 text-sm text-yellow-700">
                  <p>Please select an office from the Optimizer tab first to use Partner Scheduling.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Partner Selection Card */}
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Select Partner</h3>
          <div className="grid grid-cols-1 gap-4">
            <div>
              <Listbox value={selectedPartner} onChange={handlePartnerChange} disabled={!office || loadingPartners}>
                <Listbox.Label className="block text-sm font-medium text-gray-700 mb-2">
                  Partner Name
                </Listbox.Label>
                <div className="relative">
                  <Listbox.Button className="relative w-full cursor-pointer rounded-lg bg-white py-3 pl-4 pr-10 text-left border-2 border-gray-300 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all duration-200 hover:border-gray-400">
                    <span className="block truncate font-medium text-gray-900">
                      {loadingPartners ? (
                        'Loading partners...'
                      ) : selectedPartner ? (
                        `${selectedPartner.name} - ${selectedPartner.address}`
                      ) : (
                        <span className="text-gray-500 font-normal">Select a partner...</span>
                      )}
                    </span>
                    <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                      <svg className="h-5 w-5 text-indigo-600" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                      </svg>
                    </span>
                  </Listbox.Button>

                  <Transition
                    as={Fragment}
                    leave="transition ease-in duration-100"
                    leaveFrom="opacity-100"
                    leaveTo="opacity-0"
                  >
                    <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                      {allPartners.map((partner) => (
                        <Listbox.Option
                          key={partner.person_id}
                          value={partner}
                          className={({ active }) =>
                            `relative cursor-pointer select-none py-3 pl-10 pr-4 ${
                              active ? 'bg-indigo-50 text-indigo-900' : 'text-gray-900'
                            }`
                          }
                        >
                          {({ selected, active }) => (
                            <>
                              <span className={`block truncate ${selected ? 'font-semibold' : 'font-normal'}`}>
                                {partner.name} - {partner.address}
                              </span>
                              {selected ? (
                                <span className={`absolute inset-y-0 left-0 flex items-center pl-3 ${active ? 'text-indigo-600' : 'text-indigo-600'}`}>
                                  <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                                  </svg>
                                </span>
                              ) : null}
                            </>
                          )}
                        </Listbox.Option>
                      ))}
                    </Listbox.Options>
                  </Transition>
                </div>
              </Listbox>
              {allPartners.length > 0 && (
                <p className="mt-2 text-sm text-gray-500">
                  {allPartners.length} partners available in {office}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Partner Profile Card */}
        {selectedPartner && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 shadow rounded-lg p-6 mb-6 border border-blue-200">
            <h3 className="text-lg font-medium text-gray-900 mb-4">📋 Partner Profile</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white rounded p-3">
                <span className="text-sm text-gray-500">Name</span>
                <p className="font-semibold text-gray-900">{selectedPartner.name}</p>
              </div>
              <div className="bg-white rounded p-3">
                <span className="text-sm text-gray-500">Office</span>
                <p className="font-semibold text-gray-900">{selectedPartner.office}</p>
              </div>
              <div className="bg-white rounded p-3 md:col-span-2">
                <span className="text-sm text-gray-500">Address</span>
                <p className="font-semibold text-gray-900">{selectedPartner.address || 'N/A'}</p>
              </div>
            </div>
          </div>
        )}

        {/* Date Picker and Search */}
        {selectedPartner && (
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Find Available Vehicles</h3>
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <label htmlFor="target-date" className="block text-sm font-medium text-gray-700 mb-2">
                  📅 Target Start Date
                </label>
                <input
                  id="target-date"
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="block w-full pl-3 pr-3 py-3 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 rounded-md"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={handleFindVehicles}
                  disabled={loading || !selectedDate}
                  className="w-full sm:w-auto inline-flex justify-center items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Loading...
                    </>
                  ) : (
                    <>
                      🔍 Find Vehicles
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Message */}
        {message && (
          <div className={`rounded-md p-4 mb-6 ${
            message.includes('✅')
              ? 'bg-green-50 border border-green-200'
              : 'bg-yellow-50 border border-yellow-200'
          }`}>
            <p className={`text-sm ${message.includes('✅') ? 'text-green-800' : 'text-yellow-800'}`}>
              {message}
            </p>
          </div>
        )}

        {/* Vehicle Candidates List */}
        {candidates.length > 0 && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="mb-4">
              <h3 className="text-lg font-medium text-gray-900">
                🚗 Available Vehicles for {selectedDate}
              </h3>
              <p className="mt-1 text-sm text-gray-600">
                Found {candidates.length} available vehicle{candidates.length !== 1 ? 's' : ''} ranked by score
              </p>
            </div>

            <div className="space-y-4">
              {candidates.map((candidate, idx) => (
                <div
                  key={idx}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow duration-200"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex-1">
                      <div className="flex items-center mb-2">
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-800 text-sm font-semibold mr-3">
                          {idx + 1}
                        </span>
                        <h4 className="text-lg font-semibold text-gray-900">
                          {candidate.make} {candidate.model} {candidate.year}
                        </h4>
                      </div>
                      <div className="ml-11 space-y-1">
                        <div className="flex flex-wrap gap-3 text-sm text-gray-600">
                          <span className="inline-flex items-center">
                            🔖 VIN: ...{candidate.vin.slice(-6)}
                          </span>
                          <span className="inline-flex items-center">
                            ⭐ Score: <strong className="ml-1 text-gray-900">{candidate.score}</strong>
                          </span>
                          <span className="inline-flex items-center">
                            🏆 Rank {candidate.rank}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500">
                          Base Score: {candidate.base_score} + Publication Bonus: {candidate.pub_bonus}
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 sm:mt-0 sm:ml-4">
                      <button
                        onClick={() => handleScheduleVehicle(candidate)}
                        disabled={scheduling}
                        className="w-full sm:w-auto inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
                      >
                        ✅ Schedule This
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
