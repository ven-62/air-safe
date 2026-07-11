from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))

    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    auth_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    sensor_readings = relationship(
        "SensorReading", back_populates="station", cascade="all, delete-orphan"
    )
