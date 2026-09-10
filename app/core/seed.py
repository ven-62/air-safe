from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.stations import Station


def seed_stations():
    db: Session = SessionLocal()

    try:
        stations = [
            {
                "name": "Plaza Rizal", # Station 1
                "city": "Naga City",
                "latitude": 13.623170003841329,
                "longitude": 123.18480740588977,
            },
            {
                "name": "Naga City People's Mall", # Station 2
                "city": "Naga City",
                "latitude": 13.621406356892528,
                "longitude": 123.1836669824267
            }
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