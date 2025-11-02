# Chain Builder UI Redesign - Compact Layout

**Date:** 2025-11-01
**Status:** Design Approved - Ready for Implementation
**Applies To:** Both Partner Chain AND Vehicle Chain tabs

---

## Design Goals

1. **Full-width calendar** - Primary context, easier to read
2. **Compact chain cards** - Rectangular, not big squares
3. **Logical top-down flow** - Calendar → Chain → Parameters
4. **Consistent design** - Same layout for both tabs
5. **Less scrolling** - Everything visible on one screen

---

## New Layout Structure

```
┌──────────────────────────────────────────────────────────────────┐
│  [ Partner Chain ]  [ Vehicle Chain ]  ← Tabs                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 📅 TIMELINE CALENDAR (Full Width, ~400px height)           │  │
│  │                                                             │  │
│  │ [Partner: LA Times]    [< Oct 2025] [Nov 2025] [Dec 2025 >]│  │
│  │                                                             │  │
│  │ [Calendar grid with colored bars]                          │  │
│  │ BLUE = Active | GREEN = Planned | MAGENTA = Requested      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 🚗 GENERATED CHAIN (Appears after generate, ~150px height) │  │
│  │ ────────────────────────────────────────────────────────── │  │
│  │ 4 vehicles | 2/4 match preferences | Total Score: 2950     │  │
│  │                                                             │  │
│  │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐               │  │
│  │ │1  A+✅ │ │2  A    │ │3  A    │ │4  A+✅ │               │  │
│  │ │Honda   │ │Toyota  │ │Audi    │ │Genesis │               │  │
│  │ │Accord  │ │Camry   │ │A5      │ │G90     │               │  │
│  │ │2025    │ │2024    │ │2024    │ │2025    │               │  │
│  │ │Nov 3-10│ │Nov10-17│ │Nov17-24│ │Nov24-  │               │  │
│  │ │        │ │        │ │        │ │Dec 1   │               │  │
│  │ │⭐850   │ │⭐720   │ │⭐680   │ │⭐700   │               │  │
│  │ │[Edit▼] │ │[Edit▼] │ │[Edit▼] │ │[Edit▼] │               │  │
│  │ └────────┘ └────────┘ └────────┘ └────────┘               │  │
│  │                                                             │  │
│  │ [Save Chain] [Save & Request] [Clear Chain]               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ ⚙️ CHAIN PARAMETERS (Always visible, moves down)          │  │
│  │ ────────────────────────────────────────────────────────── │  │
│  │                                                             │  │
│  │ Partner: [LA Times ▼]       Start Date: [Nov 3, 2025]     │  │
│  │ Office: Los Angeles         # Vehicles: [4 ▼]             │  │
│  │ Days per Loan: [8 ▼]        Build Mode: ● Auto  ○ Manual  │  │
│  │                                                             │  │
│  │ 🎯 Vehicle Preferences (Collapsible)                       │  │
│  │ [▼ Expand to select models...]                             │  │
│  │                                                             │  │
│  │ [Generate Optimized Chain]                                 │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Card Design - Compact Rectangular

### Dimensions:
- **Width:** ~180px (fits 4-5 cards per row on standard screen)
- **Height:** ~120px (vs current ~250px - 50% smaller!)
- **Border:** 2px solid (green if filled, gray if empty)
- **Padding:** 8px (vs current 16px)
- **Font size:** 11-12px (vs current 14px)

### Card Content (Compact):

**Partner Chain Card:**
```
┌────────────────┐
│ 1  A+ ✅       │  ← Slot number, tier badge, preferred checkmark
│ Honda Accord   │  ← Make + Model (bold)
│ 2025           │  ← Year (gray)
│ Nov 3 - Nov 10 │  ← Dates (compact format)
│ ⭐ 850         │  ← Score
│ [Change ▼]     │  ← Edit dropdown (small)
└────────────────┘
```

**Vehicle Chain Card:**
```
┌────────────────┐
│ 1  A+ ✅       │  ← Slot number, tier badge, preferred checkmark
│ LA Times       │  ← Partner name (bold)
│ 123 Main St    │  ← Address (truncated, gray, small)
│ Nov 3 - Nov 10 │  ← Dates
│ 3.2 mi | ⭐750 │  ← Distance + Score
│ [Change ▼]     │  ← Edit dropdown
└────────────────┘
```

### Card Colors:
- **Border:** Green (#10b981) when filled, Gray (#d1d5db) when empty
- **Background:** White when filled, light gray (#f9fafb) when empty
- **Preferred:** Gold star ✅ badge in top-right
- **Hover:** Subtle shadow

---

## Implementation Changes

### 1. Remove Left/Right Panel Split

**Current:**
```jsx
<div className="flex gap-4">
  <div className="w-1/3">Left Panel</div>
  <div className="w-2/3">Right Panel</div>
</div>
```

**New:**
```jsx
<div className="flex flex-col gap-4">
  <div className="w-full">Calendar</div>
  {chain && <div className="w-full">Chain Cards</div>}
  <div className="w-full">Parameters</div>
</div>
```

### 2. Compact Card CSS

```css
.chain-card {
  width: 180px;
  height: 120px;
  padding: 8px;
  border: 2px solid #d1d5db;
  border-radius: 6px;
  background: white;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
}

.chain-card.filled {
  border-color: #10b981;
}

.chain-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.chain-card-title {
  font-size: 13px;
  font-weight: 700;
  color: #1f2937;
}

.chain-card-subtitle {
  font-size: 10px;
  color: #6b7280;
}

.chain-card-dates {
  font-size: 11px;
  color: #374151;
}

.chain-card-score {
  font-size: 11px;
  font-weight: 600;
  color: #059669;
}
```

### 3. Parameters Layout (Horizontal Grid)

```jsx
<div className="grid grid-cols-3 gap-4">
  <div>
    <label>Partner</label>
    <select>{partners}</select>
  </div>
  <div>
    <label>Start Date</label>
    <input type="date" />
  </div>
  <div>
    <label># Vehicles</label>
    <select>4, 5, 6</select>
  </div>
</div>

<div className="grid grid-cols-3 gap-4">
  <div>
    <label>Office</label>
    <div>Los Angeles</div>
  </div>
  <div>
    <label>Days per Loan</label>
    <select>7, 8, 9, 10</select>
  </div>
  <div>
    <label>Build Mode</label>
    <div>● Auto  ○ Manual</div>
  </div>
</div>
```

---

## Visual Flow

### Before Generation:
```
┌─────────────────┐
│ 📅 Calendar     │  ← Full width, 400px
└─────────────────┘
┌─────────────────┐
│ ⚙️ Parameters   │  ← Full width, ~300px
│ [Generate]      │
└─────────────────┘
```

### After Generation:
```
┌─────────────────┐
│ 📅 Calendar     │  ← Full width, 400px
└─────────────────┘
┌─────────────────┐
│ 🚗 Chain Cards  │  ← NEW! Appears here, ~150px
│ [Save] [Clear]  │
└─────────────────┘
┌─────────────────┐
│ ⚙️ Parameters   │  ← Pushed down, still visible
└─────────────────┘
```

---

## Implementation Plan

### Step 1: Remove Grid Split
- Remove `<div className="grid grid-cols-3">` wrapper
- Make everything full-width stacked

### Step 2: Redesign Chain Cards
- Reduce card size: 180px × 120px
- Compact fonts: 11-12px
- Horizontal layout: 4-5 cards per row
- Add preferred ✅ badge

### Step 3: Horizontal Parameters
- Grid layout: 3 columns
- Inline labels
- Compact spacing

### Step 4: Apply to Both Tabs
- Partner Chain: Vehicle cards
- Vehicle Chain: Partner cards (with distance)

---

## Questions Before I Start:

1. **Card height:** ~120px good, or shorter (100px)?
2. **Cards per row:** 4 cards (with gaps) or 5 cards (tighter)?
3. **ModelSelector:** Keep expandable or make more compact too?
4. **Generate button:** Keep at bottom or move to top near calendar?

Let me know and I'll start coding!
