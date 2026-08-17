from datetime import datetime
from sqlalchemy import Float, ForeignKey, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class SensorReading(Base):
    """Raw sensor readings"""
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True)

    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    pm25_ugm3: Mapped[float | None] = mapped_column(Float)
    co_ugm3: Mapped[float | None] = mapped_column(Float)
    no2_ugm3: Mapped[float | None] = mapped_column(Float)

    temperature_c: Mapped[float | None] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float)

    station = relationship("Station", back_populates="sensor_readings")

    # The AQI predictions generated from this sensor reading
    aqi_predictions = relationship(
        "AQIPrediction", back_populates="source_reading", cascade="all, delete-orphan"
    )
    # The forecast readings generated from this sensor reading
    forecasts = relationship(
        "Forecast", back_populates="source_reading", cascade="all, delete-orphan"
    )