# Embedded Mode Testing Guide

## Overview

The Media Scheduler now supports two display modes:
1. **Standalone Mode**: Full app with black menu bar and logo
2. **Embedded Mode**: Iframe-ready with horizontal tabs in page body (no logo, no black bar)

---

## How to Test

### Mode 1: Standalone (Default)

**URL**: `http://localhost:5173/`

**Expected**:
- ✅ Black menu bar at top
- ✅ DriveShop logo visible
- ✅ "Media Scheduler" title visible
- ✅ Navigation buttons in header (white background when active)
- ✅ Tabs order: Upload Data, Chain Builder, Calendar, Optimizer

**Screenshot**: This is the normal view you're used to.

---

### Mode 2: Embedded (For FMS iframe)

**URL**: `http://localhost:5173/?embedded=true`

**Expected**:
- ❌ No black menu bar
- ❌ No DriveShop logo
- ❌ No "Media Scheduler" title
- ✅ Horizontal tab navigation at top of page body
- ✅ Tabs styled with FMS colors:
  - Active tab: Green text (`#10b981`) with green underline
  - Inactive tabs: Gray text (`#919389` - Alex's h1 color)
  - Hover: Darker gray
- ✅ Tabs order: Upload Data, Chain Builder, Calendar, Optimizer
- ✅ Tabs aligned left
- ✅ Font size: 18px (per Alex's specification)
- ✅ Padding: 15px top/bottom (per Alex's specification)

**Screenshot**: Take this screenshot to show Alex!

---

## How It Works

### URL Detection

The app checks for the `?embedded=true` URL parameter:

```javascript
// In App.jsx
useEffect(() => {
  const urlParams = new URLSearchParams(window.location.search)
  const embedded = urlParams.get('embedded') === 'true'
  setIsEmbedded(embedded)
}, [])
```

### Conditional Rendering

```javascript
{/* Show header only when NOT embedded */}
{!isEmbedded && (
  <header className="bg-black">
    {/* Logo and navigation */}
  </header>
)}

{/* Show tab navigation only when embedded */}
{isEmbedded && (
  <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />
)}
```

---

## Tab Styling

### Active Tab (Current Page)
- **Color**: Green (#10b981 / text-green-600)
- **Underline**: 2px solid green border-bottom
- **Font**: Bold, 18px

### Inactive Tabs
- **Color**: Gray (#919389 / text-gray-500) - Matches Alex's h1 style
- **Hover**: Darker gray (#374151 / text-gray-700)
- **Font**: Bold, 18px

### Spacing
- **Between tabs**: 2rem (space-x-8)
- **Vertical padding**: 15px top and bottom
- **Bottom border**: 1px gray border separating tabs from content

---

## For Alex (FMS Integration)

### iframe Code

When embedding in FMS, use:

```html
<iframe
  src="https://media-scheduler.onrender.com/?embedded=true"
  width="100%"
  height="800px"
  frameborder="0"
  style="border: none;"
></iframe>
```

### URL Parameters

- **Standalone**: `https://media-scheduler.onrender.com/`
- **Embedded**: `https://media-scheduler.onrender.com/?embedded=true`

---

## Styling Details (Per Alex's Specs)

From Alex's email:
```css
h1 {
    font-size: 18px;
    color: #919389;
    margin: 0px 0px;
    padding: 15px 0px 15px 0px;
    font-weight: bold;
}
```

**How we adapted it**:
- ✅ Font size: 18px
- ✅ Inactive color: #919389 (text-gray-500)
- ✅ Active color: Green for emphasis
- ✅ Padding: 15px vertical
- ✅ Font weight: Bold
- ✅ Horizontal layout with left alignment

---

## Testing Checklist

### Standalone Mode
- [ ] Black header visible
- [ ] Logo displays correctly
- [ ] "Media Scheduler" title shows
- [ ] Tabs work in header
- [ ] Active tab has white background
- [ ] All 4 pages load correctly

### Embedded Mode
- [ ] No black header
- [ ] No logo/title
- [ ] Tab navigation at top of body
- [ ] Active tab is green with underline
- [ ] Inactive tabs are gray
- [ ] Hover effect works
- [ ] All 4 pages load correctly
- [ ] Tabs are left-aligned
- [ ] Font size is 18px
- [ ] Tabs properly spaced

### Both Modes
- [ ] Tab order: Upload Data, Chain Builder, Calendar, Optimizer
- [ ] Clicking tabs switches pages
- [ ] Page content displays properly
- [ ] Responsive on different screen sizes

---

## Screenshots to Take

1. **Standalone mode** - `http://localhost:5173/`
   - Show black header with logo
   - Show active tab (white background)

2. **Embedded mode** - `http://localhost:5173/?embedded=true`
   - Show NO black header
   - Show horizontal tabs with green active state
   - Show gray inactive tabs
   - Show proper alignment and spacing

3. **Embedded mode - Different tabs**
   - Switch to each tab to show active state changes
   - Upload Data (green underline)
   - Chain Builder (green underline)
   - Calendar (green underline)
   - Optimizer (green underline)

---

## Next Steps

1. ✅ Implementation complete
2. ⏳ Test both modes locally
3. ⏳ Take screenshots for Alex
4. ⏳ Deploy to staging
5. ⏳ Have Alex test iframe embedding
6. ⏳ Adjust styling if needed
7. ⏳ Deploy to production

---

## Files Modified

### New Files
- `frontend/src/components/TabNavigation.jsx` - New tab component

### Modified Files
- `frontend/src/App.jsx`:
  - Added `isEmbedded` state
  - Added URL parameter detection
  - Wrapped header in conditional render
  - Added TabNavigation component
  - Reordered tabs: Upload Data, Chain Builder, Calendar, Optimizer

---

**Status**: Ready for testing
**Date**: November 12, 2025
**Developer**: Ray Rierson + Claude
