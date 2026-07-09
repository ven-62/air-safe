from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_request
from app.managers.command_manager import command_manager
from app.schemas.station_command import StationCommand, MultiStationCommand

router = APIRouter()


@router.post("/station/{station_id}")
async def single_station(
    station_id: str,
    command: StationCommand,
    timestamp: str = Header(alias="AS-Timestamp"),
    nonce: str = Header(alias="AS-Nonce"),
    signature: str = Header(alias="AS-Signature"),
    db: Session = Depends(get_db)
):
    if not verify_request(command.model_dump(), timestamp, nonce, signature, db):
        raise HTTPException(status_code=401, detail="Invalid signature")

    response = await command_manager.execute_command(station_id, command)

    return response


@router.post("/stations")
async def multiple_station(
    command: MultiStationCommand,
    timestamp: str = Header(alias="AS-Timestamp"),
    nonce: str = Header(alias="AS-Nonce"),
    signature: str = Header(alias="AS-Signature"),
    db: Session = Depends(get_db)
):

    if not verify_request(command.model_dump(), timestamp, nonce, signature, db):
        raise HTTPException(status_code=401, detail="Invalid signature")

    response = await command_manager.execute_many(command.stations, command)

    return response


@router.post("/stations/all")
async def all_station(
    command: StationCommand,
    timestamp: str = Header(alias="AS-Timestamp"),
    nonce: str = Header(alias="AS-Nonce"),
    signature: str = Header(alias="AS-Signature"),
    db: Session = Depends(get_db)
):

    if not verify_request(command.model_dump(), timestamp, nonce, signature, db):
        raise HTTPException(status_code=401, detail="Invalid signature")

    response = await command_manager.execute_all(command)

    return response


@router.get("/stations/add")
async def add_station(
    data: Dict[str, Any],
    timestamp: str = Header(alias="AS-Timestamp"),
    nonce: str = Header(alias="AS-Nonce"),
    signature: str = Header(alias="AS-Signature"),
    db: Session = Depends(get_db)
):
    """Add a new station to the system."""
    if not verify_request(data, timestamp, nonce, signature, db):
        raise HTTPException(status_code=401, detail="Invalid signature")

    response = await command_manager.add_station(
        data["name"], float(data["latitude"]), float(data["longitude"]), db
    )

    return response


@router.get("/stations/remove")
async def remove_station(
    data: Dict[str, Any],
    timestamp: str = Header(alias="AS-Timestamp"),
    nonce: str = Header(alias="AS-Nonce"),
    signature: str = Header(alias="AS-Signature"),
    db: Session = Depends(get_db)
):
    """Remove a station from the system."""
    if not verify_request(
        data, timestamp, nonce, signature, db
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")

    response = await command_manager.remove_station(data["station_id"], db)
    return response


@router.get("/stations/modify")
async def modify_station(
    data: Dict[str, Any],
    timestamp: str = Header(alias="AS-Timestamp"),
    nonce: str = Header(alias="AS-Nonce"),
    signature: str = Header(alias="AS-Signature"),
    db: Session = Depends(get_db)
):
    """Modify a station's details in the system."""
    if not verify_request(data, timestamp, nonce, signature, db):
        raise HTTPException(status_code=401, detail="Invalid signature")

    response = await command_manager.modify_station(
        station_id=data["station_id"],
        name=data.get("name"),
        latitude=(
            float(data.get("latitude")) if data.get("latitude") is not None else None
        ),
        longitude=(
            float(data.get("longitude")) if data.get("longitude") is not None else None
        ),
        db=db
    )
    return response


@router.get("/list")
async def list_stations(
    data: Dict[str, Any],
    timestamp: str = Header(alias="AS-Timestamp"),
    nonce: str = Header(alias="AS-Nonce"),
    signature: str = Header(alias="AS-Signature"),
    db: Session = Depends(get_db)
):
    """List all stations in the system. This is a placeholder endpoint and should be implemented with proper logic."""
    if not verify_request(data, timestamp, nonce, signature, db):
        raise HTTPException(status_code=401, detail="Invalid signature")

    response = await command_manager.get_station(data["station_id"], db)
    return response
