from sqlalchemy import Column, Integer, Float, DateTime
from datetime import datetime
from app.utils.database import Base

class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    temperature = Column(Float)
    humidity = Column(Float)
    co = Column(Float)
    mq135 = Column(Float)
    pm25 = Column(Float)
    datetime = Column(DateTime, default=datetime.now(datetime.timezone.utc))
    