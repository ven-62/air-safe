from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Routers
from app.routes.station_route import router as station_router
from app.routes.command_route import router as command_router
from app.routes.dashboard_route import router as dashboard_router

from app.core.database import Base, engine
import app.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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

# Admin to Server connection (for sending commands to stations, and receiving station data)
app.include_router(command_router, prefix="/cmd", tags=["Commands"])


@app.get("/")
def root():
    return {
        "status": "Connected"
    }