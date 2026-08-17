from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.stations import Station


def seed_stations():
    db: Session = SessionLocal()

    try:
        stations = [
            {
                "name": "Iriga City Station",
                "city": "Iriga City",
                "latitude": 13.4322,
                "longitude": 123.4117,
            },
        ]

        for station_data in stations:

            existing_station = (
                db.query(Station)
                .filter(
                    Station.name == station_data["name"],
                    Station.city == station_data["city"],
                )
                .first()
            )

            if existing_station:
                continue

            db.add(Station(**station_data))

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()