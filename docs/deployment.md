# Deployment

This document describes deployment procedures for Media Scheduler.

## Overview

Media Scheduler is deployed to Render.com with the following architecture:

- **Frontend**: Static site (React/Vite build)
- **Backend**: Web service (FastAPI/Docker)
- **Database**: Supabase (managed PostgreSQL)

## Render Deployment

### Frontend Deployment

**Service Type**: Static Site

**Build Settings**:
- **Build Command**: `cd frontend && npm install && npm run build`
- **Publish Directory**: `frontend/dist`

**Environment Variables**:
```bash
VITE_API_BASE_URL=https://media-scheduler-api.onrender.com
```

### Backend Deployment

**Service Type**: Web Service

**Build Settings**:
- **Build Command**: `pip install -r backend/requirements.txt`
- **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`

**Alternative (Docker)**:
- **Dockerfile Path**: `backend/Dockerfile`

**Environment Variables**:
```bash
# Database
POSTGRES_URL=postgresql+psycopg://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Security
SCHEDULER_JWT_SECRET=production-secret

# APIs
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_MAPS_API_KEY=AIza...

# FMS
FMS_ENVIRONMENT=production
FMS_PRODUCTION_URL=https://fms.driveshop.com
FMS_PRODUCTION_TOKEN=your-token
FMS_PRODUCTION_REQUESTOR_ID=1949

# Sync
SYNC_ENABLED=true
SYNC_HOUR=2
SYNC_MINUTE=0
```

### Health Check

Configure Render health check:

- **Path**: `/health`
- **Interval**: 30 seconds

## MkDocs Documentation Deployment

Deploy documentation as a separate static site on Render.

**Service Type**: Static Site

**Build Settings**:
- **Build Command**: `pip install mkdocs mkdocs-material && mkdocs build`
- **Publish Directory**: `site`

**URL**: https://media-scheduler-docs.onrender.com

## Docker Configuration

### Backend Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
FROM node:22-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Build for production
RUN npm run build

# Serve with static server
RUN npm install -g serve
CMD ["serve", "-s", "dist", "-l", "5173"]
```

## Deployment Workflow

### Standard Deployment

1. **Merge to main**
   ```bash
   git checkout main
   git merge feature-branch
   git push origin main
   ```

2. **Render auto-deploys**
   - Detects push to main
   - Builds and deploys automatically

3. **Verify deployment**
   - Check Render dashboard for build status
   - Test endpoints after deployment
   - Verify frontend loads correctly

### Manual Deployment

Trigger manual deploy from Render dashboard:

1. Go to service settings
2. Click "Manual Deploy"
3. Select "Deploy latest commit"

### Rollback

If issues are detected:

1. Go to Render dashboard
2. Navigate to service
3. Click "Deploys" tab
4. Find previous successful deploy
5. Click "Rollback to this deploy"

## Environment Management

### Staging vs Production

Maintain separate Render services:

| Service | Branch | URL |
|---------|--------|-----|
| Frontend (Staging) | develop | media-scheduler-staging.onrender.com |
| Frontend (Prod) | main | media-scheduler.onrender.com |
| Backend (Staging) | develop | media-scheduler-api-staging.onrender.com |
| Backend (Prod) | main | media-scheduler-api.onrender.com |

### Environment Variable Updates

1. Go to Render service dashboard
2. Click "Environment"
3. Add/edit variables
4. Save and redeploy

!!! warning
    Changing environment variables triggers a redeploy.

## Database Deployment

### Supabase Management

Database is managed through Supabase dashboard:

- **URL**: https://supabase.com/dashboard
- **Project**: Media Scheduler

### Running Migrations

Apply migrations through Supabase SQL Editor:

1. Open Supabase dashboard
2. Go to SQL Editor
3. Paste migration SQL
4. Execute

### Backup Before Migration

Before schema changes:

1. Go to Supabase Settings
2. Navigate to Database
3. Create point-in-time backup

## Monitoring

### Render Logs

View logs in Render dashboard:

1. Select service
2. Click "Logs" tab
3. Filter by time/type

### Log Streaming

Stream logs locally:

```bash
render logs --service media-scheduler-api --tail
```

### Metrics

Monitor in Render dashboard:

- Request count
- Response time
- Memory usage
- CPU usage

### Alerts

Configure alerts for:

- Deploy failures
- High error rates
- Memory limits
- Response time thresholds

## Scaling

### Horizontal Scaling

Increase instances in Render:

1. Go to service settings
2. Update instance count
3. Save changes

### Vertical Scaling

Upgrade service plan:

1. Go to service settings
2. Select higher plan (Starter → Standard → Pro)
3. Confirm upgrade

### Auto-scaling

Render supports auto-scaling on Team/Pro plans:

- Configure min/max instances
- Set CPU/memory thresholds

## Security

### SSL/TLS

Render provides automatic SSL certificates for all services.

### Secrets Management

- Store secrets as environment variables
- Never commit secrets to repository
- Use Render's secret files for multi-line secrets

### Access Control

- Use Render teams for access management
- Enable 2FA for all team members
- Review access logs regularly

## Troubleshooting

### Build Failures

**Check build logs** for errors:

- Missing dependencies
- Syntax errors
- Environment variable issues

**Common fixes**:
```bash
# Clear cache and rebuild
# In Render: Settings → Clear build cache → Deploy
```

### Runtime Errors

**Check runtime logs**:

- Import errors
- Connection failures
- Memory issues

**Common fixes**:
- Verify environment variables
- Check database connectivity
- Increase memory allocation

### Performance Issues

**Symptoms**:
- Slow response times
- Timeouts
- Memory warnings

**Solutions**:
- Optimize database queries
- Add caching
- Increase instance size
- Scale horizontally

## CI/CD

### GitHub Actions (Optional)

Add automated testing before deploy:

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          pip install -r backend/requirements.txt
          pytest backend/

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render
        run: |
          curl -X POST ${{ secrets.RENDER_DEPLOY_HOOK }}
```

### Deploy Hooks

Create deploy hook in Render:

1. Go to service settings
2. Find "Deploy Hooks"
3. Generate hook URL
4. Use in CI/CD pipeline

## Maintenance

### Regular Tasks

| Task | Frequency | Description |
|------|-----------|-------------|
| Review logs | Daily | Check for errors |
| Update dependencies | Weekly | Security patches |
| Database vacuum | Monthly | PostgreSQL maintenance |
| Token rotation | Quarterly | Security best practice |

### Downtime Windows

For maintenance requiring downtime:

1. Schedule during low-usage hours
2. Notify users in advance
3. Display maintenance page
4. Perform updates
5. Verify functionality
6. Remove maintenance page

### Dependency Updates

Update dependencies safely:

1. Create feature branch
2. Update dependencies
3. Run tests
4. Deploy to staging
5. Verify functionality
6. Merge to main

## Disaster Recovery

### Backup Strategy

- **Database**: Supabase automated daily backups
- **Code**: Git repository
- **Configuration**: Documented environment variables

### Recovery Procedure

1. Identify failure point
2. Check recent changes
3. Rollback if needed
4. Restore from backup if necessary
5. Verify system functionality
6. Document incident

### Contact Information

For urgent deployment issues:

- Render Support: support@render.com
- Supabase Support: support@supabase.io
