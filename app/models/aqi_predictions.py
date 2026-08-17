from datetime import datetime

from sqlalchemy import Float, ForeignKey, DateTime, String, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class AQIPrediction(Base):
    __tablename__ = "aqi_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)

    # Which live reading this forecast was generated from -- lets you trace
    # a forecast back to the exact sensor snapshot that produced it, and
    # later join predicted-vs-actual once that future timestamp arrives.
    source_reading_id: Mapped[int] = mapped_column(
        ForeignKey("sensor_readings.id"), index=True, nullable=False
    )

    aqi: Mapped[float | None] = mapped_column(Float)

    # station = relationship("Station", back_populates="aqi_predictions")
    source_reading = relationship("SensorReading", back_populates="aqi_predictions")