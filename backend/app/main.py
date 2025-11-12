from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import os
import logging

from .routers import ingest
from .services.database import db_service
from .services.nightly_sync import run_nightly_sync, get_sync_config

logger = logging.getLogger(__name__)

# Initialize APScheduler
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db_service.initialize()

    # Start nightly sync scheduler
    sync_hour = int(os.getenv('SYNC_HOUR', 2))
    sync_minute = int(os.getenv('SYNC_MINUTE', 0))
    sync_enabled = os.getenv('SYNC_ENABLED', 'true').lower() == 'true'

    if sync_enabled:
        scheduler.add_job(
            run_nightly_sync,
            CronTrigger(hour=sync_hour, minute=sync_minute),
            id='nightly_fms_sync',
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"✓ Nightly sync scheduler started - runs daily at {sync_hour:02d}:{sync_minute:02d}")
    else:
        logger.info("⚠ Nightly sync disabled (SYNC_ENABLED=false)")

    yield

    # Shutdown
    if sync_enabled:
        scheduler.shutdown()
        logger.info("✓ Scheduler stopped")
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
    allow_origins=[
        "http://localhost:3001",
        "http://localhost:5173",
        "https://fms.driveshop.com",              # FMS production
        "https://staging.driveshop.com",          # FMS staging
        "https://media-scheduler.onrender.com",   # Frontend production
    ],
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

# Import and include Chain Builder router
from .routers import chain_builder
app.include_router(chain_builder.router, prefix="/api")

# Import and include FMS Integration router
from .routers import fms_integration
app.include_router(fms_integration.router)

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


# ============================================
# NIGHTLY SYNC ADMIN ENDPOINTS
# ============================================

@app.post("/api/admin/trigger-sync")
async def trigger_manual_sync():
    """
    Manually trigger FMS data sync (for testing/debugging)

    Syncs all tables:
    - Vehicles
    - Media Partners (with geocoding + preferred day analysis)
    - Loan History
    - Current Activity
    - Approved Makes

    Note: Operations Data and Budgets remain manual (Excel upload)
    """
    logger.info("[Manual Sync] Triggered by user")
    result = await run_nightly_sync()
    return result


@app.get("/api/admin/sync-config")
async def get_sync_configuration():
    """
    Get nightly sync configuration

    Returns:
        Sync schedule, URLs, and settings
    """
    config = get_sync_config()
    return config


@app.get("/api/admin/sync-status")
async def get_sync_status():
    """
    Get status of nightly sync scheduler

    Returns:
        Whether scheduler is running and next run time
    """
    is_running = scheduler.running
    next_run = None

    if is_running:
        jobs = scheduler.get_jobs()
        sync_job = next((j for j in jobs if j.id == 'nightly_fms_sync'), None)
        if sync_job and sync_job.next_run_time:
            next_run = sync_job.next_run_time.isoformat()

    return {
        'scheduler_running': is_running,
        'next_sync_time': next_run,
        'sync_hour': int(os.getenv('SYNC_HOUR', 2)),
        'sync_minute': int(os.getenv('SYNC_MINUTE', 0)),
        'sync_enabled': os.getenv('SYNC_ENABLED', 'true').lower() == 'true'
    }


@app.post("/api/admin/update-sync-schedule")
async def update_sync_schedule(sync_hour: int, sync_minute: int):
    """
    Update the nightly sync schedule

    Args:
        sync_hour: Hour (0-23)
        sync_minute: Minute (0-59)

    Returns:
        Updated schedule info
    """
    from pydantic import BaseModel

    # Validate inputs
    if not (0 <= sync_hour <= 23):
        raise HTTPException(status_code=400, detail="sync_hour must be between 0-23")
    if not (0 <= sync_minute <= 59):
        raise HTTPException(status_code=400, detail="sync_minute must be between 0-59")

    # Update environment variables (runtime only - not persisted to .env)
    os.environ['SYNC_HOUR'] = str(sync_hour)
    os.environ['SYNC_MINUTE'] = str(sync_minute)

    # Reschedule the job
    if scheduler.running:
        scheduler.remove_job('nightly_fms_sync')
        scheduler.add_job(
            run_nightly_sync,
            CronTrigger(hour=sync_hour, minute=sync_minute),
            id='nightly_fms_sync',
            replace_existing=True
        )
        logger.info(f"✓ Sync schedule updated to {sync_hour:02d}:{sync_minute:02d}")

    # Get updated next run time
    next_run = None
    if scheduler.running:
        jobs = scheduler.get_jobs()
        sync_job = next((j for j in jobs if j.id == 'nightly_fms_sync'), None)
        if sync_job and sync_job.next_run_time:
            next_run = sync_job.next_run_time.isoformat()

    return {
        'success': True,
        'message': f'Sync schedule updated to {sync_hour:02d}:{sync_minute:02d}',
        'sync_hour': sync_hour,
        'sync_minute': sync_minute,
        'next_sync_time': next_run
    }