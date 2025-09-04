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
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest.router)

@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "Media Scheduler API", "version": "1.0.0"}

@app.get("/healthz")
def health_check():
    """Health check endpoint"""
    return "ok"