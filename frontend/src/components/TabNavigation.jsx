import React from 'react';

/**
 * Horizontal Tab Navigation Component
 *
 * Replaces the black menu bar when app is embedded in FMS iframe.
 * Uses FMS styling for consistency with parent application.
 *
 * Props:
 * - activeTab: Current active tab identifier
 * - onTabChange: Callback function when tab is clicked
 */
const TabNavigation = ({ activeTab, onTabChange }) => {
  const tabs = [
    { id: 'chain-builder', label: 'Chain Builder' },
    { id: 'calendar', label: 'Calendar' },
    { id: 'optimizer', label: 'Optimizer' },
    { id: 'upload', label: 'Upload Data' }
  ];

  return (
    <div className="border-b border-gray-300 mb-6">
      <nav className="flex space-x-8">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`
              relative
              text-lg
              font-bold
              py-3
              px-1
              transition-colors
              ${activeTab === tab.id
                ? 'text-green-600 border-b-2 border-green-600'
                : 'text-gray-500 hover:text-gray-700'
              }
            `}
            style={{
              fontSize: '18px',
              padding: '15px 0px'
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
};

export default TabNavigation;
