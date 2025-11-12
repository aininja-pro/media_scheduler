# API URL Configuration - Complete ✅

**Date**: November 12, 2025
**Status**: Production ready

---

## Summary

Replaced all 98 hardcoded `http://localhost:8081` API URLs across 12 frontend files with environment-based configuration. The app now automatically uses the correct API URL for development, staging, and production environments.

---

## Changes Made

### New Files Created

1. **`frontend/src/config.js`** - Central configuration module
   ```javascript
   export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8081';
   ```

2. **`frontend/.env.development`** - Development environment
   ```bash
   VITE_API_BASE_URL=http://localhost:8081
   ```

3. **`frontend/.env.production`** - Production environment
   ```bash
   VITE_API_BASE_URL=https://media-scheduler-api.onrender.com
   ```

4. **`frontend/.env.example`** - Template for team

---

## Files Updated (12 files, 98 replacements)

### Pages
- ✅ `Calendar.jsx` - Added config import, replaced URLs
- ✅ `ChainBuilder.jsx` - Added config import, replaced URLs
- ✅ `Partners.jsx` - Added config import, replaced URLs
- ✅ `Optimizer.jsx` - Added config import, replaced URLs
- ✅ `PublicationRates.jsx` - Added config import, replaced URLs
- ✅ `ScheduleGeneration.jsx` - Added config import, replaced URLs
- ✅ `Availability.jsx` - Added config import, replaced URLs

### Components
- ✅ `AssignmentDetailsPanel.jsx` - Added config import, replaced URLs
- ✅ `ModelSelector.jsx` - Added config import, replaced URLs

### Hooks
- ✅ `useDeleteAssignment.js` - Added config import, replaced URLs
- ✅ `useSaveChain.js` - Added config import, replaced URLs

### Root
- ✅ `App.jsx` - Added config import, replaced URLs

---

## How It Works

### Configuration Hierarchy

1. **Environment Variable** (highest priority)
   - Vite reads `VITE_API_BASE_URL` from `.env.development` or `.env.production`
   - Automatically set based on `npm run dev` vs `npm run build`

2. **Fallback** (if no env variable)
   - Uses `http://localhost:8081` as default
   - Ensures app works even without env files

### Usage in Code

**Before:**
```javascript
fetch('http://localhost:8081/api/calendar/activity')
```

**After:**
```javascript
import { API_BASE_URL } from './config';

fetch(`${API_BASE_URL}/api/calendar/activity`)
```

---

## Environment Setup

### Development (Local)

**File**: `frontend/.env.development`
```bash
VITE_API_BASE_URL=http://localhost:8081
```

**Usage**: Automatically used when running `npm run dev`

---

### Production (Render)

**File**: `frontend/.env.production`
```bash
VITE_API_BASE_URL=https://media-scheduler-api.onrender.com
```

**Usage**: Automatically used when running `npm run build`

**Update**: Change the URL to match your actual Render backend deployment

---

### Staging (Optional)

Create `frontend/.env.staging`:
```bash
VITE_API_BASE_URL=https://media-scheduler-api-staging.onrender.com
```

---

## Deployment Guide

### Render Deployment

#### Backend Service
1. **Service Name**: `media-scheduler-api`
2. **URL**: `https://media-scheduler-api.onrender.com`
3. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables**: Copy from `backend/.env`

#### Frontend Service
1. **Service Name**: `media-scheduler`
2. **URL**: `https://media-scheduler.onrender.com`
3. **Build Command**: `npm run build`
4. **Publish Directory**: `dist`
5. **Environment Variables**:
   ```
   VITE_API_BASE_URL=https://media-scheduler-api.onrender.com
   ```

---

## Testing

### Local Development
```bash
cd frontend
npm run dev
```
- Opens `http://localhost:5173`
- Uses `http://localhost:8081` for API (from `.env.development`)
- Console logs: "🔧 App Configuration: { API_BASE_URL: 'http://localhost:8081' }"

### Production Build
```bash
cd frontend
npm run build
```
- Creates `dist/` folder
- Uses API URL from `.env.production`
- Build succeeded ✅ (verified November 12, 2025)

### Preview Production Build
```bash
cd frontend
npm run preview
```
- Serves production build locally
- Uses production API URL

---

## Troubleshooting

### Issue: API calls fail with "Network error"

**Check 1**: Verify environment variable is set
```bash
cd frontend
cat .env.development
```

**Check 2**: Restart dev server after changing `.env` files
```bash
npm run dev
```

**Check 3**: Check console for configuration log
```
🔧 App Configuration: {
  API_BASE_URL: 'http://localhost:8081',
  IS_DEV: true,
  IS_PROD: false
}
```

---

### Issue: Production build uses wrong URL

**Solution**: Update `frontend/.env.production`
```bash
VITE_API_BASE_URL=https://your-actual-backend-url.onrender.com
```

Then rebuild:
```bash
npm run build
```

---

### Issue: Environment variable not working

**Cause**: Vite only exposes variables prefixed with `VITE_`

**Check**: Make sure it's named `VITE_API_BASE_URL` (not `API_BASE_URL`)

---

## Git Ignore

The `.env.development` and `.env.production` files are **committed** because:
- They contain no secrets (just URLs)
- Team needs them for local development
- Production URL is public anyway

If you add sensitive data (API keys, passwords), add to `.gitignore`:
```
# .gitignore
.env.local
.env.*.local
```

---

## Migration Summary

### Before
- ❌ 98 hardcoded `http://localhost:8081` URLs
- ❌ Manual find-replace needed for deployment
- ❌ Different URLs for dev/staging/prod required code changes

### After
- ✅ All URLs use `${API_BASE_URL}` template variable
- ✅ Automatic environment detection (dev vs prod)
- ✅ Single source of truth in config.js
- ✅ Easy to update for new environments
- ✅ No code changes needed for deployment

---

## Benefits

### Development
- ✅ Works out of the box (localhost default)
- ✅ Console logging shows current configuration
- ✅ Easy to test against different backends

### Deployment
- ✅ One-line configuration change
- ✅ No code modifications needed
- ✅ Environment-specific URLs automatically selected

### Maintenance
- ✅ Single import statement per file
- ✅ Centralized configuration
- ✅ Type-safe with modern ES6 template literals

---

## Future Enhancements

### Option 1: Add More Environments
```javascript
// config.js
const ENV = import.meta.env.MODE; // 'development' | 'production' | 'staging'

export const API_BASE_URL = {
  development: 'http://localhost:8081',
  staging: 'https://api-staging.onrender.com',
  production: 'https://api.onrender.com'
}[ENV];
```

### Option 2: Add API Timeout Configuration
```javascript
// config.js
export const API_TIMEOUT = import.meta.env.VITE_API_TIMEOUT || 30000;
```

### Option 3: Add Feature Flags
```javascript
// config.js
export const FEATURES = {
  FMS_INTEGRATION: import.meta.env.VITE_FEATURE_FMS === 'true',
  NIGHTLY_SYNC: import.meta.env.VITE_FEATURE_SYNC === 'true'
};
```

---

## Verification Checklist

- [x] Created config.js with API_BASE_URL export
- [x] Created .env.development with localhost URL
- [x] Created .env.production with Render URL
- [x] Replaced all 98 hardcoded URLs with template variable
- [x] Added config import to all 12 files
- [x] Frontend builds successfully (verified)
- [x] No hardcoded localhost:8081 URLs remain (except config fallback)
- [x] Console logs show configuration in development

---

**Status**: Complete and production-ready ✅
**Build Status**: Passing ✅
**Files Changed**: 15 files (3 new, 12 updated)
**Last Updated**: November 12, 2025
