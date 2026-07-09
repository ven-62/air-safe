from fastapi import APIRouter, Header, HTTPException

from app.core.security import verify_auth_key
from app.managers.station_manager import station_manager

router = APIRouter()


@router.post("/{station_id}/readings")
async def post_station_readings(
    station_id: str, data: dict, auth_key: str = Header(alias="AS-Auth-Key")
):
    """
    Endpoint for stations to post their data to the server.
    """
    if not verify_auth_key(station_id, auth_key):
        raise HTTPException(status_code=401, detail="Invalid authentication key")

    return await station_manager.process_station_data(station_id, data)


@router.post("/{station_id}/report")
async def post_station_report(
    station_id: str, data: dict, auth_key: str = Header(alias="AS-Auth-Key")
):
    """
    Endpoint for retrieving station data.
    """
    if not verify_auth_key(station_id, auth_key):
        raise HTTPException(status_code=401, detail="Invalid authentication key")

    # Implement the logic to retrieve station data
    pass
