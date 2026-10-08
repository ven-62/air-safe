from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.managers.dashboard_manager import dashboard_manager
from app.core.websocket_manager import ws_manager
from app.core.database import get_db

router = APIRouter()

# =========================================================================
# REST endpoints (now backed by the database instead of placeholder data)
# =========================================================================

@router.get("/read/{station_id}")
async def get_pollutant_data(station_id: str, db: Session = Depends(get_db)):
    """ Endpoint for retrieving pollutant data for a specific station. """
    pollutant_data = await dashboard_manager.get_pollutant_data(station_id, db)

    return pollutant_data


@router.get("/forecast/{station_id}")
async def get_forecast_data(station_id: str, db: Session = Depends(get_db)):
    """ Endpoint for retrieving forecast data for a specific station. """
    forecast_data = await dashboard_manager.get_forecast_data(station_id, db)

    return forecast_data

@router.get("/stations")
async def get_all_stations(db: Session = Depends(get_db)):
    """ Endpoint for retrieving a list of all stations. """
    stations = dashboard_manager.get_all_stations(db)

    return stations

@router.get("/history/{station_id}")
async def get_latest_history(station_id: str, db: Session = Depends(get_db)):
    """Endpoint for retrieving history data for a specific station."""

    history_data = await dashboard_manager.get_latest_history(station_id, db)

    return history_data


# =========================================================================
# WebSocket endpoints (real-time push)
# =========================================================================
#
# These mirror the REST endpoints above:
#
#   GET  /read/{station_id}      -> WS  /read/{station_id}
#   GET  /forecast/{station_id}  -> WS  /forecast/{station_id}
#
# The FastAPI server pushes a message to every connected client the
# moment station_manager.process_station_data() saves and processes
# a new ESP32 reading. Clients don't need to send anything; the
# connection is only used to detect disconnects (receive_text()
# blocks until the client sends something or closes).

@router.websocket("/read/{station_id}")
async def websocket_read(websocket: WebSocket, station_id: str):
    """ Real-time channel: latest reading / current AQI for a station. """

    await ws_manager.connect("read", station_id, websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        await ws_manager.disconnect("read", station_id, websocket)


@router.websocket("/forecast/{station_id}")
async def websocket_forecast(websocket: WebSocket, station_id: str):
    """ Real-time channel: 1/2/3-hour forecast for a station. """

    await ws_manager.connect("forecast", station_id, websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        await ws_manager.disconnect("forecast", station_id, websocket)