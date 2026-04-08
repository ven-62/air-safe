from sqlalchemy.orm import Session
from app.models.sensor_data import SensorData

def save_sensor_data(db: Session, data: dict):
    record = SensorData(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def get_latest_data(db: Session, limit=50):
    return db.query(SensorData).order_by(SensorData.created_at.desc()).limit(limit).all()