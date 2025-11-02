# ChainBuilder.jsx UI Refactor - Execution Plan

**Goal:** Transform from 3-column layout to vertical stack with compact parameter grid
**File:** frontend/src/pages/ChainBuilder.jsx (3707 lines)
**Approach:** Surgical refactoring - move sections, keep all logic intact

---

## Current Structure (Lines 1803-3700)

```
<div className="flex h-full">                    ← Line 1803

  <div className="w-80">                          ← Line 1805 LEFT PANEL
    <h2>Chain Parameters</h2>

    {chainMode === 'partner' && (
      - Partner Selector (dropdown with search)
      - Start Date input
      - Number of Vehicles input
      - Days per Loan input
      - Make Filter (checkboxes)
      - ModelSelector (NEW - collapsible)
      - Preference Mode (radio buttons)
      - Build Mode (Auto/Manual toggle)
      - Generate Button
    )}

    {chainMode === 'vehicle' && (
      - Vehicle Selector (dropdown with search)
      - Start Date input
      - Number of Partners input
      - Days per Loan input
      - Distance Weight slider
      - Build Mode (Auto/Manual toggle)
      - Generate Button
    )}
  </div>

  <div className="flex-1">                        ← CENTER PANEL
    - Timeline Calendar
    - Chain Cards Display (current big squares)
  </div>

  <div className="w-80">                          ← RIGHT PANEL
    - Partner Intelligence
    - Budget Display
  </div>
</div>
```

---

## Target Structure (New)

```
<div className="flex flex-col gap-6 p-6">

  {/* SECTION 1: CALENDAR - Full Width */}
  <div className="bg-white rounded-lg border p-4">
    - Timeline Calendar (from center panel)
    - Full width, ~400px height
  </div>

  {/* SECTION 2: CHAIN CARDS - Full Width (shows after generation) */}
  {manualSlots.length > 0 && (
    <div className="bg-white rounded-lg border p-4">
      <h3>Generated Chain</h3>
      - Compact cards: 180px × 100px
      - 5 per row
      - (from center panel, restyled)
    </div>
  )}

  {/* SECTION 3: PARAMETERS - Full Width, Compact Grid */}
  <div className="bg-white rounded-lg border p-6">
    <h3>Chain Parameters</h3>

    {/* Row 1: Basic inputs in 5-column grid */}
    <div className="grid grid-cols-5 gap-3">
      <div>Partner/Vehicle selector</div>
      <div>Office (read-only display)</div>
      <div>Start Date</div>
      <div># Vehicles/Partners</div>
      <div>Days per Loan</div>
    </div>

    {/* Row 2: Build Mode + Generate Button */}
    <div className="grid grid-cols-2 gap-3">
      <div>Build Mode: ● Auto ○ Manual</div>
      <div>[Generate Optimized Chain] button</div>
    </div>

    {/* Row 3: Model Preferences (Partner Chain) - Collapsible */}
    {chainMode === 'partner' && (
      <details className="border-t pt-4">
        <summary>🎯 Vehicle Preferences (Optional)</summary>
        <ModelSelector /> (wider: 700px)
        <Preference Mode radio buttons>
      </details>
    )}

    {/* Row 3: Distance Weight (Vehicle Chain) */}
    {chainMode === 'vehicle' && (
      <div>Distance Weight slider</div>
    )}
  </div>

  {/* SECTION 4: BUDGET/INTELLIGENCE - Full Width */}
  <div className="bg-white rounded-lg border p-4">
    - Partner Intelligence (from right panel)
    - Budget Display (from right panel)
  </div>

</div>
```

---

## Execution Steps

### Step 1: Change Main Container (Line 1803)
```jsx
BEFORE:
<div className="flex h-full">

AFTER:
<div className="flex flex-col gap-6 p-6">
```

### Step 2: Extract Calendar from Center Panel
- Find timeline calendar JSX (currently in center panel)
- Move to Section 1 (new top section)
- Keep full width

### Step 3: Extract Chain Cards from Center Panel
- Find manualSlots.map() rendering
- Move to Section 2
- Restyle cards: 180px × 100px, 5 per row

### Step 4: Reorganize Left Panel Parameters into Grid
- Keep all existing inputs
- Arrange in grid-cols-5 for row 1
- Arrange in grid-cols-2 for row 2
- Reduce label font sizes (text-xs)
- Reduce spacing

### Step 5: Move Right Panel Content to Bottom
- Partner Intelligence
- Budget Display
- Make full width

### Step 6: Make ModelSelector Collapsible
- Wrap in <details> tag
- Default collapsed
- Expand to 700px wide

---

## Key Principles

1. **Keep ALL existing logic** - No functional changes
2. **Keep ALL existing state** - No state refactoring
3. **Keep ALL existing functions** - No function changes
4. **Only change JSX layout** - Visual reorganization only

---

## Risk Mitigation

- Work in small edits
- Test after each major section move
- Keep git ready to revert if needed
- Don't change variable names or logic

---

**Ready to execute?** Or do you want to review this plan first?
