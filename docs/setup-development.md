# Setup Development

This guide walks through setting up a local development environment for Media Scheduler.

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Docker | 20.10+ | Containerization |
| Docker Compose | 2.0+ | Multi-container orchestration |
| Node.js | 22 LTS | Frontend runtime |
| Python | 3.12+ | Backend runtime |
| Git | Latest | Version control |

### Recommended Tools

- VS Code with Python and ESLint extensions
- Postman or similar for API testing
- pgAdmin or DBeaver for database inspection

## Quick Start with Docker

The fastest way to get started is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/aininja-pro/media-scheduler.git
cd media-scheduler

# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

Access the application:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8081
- API Docs: http://localhost:8081/docs

## Environment Variables

Create a `.env` file in the project root with:

```bash
# Database (Supabase)
POSTGRES_URL=postgresql+psycopg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
SUPABASE_URL=https://[PROJECT].supabase.co
SUPABASE_ANON_KEY=eyJhbGciOi...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...

# Security
SCHEDULER_JWT_SECRET=your-super-secret-jwt-key

# External APIs
ANTHROPIC_API_KEY=sk-ant-api03-...
GOOGLE_MAPS_API_KEY=AIzaSy...

# FMS Integration
FMS_ENVIRONMENT=staging
FMS_STAGING_URL=https://staging.driveshop.com
FMS_PRODUCTION_URL=https://fms.driveshop.com
FMS_STAGING_TOKEN=your-staging-token
FMS_PRODUCTION_TOKEN=your-production-token
FMS_STAGING_REQUESTOR_ID=1949
FMS_PRODUCTION_REQUESTOR_ID=1949

# Nightly Sync
SYNC_ENABLED=false
SYNC_HOUR=2
SYNC_MINUTE=0

# Development
NODE_ENV=development
DEBUG=true
```

## Manual Setup

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Create environment file
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.development

# Run development server
npm run dev
```

## Docker Compose Configuration

The `docker-compose.yml` defines three services:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15.3
    ports:
      - "5432:5432"
    environment:
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8081:8000"
    environment:
      - DATABASE_URL=${POSTGRES_URL}
    depends_on:
      - postgres
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  postgres_data:
```

## Database Setup

### Using Supabase (Recommended)

1. Create a Supabase project at https://supabase.com
2. Copy connection details to `.env`
3. Run migrations (if available)

### Local PostgreSQL

For offline development:

```bash
# Start only postgres
docker-compose up -d postgres

# Connect
psql -h localhost -U postgres -d postgres
```

## Verifying Installation

### Check Backend

```bash
# Health check
curl http://localhost:8081/health

# API documentation
open http://localhost:8081/docs
```

### Check Frontend

```bash
# Should see application
open http://localhost:5173
```

### Check Database Connection

```bash
# In backend container
docker-compose exec backend python -c "
from app.services.database import DatabaseService
import asyncio
async def test():
    db = DatabaseService()
    await db.initialize()
    print('Connected!')
    await db.close()
asyncio.run(test())
"
```

## Development Workflow

### Running Tests

```bash
# Backend tests
cd backend
pytest

# With coverage
pytest --cov=app
```

### Linting

```bash
# Frontend
cd frontend
npm run lint

# Backend (if configured)
cd backend
flake8 app/
```

### Hot Reload

Both frontend and backend support hot reload:

- **Frontend**: Vite automatically reloads on file changes
- **Backend**: Uvicorn `--reload` flag watches for changes

### Code Formatting

```bash
# Frontend (Prettier if configured)
npm run format

# Backend
black app/
isort app/
```

## Common Development Tasks

### Adding a New API Endpoint

1. Create route in `backend/app/routers/`
2. Register router in `backend/app/main.py`
3. Create Pydantic schema if needed
4. Test with Swagger UI at `/docs`

### Adding a New Page

1. Create component in `frontend/src/pages/`
2. Add route in `frontend/src/App.jsx`
3. Update navigation if needed

### Modifying Database Schema

1. Update models/queries in backend
2. Test with local data
3. Apply migration to Supabase

### Testing FMS Integration

Use staging environment:

```bash
# In .env
FMS_ENVIRONMENT=staging
```

## Troubleshooting

### Port Already in Use

```bash
# Find process
lsof -i :5173  # or :8081

# Kill it
kill -9 <PID>
```

### Docker Issues

```bash
# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Module Not Found (Python)

```bash
# Ensure virtual environment is active
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### npm Install Fails

```bash
# Clear cache
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### Database Connection Failed

1. Check `.env` credentials
2. Verify Supabase project is running
3. Check network/firewall settings
4. Test with `psql` directly

## IDE Configuration

### VS Code Settings

Recommended `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./backend/venv/bin/python",
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "eslint.workingDirectories": ["./frontend"]
}
```

### Recommended Extensions

- Python
- Pylance
- ESLint
- Tailwind CSS IntelliSense
- Docker

## Next Steps

- Review [API Reference](api-reference.md) for endpoint documentation
- Understand the [Database Schema](database-schema.md)
- Learn about [FMS Integration](fms-integration.md)
- See [Deployment](deployment.md) for production setup
