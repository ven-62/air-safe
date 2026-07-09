from fastapi import APIRouter, Header, HTTPException
from app.managers.dashboard_manager import dashboard_manager

router = APIRouter()

@router.get("/{station_id}")
async def get_pollutant_data(station_id: str):
    """ Endpoint for retrieving pollutant data for a specific station. """
    pollutant_data = await dashboard_manager.get_pollutant_data(station_id)

    return pollutant_data
