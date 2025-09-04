import { useState } from 'react'
import driveShopLogo from './assets/DriveShop_WebLogo.png'
import './App.css'

function App() {
  const [selectedOffice, setSelectedOffice] = useState('')
  const [selectedWeek, setSelectedWeek] = useState('')
  const [activeTab, setActiveTab] = useState('dashboard')

  const offices = ['SEA', 'PDX', 'LAX', 'SFO', 'PHX', 'DEN', 'LAS']
  
  const csvTypes = [
    { id: 'vehicles', name: 'Vehicles', description: 'VIN, make, model, office, availability', icon: '🚗' },
    { id: 'media_partners', name: 'Media Partners', description: 'Partner details, contact info, eligibility', icon: '📺' },
    { id: 'partner_make_rank', name: 'Partner Rankings', description: 'A+/A/B/C rankings per partner/make', icon: '⭐' },
    { id: 'loan_history', name: 'Loan History', description: 'Historical assignment data', icon: '📊' },
    { id: 'current_activity', name: 'Current Activity', description: 'Active bookings and holds', icon: '📅' },
    { id: 'ops_capacity', name: 'Office Capacity', description: 'Driver capacity limits per office', icon: '👥' },
    { id: 'budgets', name: 'Budgets (Optional)', description: 'Quarterly budget tracking', icon: '💰' }
  ]
  
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with DriveShop logo */}
      <header className="bg-black shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8" style={{ maxWidth: '1280px' }}>
          <div className="flex justify-between items-center h-20 relative">
            <div className="flex items-center space-x-4">
              <img 
                src={driveShopLogo} 
                alt="DriveShop Logo" 
                className="h-10 w-auto"
                onError={() => console.log('Logo failed to load')}
              />
            </div>
            <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', color: '#ffffff', fontSize: '16px', fontWeight: 500 }}>
              Media Scheduler
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
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8" style={{ maxWidth: '1280px' }}>
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
                    
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors cursor-pointer">
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
                    
                    <button 
                      className="w-full mt-4 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
                      disabled={true}
                    >
                      Upload {csvType.name}
                    </button>
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
        </div>
      </main>
    </div>
  )
}

export default App