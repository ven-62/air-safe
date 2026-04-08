from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.utils.database import SessionLocal
from app.services.sensor_service import save_sensor_data, get_latest_data
from app.utils.database import get_db

router = APIRouter()

class SensorPayload(BaseModel):
    temperature: float
    humidity: float
    co: float
    mq135: float
    pm25: float

@router.post("/sensor")
def receive_data(payload: SensorPayload, db: Session = Depends(get_db)):
    return save_sensor_data(db, payload.model_dump())

@router.get("/sensor/latest")
def latest_data(db: Session = Depends(get_db)):
    return get_latest_data(db)