from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Routers
from app.routes.station_route import router as station_router
from app.routes.dashboard_route import router as dashboard_router

from app.core.database import Base, engine
from app.core.seed import seed_stations
import app.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine) # Create database tables based on SQLAlchemy models
    seed_stations() # Seed the database with initial station data if not already present
    yield


app = FastAPI(
    title="AIR-SAFE API",
    description="API for AIR-SAFE project",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ESP32 HTTP to Server connection (for sending station data to server)
app.include_router(station_router, prefix="/stn", tags=["Stations"])

# Server to frontend connection (for sending station data to frontend)
app.include_router(dashboard_router, prefix="/monitor", tags=["Monitoring"])

@app.get("/")
def root():
    """Root endpoint to check if the server is running."""
    return {
        "status": "Connected"
    }