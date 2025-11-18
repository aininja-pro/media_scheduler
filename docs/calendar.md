# Calendar

The Calendar view provides a visual timeline for viewing, managing, and editing vehicle assignments.

## Overview

Calendar displays assignments across time with:

- Color-coded status indicators
- Drag-and-drop rescheduling
- Context windows for details
- Filtering and search capabilities

## Layout

### Timeline View

The main area shows assignments as bars on a timeline:

- Horizontal axis: Dates
- Vertical axis: Partners or Vehicles (depending on view mode)
- Bar length: Assignment duration

### View Modes

Toggle between:

| Mode | Shows |
|------|-------|
| **By Partner** | Partners on Y-axis, their vehicles over time |
| **By Vehicle** | Vehicles on Y-axis, their partners over time |

### Date Range

Use the date picker to:

- Select start and end dates
- Jump to specific weeks
- Use quick presets (This Week, Next Week, This Month)

## Assignment Status Colors

| Color | Status | Description |
|-------|--------|-------------|
| **Green** | Planned | Created in scheduler, not yet sent to FMS |
| **Magenta** | Requested | Sent to FMS, awaiting approval |
| **Blue** | Active | Approved by FMS, confirmed loan |
| **Gray** | Completed | Historical assignment |

## Viewing Assignments

### Click for Details

Click any assignment to open the details panel:

- Vehicle information (make, model, VIN)
- Partner information (name, tier, contact)
- Dates (start, end, duration)
- Status and actions
- Cost estimate
- FMS request ID (if applicable)

### Context Windows

**Vehicle Context** (click vehicle name):

- Recent assignment history
- Publication success rate
- Current status/location
- Upcoming availability

**Partner Context** (click partner name):

- Tier rankings by make
- Preferred days
- Affiliation and contact
- Assignment history
- Publication metrics

## Managing Assignments

### Rescheduling

Drag and drop to change dates:

1. Click and hold an assignment
2. Drag to new position on timeline
3. Release to drop
4. Confirm the change

!!! warning
    Rescheduling validates against constraints. Invalid moves are rejected with explanation.

### Requesting to FMS

Send a planned assignment to FMS:

1. Click the green assignment
2. Select **Request** from the menu
3. Assignment turns magenta
4. Wait for FMS approval

### Unrequesting

Cancel an FMS request:

1. Click the magenta assignment
2. Select **Unrequest**
3. Request deleted from FMS
4. Assignment returns to green

### Deleting

Remove an assignment:

1. Click the assignment
2. Select **Delete**
3. If requested, also deletes from FMS
4. Assignment removed from calendar

### Editing

Modify assignment details:

1. Click the assignment
2. Select **Edit**
3. Change dates, vehicle, or partner
4. Save changes

## Filtering and Search

### Filters

Filter the calendar view by:

- **Office**: Show only selected office
- **Status**: Planned, Requested, Active, All
- **Partner Tier**: A+, A, B, C
- **Vehicle Make**: Filter by manufacturer

### Search

Use the search box to find:

- Partner names
- Vehicle makes/models
- VINs
- Assignment IDs

## Bulk Operations

### Select Multiple

Hold Shift or Ctrl to select multiple assignments.

### Bulk Actions

With multiple selected:

- **Bulk Request**: Send all to FMS
- **Bulk Delete**: Remove all
- **Bulk Export**: Download as CSV

## Capacity Indicators

### Daily Capacity Bar

The bottom of the calendar shows daily capacity:

- Pickups remaining
- Dropoffs remaining
- Total assignments for the day

### Warnings

Red indicators appear when:

- Capacity nearly exceeded
- Same-day conflicts exist
- Multiple swaps at same partner

## Context Menu

Right-click any assignment for quick actions:

- View Details
- Edit Assignment
- Request / Unrequest
- Delete
- Duplicate
- View in FMS (opens FMS link)

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Arrow Keys` | Navigate dates |
| `Delete` | Delete selected |
| `Ctrl+C` | Copy assignment |
| `Ctrl+V` | Paste assignment |
| `Escape` | Deselect all |
| `F` | Toggle filters |

## Best Practices

### Weekly Review

1. Filter to current week
2. Check for unconfirmed (green) assignments
3. Request any that are ready
4. Note any conflicts or gaps

### Conflict Resolution

When you see overlapping assignments:

1. Click conflicting assignment
2. View details to understand issue
3. Drag to non-conflicting dates
4. Or delete if duplicate

### FMS Sync

- Blue assignments are confirmed in FMS
- Magenta means awaiting FMS response
- If stuck on magenta, check FMS directly

### Performance Tips

- Use filters to reduce visible assignments
- Limit date range for faster loading
- Close context windows when not needed

## Exporting Data

### Export Options

- **CSV**: Full assignment data
- **PDF**: Printable calendar view
- **iCal**: Calendar subscription

### Export Steps

1. Set desired filters and date range
2. Click **Export**
3. Choose format
4. Download file
