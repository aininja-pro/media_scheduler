import { useState } from 'react'
import driveShopLogo from './assets/DriveShop_WebLogo.png'
import Availability from './pages/Availability.jsx'
import PublicationRates from './pages/PublicationRates.jsx'
import ScheduleGeneration from './pages/ScheduleGeneration.jsx'
import Optimizer from './pages/Optimizer.jsx'
import Calendar from './pages/Calendar.jsx'
import './App.css'

function App() {
  const [selectedOffice, setSelectedOffice] = useState('')
  const [selectedWeek, setSelectedWeek] = useState('')
  const [activeTab, setActiveTab] = useState('dashboard')
  const [vehiclesUrl, setVehiclesUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/active_vehicles.rpt&init=csv')
  const [mediaPartnersUrl, setMediaPartnersUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/media_partners.rpt&init=csv')
  const [approvedRanksUrl, setApprovedRanksUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/approved_makes.rpt&init=csv')
  const [loanHistoryUrl, setLoanHistoryUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/loan_history.rpt&init=csv')
  const [currentActivityUrl, setCurrentActivityUrl] = useState('https://reports.driveshop.com/?report=file:/home/deployer/reports/ai_scheduling/current_vehicle_activity.rpt&init=csv')
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMediaPartners, setIsLoadingMediaPartners] = useState(false)
  const [isLoadingApprovedRanks, setIsLoadingApprovedRanks] = useState(false)
  const [isLoadingLoanHistory, setIsLoadingLoanHistory] = useState(false)
  const [isLoadingCurrentActivity, setIsLoadingCurrentActivity] = useState(false)
  const [isLoadingOperationsData, setIsLoadingOperationsData] = useState(false)
  const [isLoadingBudgets, setIsLoadingBudgets] = useState(false)

  const offices = ['SEA', 'PDX', 'LAX', 'SFO', 'PHX', 'DEN', 'LAS']
  
  const handleVehiclesUpdate = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/vehicles/url?url=${encodeURIComponent(vehiclesUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} vehicles`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleMediaPartnersUpdate = async () => {
    setIsLoadingMediaPartners(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/media_partners/url?url=${encodeURIComponent(mediaPartnersUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} media partners`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingMediaPartners(false)
    }
  }

  const handleApprovedRanksUpdate = async () => {
    setIsLoadingApprovedRanks(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/approved_makes/url?url=${encodeURIComponent(approvedRanksUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} approved ranks`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingApprovedRanks(false)
    }
  }

  const handleLoanHistoryUpdate = async () => {
    setIsLoadingLoanHistory(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/loan_history/url?url=${encodeURIComponent(loanHistoryUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} loan history records`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingLoanHistory(false)
    }
  }

  const handleCurrentActivityUpdate = async () => {
    setIsLoadingCurrentActivity(true)
    try {
      const response = await fetch(`http://localhost:8081/ingest/current_activity/url?url=${encodeURIComponent(currentActivityUrl)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.rows_processed} current activity records`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingCurrentActivity(false)
    }
  }

  const handleOperationsDataUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setIsLoadingOperationsData(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`http://localhost:8081/ingest/operations_data`, {
        method: 'POST',
        body: formData,
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.tables_processed} tables: ${result.summary}`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingOperationsData(false)
      // Reset file input
      event.target.value = ''
    }
  }

  const handleBudgetsUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setIsLoadingBudgets(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`http://localhost:8081/ingest/budgets`, {
        method: 'POST',
        body: formData,
      })
      
      const result = await response.json()
      
      if (response.ok) {
        alert(`Success! Processed ${result.total_rows_processed} budget records`)
      } else {
        alert(`Error: ${result.detail}`)
      }
    } catch (error) {
      alert(`Network error: ${error.message}`)
    } finally {
      setIsLoadingBudgets(false)
      // Reset file input
      event.target.value = ''
    }
  }

  const csvTypes = [
    { id: 'vehicles', name: 'Vehicles', description: 'Year, make, model, VIN, fleet, dates', icon: '🚗' },
    { id: 'media_partners', name: 'Media Partners', description: 'Partner details, contact info, eligibility', icon: '📺' },
    { id: 'approved_makes', name: 'Approved Ranks', description: 'A+/A/B/C rankings per partner/make', icon: '⭐' },
    { id: 'loan_history', name: 'Loan History', description: 'Historical assignment data', icon: '📊' },
    { id: 'current_activity', name: 'Current Activity', description: 'Active bookings and holds', icon: '📅' },
    { id: 'operations_data', name: 'Operations Data', description: 'Rules, capacity limits, holiday dates', icon: '📊' },
    { id: 'budgets', name: 'Budgets', description: 'Office/fleet budget tracking by quarter', icon: '💰' }
  ]
  
  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header with DriveShop logo */}
      <header className="bg-black h-16 md:h-20">
        <div className="w-full px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
          <div className="flex items-center space-x-4">
              <img
                src={driveShopLogo}
                alt="DriveShop Logo"
                className="h-10 w-auto"
                onError={() => console.log('Logo failed to load')}
              />
              <span className="ml-3 text-white/90 text-lg md:text-xl lg:text-2xl font-semibold tracking-wide leading-none whitespace-nowrap">
                Media Scheduler
              </span>
          </div>

          <nav className="flex space-x-2">
              <button 
                onClick={() => setActiveTab('dashboard')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'dashboard' 
                    ? 'bg-white text-black' 
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Dashboard
              </button>
              <button 
                onClick={() => setActiveTab('upload')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'upload' 
                    ? 'bg-white text-black' 
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Upload Data
              </button>
              <button
                onClick={() => setActiveTab('schedule')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'schedule'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Schedule
              </button>
              <button
                onClick={() => setActiveTab('availability')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'availability'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Availability
              </button>
              <button
                onClick={() => setActiveTab('publication')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'publication'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Publication Rates
              </button>
              <button
                onClick={() => setActiveTab('scheduler')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'scheduler'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Schedule Generation
              </button>
              <button
                onClick={() => setActiveTab('optimizer')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'optimizer'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Optimizer
              </button>
              <button
                onClick={() => setActiveTab('calendar')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'calendar'
                    ? 'bg-white text-black'
                    : 'bg-gray-600 text-white hover:bg-gray-500'
                }`}
              >
                Calendar
              </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="w-full py-8 px-4 sm:px-6 lg:px-8">
        <div className="min-h-[800px]">
        
        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <>
            <div className="mb-8">
              <h2 className="text-3xl font-bold text-gray-900 mb-3">
                Vehicle Media Scheduler
              </h2>
              <p className="text-lg text-gray-600">
                Optimize vehicle assignments to media partners across all offices
              </p>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-8">
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="text-2xl font-bold text-blue-600">0</div>
                <div className="text-sm text-gray-500">Vehicles Loaded</div>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="text-2xl font-bold text-green-600">0</div>
                <div className="text-sm text-gray-500">Partners Loaded</div>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="text-2xl font-bold text-purple-600">7</div>
                <div className="text-sm text-gray-500">Active Offices</div>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="text-2xl font-bold text-orange-600">0</div>
                <div className="text-sm text-gray-500">Schedules Generated</div>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">Recent Activity</h3>
              </div>
              <div className="px-6 py-8 text-center">
                <div className="text-gray-400 text-6xl mb-4">📋</div>
                <p className="text-gray-500 text-lg mb-2">No recent activity</p>
                <p className="text-gray-400">Upload CSV data to get started</p>
              </div>
            </div>
          </>
        )}

        {/* Upload Data Tab */}
        {activeTab === 'upload' && (
          <>
            <div className="mb-8">
              <h2 className="text-3xl font-bold text-gray-900 mb-3">
                Upload CSV Data
              </h2>
              <p className="text-lg text-gray-600">
                Import data files for vehicles, partners, and operational constraints
              </p>
            </div>

            {/* CSV Upload Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {csvTypes.map((csvType) => (
                <div key={csvType.id} className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow">
                  <div className="p-6">
                    <div className="flex items-center mb-4">
                      <div className="text-3xl mr-3">{csvType.icon}</div>
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">{csvType.name}</h3>
                        <p className="text-sm text-gray-500">{csvType.description}</p>
                      </div>
                    </div>
                    
                    {/* CSV drop area for non-operations tables */}
                    {csvType.id !== 'operations_data' && csvType.id !== 'budgets' && (
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors cursor-pointer mb-4">
                        <div className="text-gray-400 mb-2">
                          <svg className="mx-auto h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                          </svg>
                        </div>
                        <p className="text-sm text-gray-600 mb-2">
                          Drop CSV file or <span className="text-blue-600 font-medium">browse</span>
                        </p>
                        <p className="text-xs text-gray-400">Max file size: 10MB</p>
                      </div>
                    )}
                    
                    {/* Special handling for Vehicles - URL input */}
                    {csvType.id === 'vehicles' ? (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={vehiclesUrl}
                            onChange={(e) => setVehiclesUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop reports URL..."
                          />
                        </div>
                        <button 
                          onClick={handleVehiclesUpdate}
                          disabled={isLoading}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoading ? 'Fetching...' : 'Update Vehicles Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'media_partners' ? (
                      /* Special handling for Media Partners - URL input */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={mediaPartnersUrl}
                            onChange={(e) => setMediaPartnersUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop media partners URL..."
                          />
                        </div>
                        <button 
                          onClick={handleMediaPartnersUpdate}
                          disabled={isLoadingMediaPartners}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoadingMediaPartners ? 'Fetching...' : 'Update Media Partners Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'approved_makes' ? (
                      /* Special handling for Approved Ranks - URL input */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={approvedRanksUrl}
                            onChange={(e) => setApprovedRanksUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop approved ranks URL..."
                          />
                        </div>
                        <button 
                          onClick={handleApprovedRanksUpdate}
                          disabled={isLoadingApprovedRanks}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoadingApprovedRanks ? 'Fetching...' : 'Update Approved Ranks Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'loan_history' ? (
                      /* Special handling for Loan History - URL input */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={loanHistoryUrl}
                            onChange={(e) => setLoanHistoryUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop loan history URL..."
                          />
                        </div>
                        <button 
                          onClick={handleLoanHistoryUpdate}
                          disabled={isLoadingLoanHistory}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoadingLoanHistory ? 'Fetching...' : 'Update Loan History Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'current_activity' ? (
                      /* Special handling for Current Activity - URL input */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Data Source URL:
                          </label>
                          <input
                            type="text"
                            value={currentActivityUrl}
                            onChange={(e) => setCurrentActivityUrl(e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2 text-xs focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            placeholder="Enter DriveShop current activity URL..."
                          />
                        </div>
                        <button 
                          onClick={handleCurrentActivityUpdate}
                          disabled={isLoadingCurrentActivity}
                          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          {isLoadingCurrentActivity ? 'Fetching...' : 'Update Current Activity Data'}
                        </button>
                      </div>
                    ) : csvType.id === 'operations_data' ? (
                      /* Special handling for Operations Data - Excel file upload */
                      <div className="space-y-3">
                        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-green-400 transition-colors">
                          <input
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={handleOperationsDataUpload}
                            className="hidden"
                            id={`file-input-${csvType.id}`}
                          />
                          <label
                            htmlFor={`file-input-${csvType.id}`}
                            className="cursor-pointer"
                          >
                            <div className="text-gray-400 mb-2">
                              <svg className="mx-auto h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                              </svg>
                            </div>
                            <p className="text-sm text-gray-600 mb-2">
                              Drop Excel file or <span className="text-green-600 font-medium">browse</span>
                            </p>
                            <p className="text-xs text-gray-400">Max file size: 10MB | .xlsx, .xls</p>
                          </label>
                        </div>
                        <div className="text-xs text-gray-500 space-y-1 mb-4">
                          <div>✅ Sheet 1: Rules</div>
                          <div>✅ Sheet 2: Ops Capacity</div>
                          <div>✅ Sheet 3: Holiday/Blackout Dates</div>
                        </div>
                        <div className="mt-auto">
                          <button 
                            disabled={isLoadingOperationsData}
                            className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                          >
                            {isLoadingOperationsData ? 'Processing...' : 'Ready for Excel Upload'}
                          </button>
                        </div>
                      </div>
                    ) : csvType.id === 'budgets' ? (
                      /* Special handling for Budgets - Excel file upload */
                      <div className="space-y-3">
                        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-green-400 transition-colors">
                          <input
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={handleBudgetsUpload}
                            className="hidden"
                            id={`file-input-${csvType.id}`}
                          />
                          <label
                            htmlFor={`file-input-${csvType.id}`}
                            className="cursor-pointer"
                          >
                            <div className="text-gray-400 mb-2">
                              <svg className="mx-auto h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                              </svg>
                            </div>
                            <p className="text-sm text-gray-600 mb-2">
                              Drop Excel file or <span className="text-green-600 font-medium">browse</span>
                            </p>
                            <p className="text-xs text-gray-400">Max file size: 10MB | .xlsx, .xls</p>
                          </label>
                        </div>
                        <div className="text-xs text-gray-500 space-y-1 mb-4">
                          <div>✅ Office budget data by quarter</div>
                          <div>✅ Fleet/make budget allocations</div>
                          <div>✅ Usage tracking and reporting</div>
                        </div>
                        <div className="mt-auto">
                          <button 
                            disabled={isLoadingBudgets}
                            className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
                          >
                            {isLoadingBudgets ? 'Processing...' : 'Ready for Budget Upload'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Regular file upload for other tables */
                      <button 
                        className="w-full mt-4 font-medium py-2 px-4 rounded-md transition-colors text-white border border-transparent bg-gray-600 hover:bg-white hover:text-black hover:border-black disabled:cursor-not-allowed shadow-sm"
                        disabled={true}
                      >
                        Upload {csvType.name}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Schedule Tab */}
        {activeTab === 'schedule' && (
          <>
            <div className="mb-8">
              <h2 className="text-3xl font-bold text-gray-900 mb-3">
                Generate Schedule
              </h2>
              <p className="text-lg text-gray-600">
                Create optimized vehicle-to-partner assignments for a specific office and week
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-md p-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Select Office
                  </label>
                  <select 
                    className="w-full border border-gray-300 rounded-md px-4 py-3 text-base focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    value={selectedOffice}
                    onChange={(e) => setSelectedOffice(e.target.value)}
                  >
                    <option value="">Choose an office...</option>
                    {offices.map(office => (
                      <option key={office} value={office}>{office}</option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Week Start Date (Monday)
                  </label>
                  <input 
                    type="date" 
                    className="w-full border border-gray-300 rounded-md px-4 py-3 text-base focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    value={selectedWeek}
                    onChange={(e) => setSelectedWeek(e.target.value)}
                  />
                </div>
              </div>
              
              <div className="mt-8">
                <button 
                  className={`w-full py-4 px-6 rounded-md text-lg font-medium transition-colors ${
                    selectedOffice && selectedWeek
                      ? 'bg-green-600 hover:bg-green-700 text-white'
                      : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  }`}
                  disabled={!selectedOffice || !selectedWeek}
                >
                  {selectedOffice && selectedWeek 
                    ? `Generate Schedule for ${selectedOffice}` 
                    : 'Select Office and Date to Continue'
                  }
                </button>
              </div>
            </div>
          </>
        )}

        {/* Availability Tab */}
        {activeTab === 'availability' && (
          <Availability />
        )}

        {/* Publication Rates Tab */}
        {activeTab === 'publication' && (
          <PublicationRates />
        )}

        {/* Schedule Generation Tab */}
        {activeTab === 'scheduler' && (
          <ScheduleGeneration />
        )}

        {/* Optimizer Tab */}
        {activeTab === 'optimizer' && (
          <Optimizer />
        )}

        {/* Calendar Tab */}
        {activeTab === 'calendar' && (
          <Calendar />
        )}
        </div>
      </main>
    </div>
  )
}

export default App