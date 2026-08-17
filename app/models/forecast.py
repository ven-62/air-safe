from datetime import datetime

from sqlalchemy import Float, ForeignKey, DateTime, String, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Forecast(Base):
    __tablename__ = "forecast"

    id: Mapped[int] = mapped_column(primary_key=True)

    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)

    # Which live reading this forecast was generated from -- lets you trace
    # a forecast back to the exact sensor snapshot that produced it, and
    # later join predicted-vs-actual once that future timestamp arrives.
    source_reading_id: Mapped[int] = mapped_column(
        ForeignKey("sensor_readings.id"), index=True, nullable=False
    )

    horizon_hours: Mapped[int] = mapped_column(Integer, index=True)  # 1, 2, or 3

    pm25_ugm3: Mapped[float | None] = mapped_column(Float)
    co_ugm3: Mapped[float | None] = mapped_column(Float)
    no2_ugm3: Mapped[float | None] = mapped_column(Float)

    temperature_c: Mapped[float | None] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float)

    aqi: Mapped[float | None] = mapped_column(Float)

    source_reading = relationship("SensorReading", back_populates="forecasts")