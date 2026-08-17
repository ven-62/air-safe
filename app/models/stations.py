from sqlalchemy import Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Station(Base):
    __tablename__ = "stations"

    __table_args__ = (
        UniqueConstraint(
            "name",
            "city",
            name="uq_station_name_city",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))

    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    sensor_readings = relationship(
        "SensorReading",
        back_populates="station",
        cascade="all, delete-orphan",
    )