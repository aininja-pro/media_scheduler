# Chain Builder v2 - Manual Vehicle Selection

## Current State (v1 - Completed)
The Chain Builder automatically suggests vehicles for each slot in a chain using optimizer scoring logic.

**What works:**
- Smart gap-finding (works around existing commitments)
- Model diversity enforcement (no duplicate make+model)
- VIN exclusion (partner history)
- Make filtering with checkboxes
- Save/delete chains
- Timeline visualization

**Limitation:**
- Scheduler has no choice in which specific vehicles are assigned
- Can only swap vehicles one at a time after generation (tedious)

---

## Requested Enhancement (v2)

### **Goal**: Give schedulers dropdown selection for each slot

### **User Story**:
Rafael (scheduler) wants to build a 7-vehicle chain for Amy Clemens:
1. Selects Amy, picks start date Nov 4, requests 7 vehicles
2. System calculates 7 slot dates (Nov 4-11, Nov 12-19, ..., Nov 60-67)
3. **NEW**: For each slot, shows dropdown of 20-40 eligible vehicles
4. Rafael manually picks: Slot 1 → Toyota Camry, Slot 2 → Honda Accord, etc.
5. Saves chain with his hand-picked vehicles

### **Why This Matters**:
- Rafael knows his partners personally
- Wants brand diversity (not 5 Toyotas in a row)
- Sees ALL available options without guessing
- Faster than current FMS (no back-and-forth searching)

---

## Two Modes to Support

### **Mode 1: Auto-Generate** (current behavior - keep as-is)
- "Generate Chain" button
- System picks best vehicles automatically
- Great for quick suggestions

### **Mode 2: Manual Build** (new feature)
- "Manual Build" button
- System generates **empty slots with dates**
- Each slot shows dropdown of eligible vehicles
- Scheduler picks from dropdown for each slot
- Full control over vehicle selection

---

## Technical Requirements

### **Backend Changes**

#### New Endpoint: `/api/chain-builder/get-slot-options`
```python
GET /api/chain-builder/get-slot-options
  ?person_id=421
  &office=Los Angeles
  &start_date=2025-11-04
  &num_vehicles=7
  &days_per_loan=8
  &slot_index=0  # Which slot (0-6)
  &preferred_makes=Toyota,Honda  # Optional

Returns:
{
  "slot": {
    "index": 0,
    "start_date": "2025-11-04",
    "end_date": "2025-11-11"
  },
  "eligible_vehicles": [
    {
      "vin": "1234ABC",
      "make": "Toyota",
      "model": "Camry",
      "trim": "XLE",
      "year": "2025",
      "score": 1158,
      "tier": "A+",
      "last_4_vin": "4ABC"
    },
    ...  # 20-40 vehicles
  ],
  "total_eligible": 41
}
```

**Logic**:
- Reuse existing availability checking
- Filter to vehicles available for this slot's date range
- Exclude vehicles already picked in previous slots
- Sort by score (best first)
- Return top 50 or all

---

### **Frontend Changes**

#### Manual Build UI Flow:

**Step 1**: Click "Manual Build" button
- Calls smart scheduling to get slot dates
- Shows 7 empty slot cards with dates

**Step 2**: Each slot card shows:
```
┌─────────────────────────────┐
│ Slot 1 │ Nov 4-11 │ [A+ Tier] │
├─────────────────────────────┤
│ Select Vehicle:             │
│ [Dropdown: 41 vehicles ▼]   │
│                             │
│ Selected: (none)            │
└─────────────────────────────┘
```

**Step 3**: Click dropdown → shows scrollable list:
```
Select Vehicle for Slot 1
┌──────────────────────────────────┐
│ 🔍 Search...                     │
├──────────────────────────────────┤
│ ○ Toyota Camry XLE - 4352  (A+)  │ ← Score: 1158
│ ○ Honda Accord Sport - 7891 (A+) │ ← Score: 1142
│ ○ Mazda CX-90 Turbo - 3456  (A)  │ ← Score: 920
│ ... (38 more)                    │
└──────────────────────────────────┘
```

**Step 4**: After selecting for all slots → "Save Chain" button activates

**Step 5**: Save → writes to `scheduled_assignments`

---

## UI Mockup

### Manual Build Panel:
```
┌─────────────────────────────────────────────────────┐
│ Chain Builder - Manual Mode                        │
├─────────────────────────────────────────────────────┤
│ Media Partner: Amy Clemens                          │
│ Start Date: Nov 4, 2025                             │
│ Vehicles: 7 | Days per: 8                           │
│                                                     │
│ [Auto-Generate]  [Manual Build] ← Mode toggle      │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌─────────────────┐ ┌─────────────────┐           │
│ │ Slot 1          │ │ Slot 2          │           │
│ │ Nov 4-11        │ │ Nov 12-19       │           │
│ │ [Select ▼] 41   │ │ [Select ▼] 40   │           │
│ │ Toyota Camry    │ │ Honda Accord    │           │
│ └─────────────────┘ └─────────────────┘           │
│                                                     │
│ ┌─────────────────┐ ┌─────────────────┐           │
│ │ Slot 3          │ │ Slot 4          │           │
│ │ Nov 20-27       │ │ Nov 28-Dec 5    │           │
│ │ [Select ▼] 38   │ │ [Select ▼] 42   │           │
│ │ (not selected)  │ │ (not selected)  │           │
│ └─────────────────┘ └─────────────────┘           │
│                                                     │
│ ... (3 more slots)                                  │
│                                                     │
│ [Save Chain] ← Only active when all slots filled   │
└─────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### **Phase 1: Backend API** (2-3 hours)
1. Create `/get-slot-options` endpoint
2. Reuse existing availability + scoring logic
3. Return sorted list of eligible vehicles per slot
4. Add endpoint to save manually-selected chain

### **Phase 2: Frontend Manual Mode** (3-4 hours)
1. Add "Auto-Generate" / "Manual Build" toggle buttons
2. Manual Build: Generate empty slot cards with dates
3. Each card has searchable dropdown of eligible vehicles
4. Show vehicle count badge ("41 vehicles")
5. Disable Save until all slots have selections

### **Phase 3: Integration** (1-2 hours)
1. Validate no duplicate VINs across slots
2. Handle slot deletion (regenerate options)
3. Show loading states while fetching options
4. Success messages and error handling

---

## Edge Cases to Handle

1. **Slot has 0 eligible vehicles** (all reviewed/unavailable)
   - Show "No vehicles available" message
   - Suggest adjusting dates or make filters

2. **Partner changes mind mid-build**
   - Allow "Clear All Selections" button
   - Or switch back to Auto-Generate mode

3. **Vehicle becomes unavailable** (someone else booked it)
   - Validation on save
   - Show error, let them re-pick

4. **Too many vehicles to show** (>100)
   - Show top 50 by score
   - Add "Show More" button or pagination

---

## Success Metrics

✅ Rafael can build a 7-vehicle chain in **under 2 minutes**
✅ He has **full visibility** into what's available
✅ **No more blind swapping** - sees all options upfront
✅ Maintains **all business rules** (cooldown, diversity, availability)

---

## Questions for Next Session

1. Should dropdowns show **all eligible vehicles** or just **top 50**?
2. Do we need vehicle photos/details in dropdown, or just Make/Model/VIN?
3. Should we allow **partial chain saves** (e.g., fill 4 slots, save, fill rest later)?
4. Keep both modes or just Manual Build (most flexible)?

---

**Status**: Ready to implement. Estimated 6-8 hours total development time.
