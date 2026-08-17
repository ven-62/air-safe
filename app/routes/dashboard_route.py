from fastapi import APIRouter, Header, HTTPException
from app.managers.dashboard_manager import dashboard_manager

router = APIRouter()

@router.get("/read/{station_id}")
async def get_pollutant_data(station_id: str):
    """ Endpoint for retrieving pollutant data for a specific station. """
    pollutant_data = await dashboard_manager.get_pollutant_data(station_id)

    return pollutant_data


@router.get("/forecast/{station_id}")
async def get_forecast_data(station_id: str):
    """ Endpoint for retrieving forecast data for a specific station. """
    forecast_data = await dashboard_manager.get_forecast_data(station_id)

    return forecast_data

@router.get("/stations")
async def get_all_stations():
    """ Endpoint for retrieving a list of all stations. """
    stations = dashboard_manager.get_all_stations()

    return stations

@router.get("/history/{station_id}")
async def get_latest_history(station_id: str):
    """Endpoint for retrieving history data for a specific station."""

    history_data = await dashboard_manager.get_latest_history(station_id)

    return history_data