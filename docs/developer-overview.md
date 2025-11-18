# Developer Overview

This document provides a technical overview of Media Scheduler's architecture and implementation.

## System Architecture

Media Scheduler is a full-stack application with three main layers:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    Backend      │────▶│    Database     │
│   React/Vite    │     │    FastAPI      │     │    Supabase     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         │              │   OR-Tools      │              │
         │              │   Optimizer     │              │
         │              └─────────────────┘              │
         │                       │
         │                       ▼
         │              ┌─────────────────┐
         └─────────────▶│      FMS        │
                        │   Integration   │
                        └─────────────────┘
```

## Technology Stack

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19 | UI framework |
| Vite | 7.1 | Build tool and dev server |
| Tailwind CSS | 4.1 | Styling |
| Headless UI | Latest | Accessible UI components |
| @dnd-kit/core | Latest | Drag-and-drop functionality |

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Runtime |
| FastAPI | Latest | API framework |
| uvicorn | Latest | ASGI server |
| Google OR-Tools | 9.14 | Constraint satisfaction solver |
| pandas | Latest | Data processing |
| httpx | Latest | Async HTTP client |
| APScheduler | Latest | Background task scheduling |

### Database

| Technology | Version | Purpose |
|------------|---------|---------|
| Supabase | Latest | Hosted PostgreSQL |
| psycopg | Latest | Async PostgreSQL driver |

### Infrastructure

| Technology | Purpose |
|------------|---------|
| Docker | Containerization |
| Docker Compose | Local development |
| Render | Production hosting |

## Project Structure

### Root Directory

```
media_scheduler/
├── frontend/           # React application
├── backend/            # FastAPI application
├── docs/               # Documentation
├── docker-compose.yml  # Local development
├── .env                # Environment variables
└── mkdocs.yml          # Documentation config
```

### Frontend Structure

```
frontend/src/
├── App.jsx                 # Main application component
├── config.js               # API configuration
├── main.jsx                # Entry point
├── index.css               # Global styles
├── pages/
│   ├── Optimizer.jsx       # Phase 7 optimizer UI
│   ├── ChainBuilder.jsx    # Chain building interface
│   ├── Calendar.jsx        # Timeline visualization
│   ├── Partners.jsx        # Partner management
│   ├── PublicationRates.jsx
│   └── Availability.jsx
├── components/
│   ├── ModelSelector.jsx
│   ├── AssignmentDetailsPanel.jsx
│   ├── OptimizerDiagnostics.jsx
│   └── TimelineBar.jsx
├── hooks/
│   ├── useDeleteAssignment.js
│   └── useSaveChain.js
└── utils/
    └── eventManager.js
```

### Backend Structure

```
backend/app/
├── main.py                 # FastAPI app initialization
├── routers/
│   ├── ingest.py          # Data ingestion endpoints
│   ├── solver.py          # Solver endpoints
│   ├── ui_phase7.py       # Optimizer endpoints
│   ├── calendar.py        # Calendar endpoints
│   ├── chain_builder.py   # Chain builder endpoints
│   ├── fms_integration.py # FMS API integration
│   └── etl.py             # ETL pipeline
├── services/
│   ├── database.py        # Supabase client
│   ├── nightly_sync.py    # Scheduled sync
│   └── pagination.py      # Query helpers
├── solver/
│   ├── ortools_solver_v6.py    # Main optimizer
│   ├── vehicle_chain_solver.py
│   ├── partner_chain_solver.py
│   ├── candidates.py
│   ├── scoring.py
│   ├── cooldown_filter.py
│   ├── tier_caps_soft.py
│   └── budget_constraints.py
├── chain_builder/
│   ├── availability.py
│   ├── exclusions.py
│   ├── geography.py
│   └── smart_scheduling.py
├── etl/
│   ├── publication.py
│   ├── availability.py
│   └── cooldown.py
├── utils/
│   ├── geocoding.py
│   ├── media_costs.py
│   └── geo.py
└── schemas/
    └── ingest.py
```

## Core Components

### Optimizer Engine

The optimizer uses Google OR-Tools CP-SAT solver for constraint satisfaction:

**Key Files**:
- `backend/app/solver/ortools_solver_v6.py` - Main solver implementation
- `backend/app/solver/scoring.py` - Scoring functions
- `backend/app/solver/candidates.py` - Candidate generation

**Objectives**:
- Maximize publication rates
- Geographic optimization
- Fair distribution
- Budget awareness

**Constraints**:
- Vehicle availability
- Partner eligibility
- Cooldown periods
- Daily capacity
- Budget limits

### Chain Builder

Builds sequential assignment chains for partners or vehicles:

**Key Files**:
- `backend/app/routers/chain_builder.py` - API endpoints
- `backend/app/chain_builder/smart_scheduling.py` - Scheduling logic
- `frontend/src/pages/ChainBuilder.jsx` - UI component

### FMS Integration

Bi-directional sync with Fleet Management System:

**Key Files**:
- `backend/app/routers/fms_integration.py` - API integration
- `backend/app/services/nightly_sync.py` - Scheduled sync

**Operations**:
- Create vehicle requests
- Delete vehicle requests
- Sync status updates

### Data Pipeline

ETL processes for data management:

**Key Files**:
- `backend/app/routers/ingest.py` - Data ingestion
- `backend/app/etl/publication.py` - Publication rate calculation
- `backend/app/services/nightly_sync.py` - Automated sync

## Data Flow

### Assignment Creation

```
User Action → Frontend → API → Database → Response → UI Update
```

### FMS Request Flow

```
Create in Scheduler → Send to FMS → FMS Approval → Sync Back → Update Status
```

### Optimization Flow

```
Load Data → Generate Candidates → Apply Constraints →
Optimize → Score Solutions → Return Results
```

## Key Patterns

### API Routing

FastAPI routers with dependency injection:

```python
@router.post("/run")
async def run_optimizer(request: RunRequest) -> Dict[str, Any]:
    db = DatabaseService()
    await db.initialize()
    try:
        # ... logic
    finally:
        await db.close()
```

### Database Queries

Supabase client with pandas integration:

```python
response = db.client.table('vehicles')\
    .select('*')\
    .eq('office', office)\
    .execute()
df = pd.DataFrame(response.data)
```

### State Management

React useState and useEffect patterns:

```javascript
const [data, setData] = useState([]);
const [loading, setLoading] = useState(false);

useEffect(() => {
    fetchData();
}, [dependencies]);
```

### API Configuration

Environment-based API URLs:

```javascript
import { API_BASE_URL } from '../config';
fetch(`${API_BASE_URL}/api/endpoint`)
```

## Performance Considerations

### Optimizer

- Time-limited solving (default 60s)
- Incremental constraint evaluation
- Caching of repeated calculations

### Frontend

- Virtual scrolling for large lists
- Debounced search inputs
- Lazy loading of context windows

### Database

- Indexed queries on common filters
- Paginated results for large datasets
- Connection pooling

## Security

### Authentication

- JWT tokens for API authentication
- Role-based access control
- Secure environment variables

### Data Protection

- SSL/TLS for all connections
- Sanitized user inputs
- CORS configuration

## Testing

### Backend Tests

Located in `backend/` directory:

- Unit tests for solver functions
- Integration tests for API endpoints
- Data validation tests

### Running Tests

```bash
cd backend
pytest
```

## Development Workflow

1. Create feature branch
2. Implement changes
3. Run local tests
4. Deploy to staging
5. Verify FMS integration
6. Create pull request
7. Code review
8. Merge to main
9. Deploy to production

## Additional Resources

- [Setup Development](setup-development.md) - Local environment setup
- [API Reference](api-reference.md) - API documentation
- [Database Schema](database-schema.md) - Data model
- [FMS Integration](fms-integration.md) - FMS technical details
- [Deployment](deployment.md) - Deployment procedures
