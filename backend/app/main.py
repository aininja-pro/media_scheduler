from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import ingest
from .services.database import db_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db_service.initialize()
    yield
    # Shutdown
    await db_service.close()

app = FastAPI(
    title="Media Scheduler API",
    description="Vehicle-to-media partner scheduling optimization system",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest.router)

# Import and include ETL router
from .routers import etl
app.include_router(etl.router, prefix="/api")

# Import and include Solver router
from .routers import solver
app.include_router(solver.router, prefix="/api")

# Import and include UI Phase 7 router
from .routers import ui_phase7
app.include_router(ui_phase7.router, prefix="/api")

# Import and include Calendar router
from .routers import calendar
app.include_router(calendar.router)

@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "Media Scheduler API", "version": "1.0.0"}

@app.get("/api/offices")
async def get_offices():
    """Get list of active offices"""
    try:
        response = db_service.client.table('offices').select('*').eq('active', True).order('name').execute()
        return response.data if response.data else []
    except Exception as e:
        return {"error": str(e)}

@app.get("/healthz")
def health_check():
    """Health check endpoint"""
    return "ok"

@app.get("/healthz/db")
async def database_health_check():
    """Database connection health check"""
    try:
        is_connected = await db_service.test_connection()
        return {"database": "connected" if is_connected else "disconnected"}
    except Exception as e:
        return {"database": "error", "detail": str(e)}