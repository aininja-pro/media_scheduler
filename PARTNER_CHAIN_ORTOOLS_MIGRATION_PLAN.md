# Partner Chain OR-Tools Migration with Model Preferences
**Date Created:** 2025-11-01
**Status:** Planning Complete - Ready for Implementation
**Feature:** Migrate Partner Chain from Greedy to OR-Tools + Add Model Preference Filtering

---

## Table of Contents
1. [Overview](#overview)
2. [Current vs Proposed Architecture](#current-vs-proposed-architecture)
3. [Business Requirements](#business-requirements)
4. [OR-Tools Model Design](#or-tools-model-design)
5. [Implementation Plan - 6 Phases](#implementation-plan---6-phases)
6. [UI/UX Design](#uiux-design)
7. [API Specifications](#api-specifications)
8. [Testing Strategy](#testing-strategy)
9. [Rollback Strategy](#rollback-strategy)

---

## Overview

### Current State (Greedy Algorithm)
**File:** `backend/app/routers/chain_builder.py` lines 260-382

**How it works:**
```python
# For each slot sequentially:
for slot_index, smart_slot in enumerate(smart_slots):
    # Get available vehicles for this slot
    slot_vins = get_available_vehicles_for_slot(...)

    # Score candidates using optimizer scoring
    scored_candidates = compute_candidate_scores(...)

    # Pick best vehicle that doesn't violate rules
    # HARD RULES:
    # - No duplicate models in chain
    # - No 3+ consecutive same make
    best_vehicle = scored_candidates.sort_values('score').iloc[0]

    suggested_chain.append(best_vehicle)
    used_vins.add(vin)
    used_models.add((make, model))
```

**Problems:**
1. ❌ Greedy = locally optimal, not globally optimal
2. ❌ Can't optimize across all slots simultaneously
3. ❌ No model preference support (except hard filter)
4. ❌ Can't balance diversity vs quality tradeoffs
5. ❌ Sometimes gets "stuck" with suboptimal early picks

**Example Problem:**
```
Slot 1: Picks highest-scoring vehicle (Audi A5, score 1200)
Slot 2: Now forced to avoid Audi A5 model
Slot 3: Now forced to avoid consecutive Audi
Slot 4: Limited options, settles for low-score vehicle (Honda Civic, score 400)

Better Global Solution:
Slot 1: Honda Accord (score 1100) ← Slightly lower
Slot 2: Audi A5 (score 1200)
Slot 3: Toyota Camry (score 1150)
Slot 4: Genesis G90 (score 1180)
Total: 4630 vs 4200 (greedy)
```

---

### Proposed State (OR-Tools CP-SAT Solver)

**Why OR-Tools?**
1. ✅ Global optimization - considers all slots simultaneously
2. ✅ Flexible constraint handling (hard + soft)
3. ✅ Multi-objective optimization (quality + diversity + preferences)
4. ✅ Fast solving (<5 seconds for 4-6 vehicles, 50-100 candidates)
5. ✅ Proven - already works great for Vehicle Chain
6. ✅ Explainable - can show why vehicles were selected

**Similarity to Vehicle Chain Solver:**
- Vehicle Chain: Pick N partners for 1 vehicle (minimize distance, maximize quality)
- Partner Chain: Pick N vehicles for 1 partner (maximize quality, diversity, preferences)

Both are **assignment problems with sequencing constraints**.

---

## Current vs Proposed Architecture

### File Structure

**Current:**
```
backend/app/
├── routers/
│   └── chain_builder.py (lines 42-450)
│       └── suggest_chain() ← GREEDY LOOP HERE
├── solver/
│   ├── scoring.py (compute_candidate_scores)
│   └── vehicle_chain_solver.py (OR-Tools for Vehicle Chain)
```

**Proposed:**
```
backend/app/
├── routers/
│   └── chain_builder.py (lines 42-450)
│       └── suggest_chain() ← CALL NEW SOLVER HERE
├── solver/
│   ├── scoring.py (compute_candidate_scores) [REUSE]
│   ├── vehicle_chain_solver.py (OR-Tools for Vehicle Chain) [REFERENCE]
│   └── partner_chain_solver.py (NEW - OR-Tools for Partner Chain)
```

---

## Business Requirements

### From Scheduler Feedback (David Morck):
> "When solving for a partner, a lot of time they give me a list of models they want to review. It would be great if I could pick these 5-7 models and it would generate this optimized chain."

> "It doesn't necessarily have to link perfectly, but what is the best chain based on availability?"

### Interpreted Requirements:

1. **Model Preference Selection**
   - User picks 5-7 specific models (e.g., Honda Accord, Toyota Camry, Audi A5)
   - System prioritizes these models in chain generation
   - If insufficient preferred models, fills with other high-quality vehicles

2. **Preference Modes**
   - **Prioritize:** Boost preferred models' scores (+800 points)
   - **Strict:** ONLY use preferred models (fail if insufficient)
   - **Ignore:** Let optimizer decide (no preferences)

3. **Gaps Allowed**
   - Chains don't need to be perfectly sequential (gaps between loans OK)
   - Example: Slot 1 ends Nov 10, Slot 2 starts Nov 15 (5-day gap) ← ALLOWED
   - Uses `smart_scheduling.py` to thread around existing commitments

4. **Optimization Goals**
   - Maximize total quality score (tier rank + publication + geography)
   - Balance model diversity (prefer different makes/models)
   - Respect partner preferences (boost preferred models)
   - Avoid monotony (no 3+ consecutive same make)

---

## OR-Tools Model Design

### Decision Variables

```python
# Binary: Is vehicle v assigned to slot s?
x[vin, slot_index] = model.NewBoolVar(f'x_{vin}_{slot}')

# Example:
# x['1HGBH41JXMN109186', 0] = 1  ← Honda Accord assigned to Slot 0
# x['1HGBH41JXMN109186', 1] = 0  ← Honda Accord NOT assigned to Slot 1
```

### Hard Constraints

```python
# 1. Each slot assigned exactly one vehicle
for s in range(num_slots):
    model.Add(sum(x[v, s] for v in candidate_vins) == 1)

# 2. Each vehicle used at most once
for v in candidate_vins:
    model.Add(sum(x[v, s] for s in range(num_slots)) <= 1)

# 3. Vehicle available during slot dates
for v in candidate_vins:
    for s in range(num_slots):
        if not is_available(v, smart_slots[s]):
            model.Add(x[v, s] == 0)

# 4. No duplicate models (HARD RULE)
# Group VINs by (make, model)
model_to_vins = {}  # {('Honda', 'Accord'): ['VIN1', 'VIN2', ...]}
for make_model, vins in model_to_vins.items():
    # At most 1 vehicle with this make/model in entire chain
    model.Add(
        sum(x[v, s] for v in vins for s in range(num_slots)) <= 1
    )

# 5. STRICT MODE: Only preferred models (if specified)
if preference_mode == "strict" and model_preferences:
    preferred_vins = get_preferred_vins(model_preferences, vehicles_df)
    for v in candidate_vins:
        if v not in preferred_vins:
            for s in range(num_slots):
                model.Add(x[v, s] == 0)
```

### Soft Objectives (Weighted)

```python
# Objective 1: Maximize vehicle quality scores
# Scores from compute_candidate_scores():
#   - Rank weight (A+=1000, A=700, B=400, C=100)
#   - Geo bonus (market match = +100)
#   - History bonus (publications >=1 = +50)
#   - Pub rate bonus (0-100 based on rate)
#   - Model bonus (hash-based 0-50)
#   - VIN bonus (hash-based 0-20)

total_quality_score = sum(
    vehicle_scores[v] * x[v, s]
    for v in candidate_vins
    for s in range(num_slots)
)

# Objective 2: Penalize consecutive same make (avoid monotony)
# Create binary variables for "consecutive same make" events
consecutive_same_make = {}
for make, vins in make_to_vins.items():
    for s in range(num_slots - 1):
        # Is slot s this make? Is slot s+1 this make?
        slot_s_is_make = sum(x[v, s] for v in vins)
        slot_s1_is_make = sum(x[v, s+1] for v in vins)

        # consecutive = 1 IFF both slots have this make
        consecutive = model.NewBoolVar(f'consec_{make}_{s}')
        model.Add(consecutive <= slot_s_is_make)
        model.Add(consecutive <= slot_s1_is_make)
        model.Add(consecutive >= slot_s_is_make + slot_s1_is_make - 1)

        consecutive_same_make[make, s] = consecutive

diversity_penalty = sum(
    consecutive_same_make[make, s] * 150  # Penalty per consecutive pair
    for make, s in consecutive_same_make
)

# Objective 3: Boost preferred models (PRIORITIZE mode)
preference_bonus = 0
if preference_mode == "prioritize" and model_preferences:
    preferred_vins = get_preferred_vins(model_preferences, vehicles_df)
    preference_bonus = sum(
        800 * x[v, s]  # +800 points per preferred vehicle
        for v in preferred_vins
        for s in range(num_slots)
    )

# Combined Objective
model.Maximize(
    total_quality_score +    # Primary: Vehicle quality
    preference_bonus -       # Boost: Preferred models
    diversity_penalty        # Penalty: Consecutive same make
)
```

### Solver Parameters

```python
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 30
solver.parameters.random_seed = 42  # Deterministic
solver.parameters.num_search_workers = 4  # Parallel search
```

---

## Implementation Plan - 6 Phases

### Phase 1: Backend Solver Foundation
**Estimated:** 3-5 days

#### Chunk 1.1: Create partner_chain_solver.py ✅
**Files Created:**
- `backend/app/solver/partner_chain_solver.py`

**Functions:**
```python
@dataclass
class Vehicle:
    """Vehicle candidate for partner chain"""
    vin: str
    make: str
    model: str
    year: str
    score: int
    rank: str  # A+, A, B, C
    available: bool

@dataclass
class ModelPreference:
    """User-specified model preference"""
    make: str
    model: str
    boost_score: int = 800

@dataclass
class PartnerChainResult:
    """Result from OR-Tools solver"""
    status: str  # 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE'
    chain: List[Dict]  # Selected vehicles with slots
    optimization_stats: Dict
    solver_time_ms: int
    alternatives: List[Dict]  # Top N alternative solutions

def solve_partner_chain(
    person_id: int,
    partner_name: str,
    office: str,
    smart_slots: List[Dict],  # From smart_scheduling
    candidate_vehicles_df: pd.DataFrame,
    vehicle_scores: Dict[str, int],  # From compute_candidate_scores
    model_preferences: Optional[List[ModelPreference]] = None,
    preference_mode: str = "prioritize",  # "prioritize" | "strict" | "ignore"
    diversity_weight: float = 150.0,  # Penalty for consecutive same make
    min_quality_threshold: int = 400  # Minimum acceptable score
) -> PartnerChainResult:
    """
    Solve partner chain using OR-Tools CP-SAT.

    Decision Variables:
        x[vin, slot] = 1 if vehicle assigned to slot

    Hard Constraints:
        - Each slot gets exactly 1 vehicle
        - Each vehicle used at most once
        - Vehicle available during slot
        - No duplicate models in chain
        - STRICT mode: Only preferred models

    Soft Objectives:
        - Maximize total quality score
        - Minimize consecutive same make penalty
        - Maximize preference bonus (if PRIORITIZE mode)

    Returns:
        PartnerChainResult with optimal chain
    """
```

**Testing:**
- ✅ Solver finds optimal 4-vehicle chain
- ✅ No duplicate models
- ✅ All vehicles available during slots
- ✅ Preference mode "prioritize" boosts scores
- ✅ Preference mode "strict" filters to only preferred
- ✅ Diversity penalty works (avoids consecutive same make)

**Commit Message:**
`"Add OR-Tools CP-SAT solver for Partner Chain optimization"`

---

#### Chunk 1.2: Helper Functions for Model Grouping ✅
**Files Modified:**
- `backend/app/solver/partner_chain_solver.py`

**New Functions:**
```python
def group_vehicles_by_model(
    vehicles_df: pd.DataFrame
) -> Dict[Tuple[str, str], List[str]]:
    """
    Group VINs by (make, model).
    Returns: {('Honda', 'Accord'): ['VIN1', 'VIN2', ...]}
    """

def group_vehicles_by_make(
    vehicles_df: pd.DataFrame
) -> Dict[str, List[str]]:
    """
    Group VINs by make.
    Returns: {'Honda': ['VIN1', 'VIN2', ...]}
    """

def get_preferred_vins(
    model_preferences: List[ModelPreference],
    vehicles_df: pd.DataFrame
) -> Set[str]:
    """
    Get VINs matching preferred models.
    Returns: {'VIN1', 'VIN2', ...}
    """

def calculate_preference_bonus(
    vin: str,
    vehicles_df: pd.DataFrame,
    model_preferences: List[ModelPreference]
) -> int:
    """
    Calculate bonus for preferred vehicle.
    Returns: 800 if preferred, 0 otherwise
    """
```

**Commit Message:**
`"Add model grouping utilities for Partner Chain solver"`

---

### Phase 2: API Integration
**Estimated:** 2-3 days

#### Chunk 2.1: Modify /suggest-chain Endpoint ✅
**Files Modified:**
- `backend/app/routers/chain_builder.py` (lines 42-450)

**Changes:**
```python
@router.get("/suggest-chain")
async def suggest_chain(
    person_id: int = Query(...),
    office: str = Query(...),
    start_date: str = Query(...),
    num_vehicles: int = Query(4, ge=1, le=10),
    days_per_loan: int = Query(7, ge=1, le=14),
    preferred_makes: Optional[str] = Query(None),  # DEPRECATED
    model_preferences: Optional[str] = Query(None),  # NEW: JSON string
    preference_mode: str = Query("prioritize"),  # NEW: "prioritize" | "strict" | "ignore"
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    NEW: Uses OR-Tools solver instead of greedy loop.

    model_preferences format:
        '[{"make":"Honda","model":"Accord"},{"make":"Toyota","model":"Camry"}]'
    """
```

**Implementation:**
```python
# REPLACE greedy loop (lines 260-382) with:

# Parse model preferences
model_prefs = []
if model_preferences:
    try:
        prefs_data = json.loads(model_preferences)
        model_prefs = [ModelPreference(**p) for p in prefs_data]
    except Exception as e:
        logger.error(f"Failed to parse model preferences: {e}")

# Call OR-Tools solver
from ..solver.partner_chain_solver import solve_partner_chain

chain_result = solve_partner_chain(
    person_id=person_id,
    partner_name=partner_name,
    office=office,
    smart_slots=smart_slots,
    candidate_vehicles_df=slot_vehicles,
    vehicle_scores=vehicle_scores_dict,
    model_preferences=model_prefs,
    preference_mode=preference_mode
)

if chain_result.status not in ['OPTIMAL', 'FEASIBLE']:
    raise HTTPException(
        status_code=400,
        detail=f"Could not find feasible chain: {chain_result.status}"
    )

# Format response
suggested_chain = chain_result.chain
```

**Testing:**
- ✅ Endpoint returns optimal chain
- ✅ Model preferences parsed correctly
- ✅ Preference modes work (prioritize, strict, ignore)
- ✅ Handles infeasible cases gracefully

**Commit Message:**
`"Integrate OR-Tools solver into /suggest-chain endpoint"`

---

### Phase 3: Frontend UI - Model Selection
**Estimated:** 4-5 days

#### Chunk 3.1: Model Selection Component ✅
**Files Created:**
- `frontend/src/components/ModelSelector.jsx`

**Component Structure:**
```jsx
<ModelSelector
  office={selectedOffice}
  onSelectionChange={(selectedModels) => setModelPreferences(selectedModels)}
  value={modelPreferences}
/>

// Returns:
// [
//   {make: "Honda", model: "Accord"},
//   {make: "Toyota", model: "Camry"}
// ]
```

**Features:**
- Search box (filter by make/model name)
- Checkbox tree:
  - Make level (expand/collapse)
  - Model level (checkboxes)
- Availability counts: "Honda Accord (5 available)"
- Selected tags display: `[Honda Accord ×] [Toyota Camry ×]`

**UI Layout:**
```jsx
<div className="model-selector">
  <input
    type="text"
    placeholder="🔍 Search make/model..."
    value={searchTerm}
  />

  <div className="selected-tags">
    {selectedModels.map(m => (
      <span key={`${m.make}-${m.model}`} className="tag">
        {m.make} {m.model}
        <button onClick={() => remove(m)}>×</button>
      </span>
    ))}
  </div>

  <div className="tree">
    {filteredMakes.map(make => (
      <div key={make} className="make-group">
        <label>
          <input
            type="checkbox"
            checked={isAllModelsSelected(make)}
            onChange={() => toggleMake(make)}
          />
          <span>{make} ({availableCount[make]} available)</span>
        </label>

        {expandedMakes.includes(make) && (
          <div className="models">
            {models[make].map(model => (
              <label key={model}>
                <input
                  type="checkbox"
                  checked={isSelected(make, model)}
                  onChange={() => toggle(make, model)}
                />
                <span>{model} ({availableCount[make][model]})</span>
              </label>
            ))}
          </div>
        )}
      </div>
    ))}
  </div>

  <div className="summary">
    {selectedModels.length} models selected
  </div>
</div>
```

**Commit Message:**
`"Add ModelSelector component with checkbox tree and search"`

---

#### Chunk 3.2: Integrate into ChainBuilder.jsx ✅
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**Changes:**
```jsx
// Add state for model preferences
const [modelPreferences, setModelPreferences] = useState([]);
const [preferenceMode, setPreferenceMode] = useState('prioritize');

// Only show in Partner Chain mode
{chainMode === 'partner' && (
  <div className="vehicle-preferences">
    <h3>🎯 Vehicle Preferences (Optional)</h3>

    <ModelSelector
      office={selectedOffice}
      onSelectionChange={setModelPreferences}
      value={modelPreferences}
    />

    <div className="preference-mode">
      <label>
        <input
          type="radio"
          checked={preferenceMode === 'prioritize'}
          onChange={() => setPreferenceMode('prioritize')}
        />
        Prioritize (boost score +800)
      </label>

      <label>
        <input
          type="radio"
          checked={preferenceMode === 'strict'}
          onChange={() => setPreferenceMode('strict')}
        />
        Strict (only these models)
      </label>

      <label>
        <input
          type="radio"
          checked={preferenceMode === 'ignore'}
          onChange={() => setPreferenceMode('ignore')}
        />
        Let AI decide (ignore preferences)
      </label>
    </div>
  </div>
)}
```

**Session Storage:**
```javascript
// Save preferences
sessionStorage.setItem(
  'chainbuilder_model_preferences',
  JSON.stringify(modelPreferences)
);
sessionStorage.setItem(
  'chainbuilder_preference_mode',
  preferenceMode
);

// Restore on load
useEffect(() => {
  const savedPrefs = sessionStorage.getItem('chainbuilder_model_preferences');
  if (savedPrefs) {
    setModelPreferences(JSON.parse(savedPrefs));
  }

  const savedMode = sessionStorage.getItem('chainbuilder_preference_mode');
  if (savedMode) {
    setPreferenceMode(savedMode);
  }
}, []);
```

**Commit Message:**
`"Integrate model preference UI into Partner Chain Builder"`

---

#### Chunk 3.3: Update API Call to Include Preferences ✅
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**Changes:**
```javascript
const generatePartnerChain = async () => {
  setIsGenerating(true);

  try {
    // Build query params
    const params = new URLSearchParams({
      person_id: selectedPartner.person_id,
      office: selectedOffice,
      start_date: startDate,
      num_vehicles: numVehicles,
      days_per_loan: daysPerLoan,
      preference_mode: preferenceMode
    });

    // Add model preferences as JSON string
    if (modelPreferences.length > 0 && preferenceMode !== 'ignore') {
      params.append(
        'model_preferences',
        JSON.stringify(modelPreferences)
      );
    }

    const response = await fetch(
      `/api/chain-builder/suggest-chain?${params}`
    );

    const data = await response.json();

    if (data.status === 'success') {
      setPartnerChain(data);
      // Show success message with preference info
      if (modelPreferences.length > 0) {
        const matchCount = data.suggested_chain.filter(v =>
          modelPreferences.some(p =>
            p.make === v.make && p.model === v.model
          )
        ).length;

        setMessage(
          `Chain generated! ${matchCount}/${data.suggested_chain.length} ` +
          `vehicles match your preferences.`
        );
      }
    } else {
      setError(data.detail || 'Failed to generate chain');
    }
  } catch (err) {
    setError(err.message);
  } finally {
    setIsGenerating(false);
  }
};
```

**Commit Message:**
`"Pass model preferences to backend in chain generation API call"`

---

### Phase 4: Availability Counting
**Estimated:** 2 days

#### Chunk 4.1: Availability Count Endpoint ✅
**Files Modified:**
- `backend/app/routers/chain_builder.py`

**New Endpoint:**
```python
@router.get("/model-availability")
async def get_model_availability(
    person_id: int = Query(...),
    office: str = Query(...),
    start_date: str = Query(...),
    num_vehicles: int = Query(4),
    days_per_loan: int = Query(7),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get availability counts by make/model for model selector UI.

    Returns:
        {
            "Honda": {
                "total": 12,
                "Accord": 5,
                "CR-V": 4,
                "Civic": 3
            },
            "Toyota": {
                "total": 8,
                "Camry": 3,
                "RAV4": 5
            }
        }
    """

    # Load data (vehicles, loan_history, activity, etc.)
    # ... same as suggest_chain ...

    # Get eligible vehicles (not reviewed, approved makes)
    exclusion_result = get_vehicles_not_reviewed(...)
    available_vins = exclusion_result['available_vins']

    # Build availability grid
    availability_grid = build_chain_availability_grid(...)

    # Count available vehicles by make/model
    availability_by_model = {}

    for make in vehicles_df[vehicles_df['vin'].isin(available_vins)]['make'].unique():
        make_vehicles = vehicles_df[
            (vehicles_df['vin'].isin(available_vins)) &
            (vehicles_df['make'] == make)
        ]

        availability_by_model[make] = {
            "total": len(make_vehicles)
        }

        for model in make_vehicles['model'].unique():
            model_vins = make_vehicles[make_vehicles['model'] == model]['vin']

            # Check if ANY slot can use this model
            available_count = 0
            for slot_idx in range(num_vehicles):
                slot_vins = get_available_vehicles_for_slot(...)
                if any(vin in slot_vins for vin in model_vins):
                    available_count += len([v for v in model_vins if v in slot_vins])
                    break  # Count once per model

            availability_by_model[make][model] = available_count

    return availability_by_model
```

**Commit Message:**
`"Add model availability count endpoint for UI"`

---

#### Chunk 4.2: Call Availability Endpoint from Frontend ✅
**Files Modified:**
- `frontend/src/components/ModelSelector.jsx`

**Changes:**
```jsx
const ModelSelector = ({ office, person_id, start_date, onSelectionChange, value }) => {
  const [availability, setAvailability] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load availability when office/partner changes
    const loadAvailability = async () => {
      if (!office || !person_id || !start_date) return;

      setLoading(true);
      try {
        const params = new URLSearchParams({
          person_id,
          office,
          start_date,
          num_vehicles: 4,
          days_per_loan: 7
        });

        const response = await fetch(
          `/api/chain-builder/model-availability?${params}`
        );
        const data = await response.json();
        setAvailability(data);
      } catch (err) {
        console.error('Failed to load availability:', err);
      } finally {
        setLoading(false);
      }
    };

    loadAvailability();
  }, [office, person_id, start_date]);

  return (
    <div className="model-selector">
      {loading ? (
        <div>Loading availability...</div>
      ) : (
        <div className="tree">
          {Object.keys(availability).map(make => (
            <div key={make}>
              <label>
                <input type="checkbox" />
                {make} ({availability[make].total} available)
              </label>
              {/* Render models with availability[make][model] counts */}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
```

**Commit Message:**
`"Display real-time availability counts in model selector"`

---

### Phase 5: Solver Diagnostics & Explanations
**Estimated:** 2 days

#### Chunk 5.1: Add Diagnostics to Solver ✅
**Files Modified:**
- `backend/app/solver/partner_chain_solver.py`

**New Function:**
```python
def explain_partner_chain_result(
    result: PartnerChainResult,
    all_candidates: pd.DataFrame,
    vehicle_scores: Dict[str, int],
    model_preferences: List[ModelPreference]
) -> Dict:
    """
    Explain why certain vehicles were/weren't selected.

    Returns:
        {
            "selected_vehicles": [
                {
                    "vin": "...",
                    "make": "Honda",
                    "model": "Accord",
                    "slot": 0,
                    "score": 1250,
                    "reason": "Highest-scoring preferred model"
                }
            ],
            "excluded_vehicles": [
                {
                    "vin": "...",
                    "make": "Audi",
                    "model": "A5",
                    "score": 1300,
                    "reason": "Model duplicate (Audi A5 already in slot 1)"
                }
            ],
            "preference_impact": {
                "preferred_count": 3,
                "total_count": 4,
                "boost_applied": "+2400 points"
            },
            "diversity_analysis": {
                "consecutive_penalties": 1,
                "make_distribution": {
                    "Honda": 2,
                    "Toyota": 1,
                    "Audi": 1
                }
            }
        }
    """
```

**Commit Message:**
`"Add diagnostics explaining solver decisions"`

---

#### Chunk 5.2: Display Diagnostics in UI ✅
**Files Modified:**
- `frontend/src/pages/ChainBuilder.jsx`

**Changes:**
```jsx
{partnerChain && partnerChain.diagnostics && (
  <div className="solver-diagnostics">
    <h3>🔍 Optimization Details</h3>

    <div className="preference-impact">
      <strong>Preference Match:</strong>
      {partnerChain.diagnostics.preference_impact.preferred_count}/
      {partnerChain.diagnostics.preference_impact.total_count} vehicles
      match your preferences
    </div>

    <div className="make-distribution">
      <strong>Make Distribution:</strong>
      {Object.entries(partnerChain.diagnostics.diversity_analysis.make_distribution)
        .map(([make, count]) => `${make} (${count})`)
        .join(', ')}
    </div>

    <button onClick={() => setShowFullDiagnostics(true)}>
      View Full Analysis
    </button>
  </div>
)}
```

**Commit Message:**
`"Display solver diagnostics in Chain Builder UI"`

---

### Phase 6: Testing & Polish
**Estimated:** 3 days

#### Chunk 6.1: Integration Tests ✅
**Files Created:**
- `backend/tests/test_partner_chain_solver.py`

**Test Cases:**
```python
def test_solver_basic_chain():
    """4-vehicle chain, no preferences"""

def test_solver_with_preferences_prioritize():
    """Preferred models boosted but not required"""

def test_solver_with_preferences_strict():
    """ONLY preferred models allowed"""

def test_solver_insufficient_preferred():
    """Strict mode fails if not enough preferred vehicles"""

def test_solver_diversity():
    """No 3+ consecutive same make"""

def test_solver_no_duplicate_models():
    """Each model used at most once"""

def test_solver_availability_constraints():
    """Vehicles available during slots"""

def test_solver_performance():
    """Solves in <5 seconds with 100 candidates"""
```

**Commit Message:**
`"Add comprehensive integration tests for Partner Chain solver"`

---

#### Chunk 6.2: Regression Testing ✅
**Manual Testing:**
- [ ] Existing Partner Chain manual mode still works
- [ ] Vehicle Chain mode unaffected
- [ ] Optimizer unaffected
- [ ] Calendar displays chains correctly
- [ ] Session storage persists preferences
- [ ] No console errors

**Commit Message:**
`"Verify no regressions in existing Chain Builder functionality"`

---

#### Chunk 6.3: Performance Optimization ✅
**Areas to Optimize:**
- Cache availability grid (don't rebuild per API call)
- Batch model availability queries
- Solver timeout handling (fallback to greedy if OR-Tools times out)

**Commit Message:**
`"Optimize Partner Chain solver performance and error handling"`

---

## UI/UX Design

### Full Partner Chain UI (Updated)

```
┌──────────────────────────────────────────────────────────────────┐
│  [ Partner Chain ]  [ Vehicle Chain ]  ← Tabs                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 🎯 PARTNER CHAIN BUILDER                                   │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │                                                             │  │
│  │  Partner: [LA Times ▼]                                     │  │
│  │  Office: Los Angeles                                       │  │
│  │  Start Date: [Nov 3, 2025]                                 │  │
│  │  # Vehicles: [4 ▼]   Days per Loan: [8 ▼]                 │  │
│  │                                                             │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │  │
│  │                                                             │  │
│  │  🎯 Vehicle Preferences (Optional) ← NEW!                  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │ 🔍 Search: [Honda______]                           │  │  │
│  │  │                                                      │  │  │
│  │  │ Selected (3): [Honda Accord ×] [Honda CR-V ×]      │  │  │
│  │  │               [Toyota Camry ×]                      │  │  │
│  │  │                                                      │  │  │
│  │  │ Available Models:                                   │  │  │
│  │  │ ┌────────────────────────────────────────────────┐ │  │  │
│  │  │ │ ☑ Honda (12 available)          [Expand ▼]    │ │  │  │
│  │  │ │   ├─ ☑ Accord (5)                             │ │  │  │
│  │  │ │   ├─ ☑ CR-V (4)                               │ │  │  │
│  │  │ │   └─ ☐ Civic (3)                              │ │  │  │
│  │  │ │                                                │ │  │  │
│  │  │ │ ☐ Toyota (8 available)          [Expand ▼]    │ │  │  │
│  │  │ │   ├─ ☑ Camry (3)                              │ │  │  │
│  │  │ │   └─ ☐ RAV4 (5)                               │ │  │  │
│  │  │ │                                                │ │  │  │
│  │  │ │ ☐ Audi (6 available)            [Expand ▶]    │ │  │  │
│  │  │ │ ☐ Genesis (4 available)         [Expand ▶]    │ │  │  │
│  │  │ └────────────────────────────────────────────────┘ │  │  │
│  │  │                                                      │  │  │
│  │  │ [Clear All] [Select Popular]                        │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                             │  │
│  │  Preference Mode:                                          │  │
│  │  ● Prioritize (boost score +800)                          │  │
│  │  ○ Strict (only these models)                             │  │
│  │  ○ Let AI decide (ignore preferences)                     │  │
│  │                                                             │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │  │
│  │                                                             │  │
│  │  Build Mode:                                               │  │
│  │  ● Auto-Generate (OR-Tools Optimized) ← UPGRADED!         │  │
│  │  ○ Manual Build                                            │  │
│  │                                                             │  │
│  │  [Generate Optimized Chain]                                │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 🔍 Optimization Results                                    │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │                                                             │  │
│  │ ✅ Chain Generated!                                        │  │
│  │ Preference Match: 3/4 vehicles match your preferences      │  │
│  │ Make Distribution: Honda (2), Toyota (1), Audi (1)         │  │
│  │ Total Score: 4,850 points                                  │  │
│  │ Solver Time: 1.2 seconds                                   │  │
│  │                                                             │  │
│  │ [View Full Analysis]                                       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 📅 Chain Timeline                                          │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │                                                             │  │
│  │ [Green bars showing proposed chain on calendar timeline]   │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 🚗 Chain Vehicles                                          │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │                                                             │  │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │  │
│  │ │ Slot 1   │ │ Slot 2   │ │ Slot 3   │ │ Slot 4   │      │  │
│  │ │ A+       │ │ A        │ │ A+       │ │ A        │      │  │
│  │ │──────────│ │──────────│ │──────────│ │──────────│      │  │
│  │ │Honda     │ │Toyota    │ │Honda     │ │Audi      │      │  │
│  │ │Accord    │ │Camry     │ │CR-V      │ │A5        │      │  │
│  │ │2025      │ │2024      │ │2025      │ │2024      │      │  │
│  │ │          │ │          │ │          │ │          │      │  │
│  │ │Nov 3-11  │ │Nov 15-23 │ │Nov 27-   │ │Dec 5-13  │      │  │
│  │ │          │ │          │ │Dec 5     │ │          │      │  │
│  │ │Score:1250│ │Score:1180│ │Score:1220│ │Score:1200│      │  │
│  │ │✅ Prefer │ │✅ Prefer │ │✅ Prefer │ │          │      │  │
│  │ │          │ │          │ │          │ │          │      │  │
│  │ │[Change ▼]│ │[Change ▼]│ │[Change ▼]│ │[Change ▼]│      │  │
│  │ │[Delete]  │ │[Delete]  │ │[Delete]  │ │[Delete]  │      │  │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  [Save Chain (Manual)] [Save & Request (Send to FMS)]             │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## API Specifications

### Modified Endpoints

#### GET /chain-builder/suggest-chain (MODIFIED)

**Query Parameters:**
```
person_id: int (required)
office: str (required)
start_date: str (required, YYYY-MM-DD)
num_vehicles: int (default 4, range 1-10)
days_per_loan: int (default 7, range 1-14)
model_preferences: str (optional, JSON array)
  Example: '[{"make":"Honda","model":"Accord"},{"make":"Toyota","model":"Camry"}]'
preference_mode: str (default "prioritize", options: "prioritize" | "strict" | "ignore")
```

**Response:**
```json
{
  "status": "success",
  "partner_info": {
    "person_id": 1523,
    "name": "LA Times",
    "office": "Los Angeles"
  },
  "chain_params": {
    "start_date": "2025-11-03",
    "num_vehicles": 4,
    "days_per_loan": 8,
    "total_span_days": 35
  },
  "suggested_chain": [
    {
      "slot": 1,
      "vin": "1HGBH41JXMN109186",
      "make": "Honda",
      "model": "Accord",
      "year": "2025",
      "start_date": "2025-11-03",
      "end_date": "2025-11-11",
      "score": 1250,
      "tier": "A+",
      "is_preferred": true
    }
  ],
  "optimization_stats": {
    "solver_status": "OPTIMAL",
    "solver_time_ms": 1245,
    "total_score": 4850,
    "candidates_considered": 87,
    "preferred_match_count": 3,
    "diversity_penalty": 150
  },
  "diagnostics": {
    "preference_impact": {
      "preferred_count": 3,
      "total_count": 4,
      "boost_applied": "+2400"
    },
    "diversity_analysis": {
      "consecutive_penalties": 1,
      "make_distribution": {
        "Honda": 2,
        "Toyota": 1,
        "Audi": 1
      }
    }
  }
}
```

---

#### GET /chain-builder/model-availability (NEW)

**Query Parameters:**
```
person_id: int (required)
office: str (required)
start_date: str (required)
num_vehicles: int (default 4)
days_per_loan: int (default 7)
```

**Response:**
```json
{
  "Honda": {
    "total": 12,
    "Accord": 5,
    "CR-V": 4,
    "Civic": 3
  },
  "Toyota": {
    "total": 8,
    "Camry": 3,
    "RAV4": 5
  },
  "Audi": {
    "total": 6,
    "A5": 3,
    "Q5": 3
  }
}
```

---

## Testing Strategy

### Unit Tests (Backend)

**File:** `backend/tests/test_partner_chain_solver.py`

```python
def test_solver_basic_chain():
    """Generate 4-vehicle chain with no preferences"""
    result = solve_partner_chain(
        person_id=1523,
        smart_slots=[...],
        candidate_vehicles_df=vehicles_df,
        vehicle_scores=scores
    )
    assert result.status == 'OPTIMAL'
    assert len(result.chain) == 4
    assert all_unique_models(result.chain)

def test_solver_preferences_prioritize():
    """Preferred models boosted"""
    prefs = [
        ModelPreference(make="Honda", model="Accord"),
        ModelPreference(make="Toyota", model="Camry")
    ]
    result = solve_partner_chain(..., model_preferences=prefs, preference_mode="prioritize")
    preferred_count = sum(1 for v in result.chain if is_preferred(v, prefs))
    assert preferred_count >= 2  # Should favor preferred

def test_solver_preferences_strict():
    """Only preferred models allowed"""
    prefs = [ModelPreference(make="Honda", model="Accord")]
    result = solve_partner_chain(..., model_preferences=prefs, preference_mode="strict")
    assert all(v['make'] == 'Honda' and v['model'] == 'Accord' for v in result.chain)

def test_solver_diversity():
    """No 3+ consecutive same make"""
    result = solve_partner_chain(...)
    for i in range(len(result.chain) - 2):
        makes = [result.chain[i]['make'], result.chain[i+1]['make'], result.chain[i+2]['make']]
        assert not (makes[0] == makes[1] == makes[2])

def test_solver_performance():
    """Solves in <5 seconds with 100 candidates"""
    start = time.time()
    result = solve_partner_chain(..., candidate_vehicles_df=large_df)
    elapsed = time.time() - start
    assert elapsed < 5.0
    assert result.status in ['OPTIMAL', 'FEASIBLE']
```

---

### Integration Tests (Full Stack)

**Manual Test Cases:**

1. **Happy Path - Prioritize Mode**
   - Select partner: LA Times
   - Select 3 models: Honda Accord, Honda CR-V, Toyota Camry
   - Mode: Prioritize
   - Expected: Chain has >=2 preferred models

2. **Strict Mode - Sufficient**
   - Select partner: LA Times
   - Select 6 models (enough availability)
   - Mode: Strict
   - Expected: All 4 slots use preferred models

3. **Strict Mode - Insufficient**
   - Select partner: LA Times
   - Select 1 model: Genesis G90 (only 2 available)
   - Mode: Strict, 4 vehicles
   - Expected: Error "Not enough preferred vehicles available"

4. **Ignore Mode**
   - Select preferences but choose "Let AI decide"
   - Expected: Preferences ignored, optimizer picks best vehicles

5. **Session Persistence**
   - Select preferences
   - Refresh page
   - Expected: Preferences restored

6. **Availability Counts**
   - Change start date
   - Expected: Availability counts update dynamically

---

### Performance Benchmarks

**Target Metrics:**
- OR-Tools solver: <5 seconds (4-6 vehicles, 50-100 candidates)
- Model availability endpoint: <2 seconds
- UI model selector load: <1 second
- Full chain generation (API + UI): <8 seconds

---

## Rollback Strategy

### Phase-by-Phase Rollback

Each phase is independently committable. If issues found:

```bash
# Rollback last phase
git revert HEAD~N  # N = number of commits in phase

# Or cherry-pick successful chunks
git cherry-pick <chunk-hash>
```

### Feature Flag (Optional)

Add flag to enable/disable OR-Tools solver:

```python
# backend/app/config.py
USE_ORTOOLS_PARTNER_CHAIN = os.getenv('USE_ORTOOLS_PARTNER_CHAIN', 'true') == 'true'

# In suggest_chain():
if USE_ORTOOLS_PARTNER_CHAIN:
    result = solve_partner_chain(...)  # New OR-Tools
else:
    result = greedy_chain_selection(...)  # Old greedy (keep as backup)
```

---

## Success Criteria

### Feature Complete Checklist

- [ ] OR-Tools solver for Partner Chain implemented
- [ ] Model preference UI with checkbox tree
- [ ] Preference modes work (prioritize, strict, ignore)
- [ ] Availability counts display correctly
- [ ] Session storage persists preferences
- [ ] Chain generation uses OR-Tools (not greedy)
- [ ] Solver diagnostics explain decisions
- [ ] No duplicate models in chain
- [ ] No 3+ consecutive same make
- [ ] Integration tests pass
- [ ] Performance targets met (<5 sec solver)
- [ ] No regressions in existing features
- [ ] Documentation updated

---

## Timeline Estimate

**Total Duration:** 3-4 weeks

| Phase | Duration | Description |
|-------|----------|-------------|
| Phase 1 | 3-5 days | Backend OR-Tools solver |
| Phase 2 | 2-3 days | API integration |
| Phase 3 | 4-5 days | Frontend UI (model selector) |
| Phase 4 | 2 days | Availability counting |
| Phase 5 | 2 days | Diagnostics & explanations |
| Phase 6 | 3 days | Testing & polish |

**Buffer:** 3-5 days for unexpected issues

---

## Future Enhancements (Post-Launch)

1. **Preference Templates**
   - Save common preference sets to database
   - "Honda Preference Set", "Luxury Set", "EV Set"
   - Quick-apply saved templates

2. **Smart Suggestions**
   - Historical analysis: "LA Times published 12 articles about Honda Accord"
   - Auto-suggest: "Based on history, recommend: Accord, CR-V, Civic"

3. **A/B Testing**
   - Run OR-Tools and greedy in parallel
   - Compare quality scores and user satisfaction
   - Data-driven decision on which is better

4. **Multi-Objective Sliders**
   - Quality weight vs Diversity weight
   - Similar to Vehicle Chain's distance weight slider
   - User controls tradeoff: "Perfect diversity" vs "Highest quality"

---

## Questions & Answers

### Q: Why OR-Tools instead of improving greedy?
**A:** Greedy = locally optimal. OR-Tools = globally optimal. With model preferences and diversity constraints, OR-Tools finds better solutions by considering all slots simultaneously.

### Q: Will this slow down chain generation?
**A:** OR-Tools adds ~2-4 seconds (vs <1 sec greedy). But benefit of better chains outweighs cost. Also, already proven fast enough in Vehicle Chain.

### Q: What if partner has no preferred models available?
**A:**
- **Prioritize mode:** Falls back to best available vehicles
- **Strict mode:** Returns error "Not enough preferred models available"

### Q: Can preferences be saved per partner?
**A:** Not in initial version (session storage only). Phase 2 enhancement will add database-backed templates.

---

**END OF PARTNER CHAIN OR-TOOLS MIGRATION PLAN**
