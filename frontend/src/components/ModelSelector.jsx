/**
 * ModelSelector Component
 *
 * Checkbox tree UI for selecting vehicle makes/models for Partner Chain preferences.
 * Allows users to select 5-7 specific models to prioritize in chain generation.
 *
 * Features:
 * - Search box (filter by make/model name)
 * - Expandable make groups with model checkboxes
 * - Availability counts displayed per make/model
 * - Selected models shown as removable tags
 * - Lazy loading of availability data
 */

import React, { useState, useEffect } from 'react';
import '../styles/ModelSelector.css';

const ModelSelector = ({
  office,
  personId,
  startDate,
  numVehicles = 4,
  daysPerLoan = 8,
  onSelectionChange,
  value = []
}) => {
  const [availability, setAvailability] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedMakes, setExpandedMakes] = useState([]);
  const [selectedModels, setSelectedModels] = useState(value || []);

  // Load availability data when parameters change
  useEffect(() => {
    if (!office || !personId || !startDate) {
      return;
    }

    const loadAvailability = async () => {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          person_id: personId,
          office: office,
          start_date: startDate,
          num_vehicles: numVehicles,
          days_per_loan: daysPerLoan
        });

        const response = await fetch(
          `/api/chain-builder/model-availability?${params}`
        );

        if (!response.ok) {
          throw new Error(`Failed to load availability: ${response.status}`);
        }

        const data = await response.json();
        setAvailability(data);
      } catch (err) {
        console.error('Failed to load model availability:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadAvailability();
  }, [office, personId, startDate, numVehicles, daysPerLoan]);

  // Sync external value changes to internal state
  useEffect(() => {
    setSelectedModels(value || []);
  }, [value]);

  // Filter makes/models by search term
  const filteredAvailability = React.useMemo(() => {
    if (!searchTerm) return availability;

    const filtered = {};
    const lowerSearch = searchTerm.toLowerCase();

    Object.keys(availability).forEach(make => {
      const makeLower = make.toLowerCase();
      const makeMatches = makeLower.includes(lowerSearch);

      if (makeMatches) {
        // Make matches - include all models
        filtered[make] = availability[make];
      } else {
        // Check if any model matches
        const matchingModels = {};
        Object.keys(availability[make]).forEach(key => {
          if (key === 'total') {
            matchingModels.total = availability[make].total;
          } else if (key.toLowerCase().includes(lowerSearch)) {
            matchingModels[key] = availability[make][key];
          }
        });

        if (Object.keys(matchingModels).length > 1) {
          filtered[make] = matchingModels;
        }
      }
    });

    return filtered;
  }, [availability, searchTerm]);

  // Toggle make expansion
  const toggleMake = (make) => {
    setExpandedMakes(prev =>
      prev.includes(make)
        ? prev.filter(m => m !== make)
        : [...prev, make]
    );
  };

  // Check if all models in make are selected
  const isAllModelsSelected = (make) => {
    if (!availability[make]) return false;

    const models = Object.keys(availability[make]).filter(k => k !== 'total');
    if (models.length === 0) return false;

    return models.every(model =>
      selectedModels.some(s => s.make === make && s.model === model)
    );
  };

  // Check if specific model is selected
  const isModelSelected = (make, model) => {
    return selectedModels.some(s => s.make === make && s.model === model);
  };

  // Toggle entire make (select/deselect all models)
  const toggleEntireMake = (make) => {
    if (!availability[make]) return;

    const models = Object.keys(availability[make]).filter(k => k !== 'total');

    if (isAllModelsSelected(make)) {
      // Deselect all models in this make
      const newSelection = selectedModels.filter(s => s.make !== make);
      setSelectedModels(newSelection);
      onSelectionChange(newSelection);
    } else {
      // Select all models in this make
      const newModels = models.map(model => ({ make, model }));
      const newSelection = [
        ...selectedModels.filter(s => s.make !== make),
        ...newModels
      ];
      setSelectedModels(newSelection);
      onSelectionChange(newSelection);
    }
  };

  // Toggle specific model
  const toggleModel = (make, model) => {
    if (isModelSelected(make, model)) {
      // Deselect
      const newSelection = selectedModels.filter(
        s => !(s.make === make && s.model === model)
      );
      setSelectedModels(newSelection);
      onSelectionChange(newSelection);
    } else {
      // Select
      const newSelection = [...selectedModels, { make, model }];
      setSelectedModels(newSelection);
      onSelectionChange(newSelection);
    }
  };

  // Remove specific tag
  const removeTag = (make, model) => {
    const newSelection = selectedModels.filter(
      s => !(s.make === make && s.model === model)
    );
    setSelectedModels(newSelection);
    onSelectionChange(newSelection);
  };

  // Clear all selections
  const clearAll = () => {
    setSelectedModels([]);
    onSelectionChange([]);
  };

  if (loading) {
    return (
      <div className="model-selector loading">
        <div className="loading-spinner">Loading available models...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="model-selector error">
        <div className="error-message">
          ⚠️ Failed to load availability: {error}
        </div>
      </div>
    );
  }

  const makes = Object.keys(filteredAvailability).sort();

  return (
    <div className="model-selector">
      <div className="search-box">
        <input
          type="text"
          placeholder="🔍 Search make/model..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>

      {selectedModels.length > 0 && (
        <div className="selected-tags">
          <div className="tags-header">
            <span className="tags-label">Selected Models ({selectedModels.length}):</span>
            <button
              className="clear-all-button"
              onClick={clearAll}
              title="Clear all selections"
            >
              Clear All
            </button>
          </div>
          <div className="tags-container">
            {selectedModels.map((sel, idx) => (
              <span key={idx} className="tag">
                {sel.make} {sel.model}
                <button
                  className="tag-remove"
                  onClick={() => removeTag(sel.make, sel.model)}
                  title="Remove"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="tree-container">
        {makes.length === 0 ? (
          <div className="empty-state">
            {searchTerm ? (
              <p>No models match "{searchTerm}"</p>
            ) : (
              <p>No available models found</p>
            )}
          </div>
        ) : (
          makes.map(make => {
            const makeData = filteredAvailability[make];
            const models = Object.keys(makeData).filter(k => k !== 'total').sort();
            const isExpanded = expandedMakes.includes(make);
            const allSelected = isAllModelsSelected(make);

            return (
              <div key={make} className="make-group">
                <div className="make-header">
                  <label className="make-label">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={() => toggleEntireMake(make)}
                      className="make-checkbox"
                    />
                    <span className="make-name">{make}</span>
                    <span className="make-count">({makeData.total || 0} available)</span>
                  </label>
                  <button
                    className="expand-button"
                    onClick={() => toggleMake(make)}
                    title={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded ? '▼' : '▶'}
                  </button>
                </div>

                {isExpanded && (
                  <div className="models-list">
                    {models.map(model => {
                      const count = makeData[model] || 0;
                      const isSelected = isModelSelected(make, model);

                      return (
                        <label key={model} className="model-label">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleModel(make, model)}
                            className="model-checkbox"
                          />
                          <span className="model-name">{model}</span>
                          <span className="model-count">({count})</span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className="selector-footer">
        <span className="selection-summary">
          {selectedModels.length} model{selectedModels.length !== 1 ? 's' : ''} selected
        </span>
      </div>
    </div>
  );
};

export default ModelSelector;
