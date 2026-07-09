from sqlalchemy.orm import Session

from app.models.station import Station
from app.schemas.station_command import StationCommand
from app.schemas.station_command import MultiStationCommand


class CommandManager:

    async def execute_command(self, station_id, command: StationCommand, db: Session):
        pass

    async def execute_many(self, stations, command: MultiStationCommand, db: Session):
        pass

    async def execute_all(self, command: StationCommand, db: Session):
        pass

    async def add_station(
        self, name: str, latitude: float, longitude: float, db: Session
    ):
        """Add a new station to the system."""
        existing_stn = db.query(Station).filter_by(name=name).first()

        if existing_stn:
            return {
                "status": "error",
                "message": f"Station with name '{name}' already exists.",
            }

        import random
        import string

        # Generate a random 7 character authentication key for the new station
        auth_key = "".join(random.choices(string.ascii_letters + string.digits, k=7))

        new_station = Station(
            name=name, latitude=latitude, longitude=longitude, auth_key=auth_key
        )
        db.add(new_station)
        db.commit()

        return {
            "status": "success",
            "message": f"Station added successfully.",
            "station_id": new_station.id,
            "auth_key": auth_key,
        }

    async def remove_station(self, station_id: str, db: Session):
        """Remove a station from the system."""
        station = db.query(Station).filter_by(id=station_id).first()

        if not station:
            return {
                "status": "error",
                "message": f"Station with ID '{station_id}' does not exist.",
            }

        db.delete(station)
        db.commit()

        return {
            "status": "success",
            "message": f"Station with ID '{station_id}' removed successfully.",
        }

    async def modify_station(
        self,
        station_id: str,
        name: str = None,
        latitude: float = None,
        longitude: float = None,
        db: Session = None,
    ):
        """Modify a station's details in the system."""
        station = db.query(Station).filter_by(id=station_id).first()

        if not station:
            return {
                "status": "error",
                "message": f"Station with ID '{station_id}' does not exist.",
            }

        if name is not None:
            station.name = name
        if latitude is not None:
            station.latitude = latitude
        if longitude is not None:
            station.longitude = longitude

        db.commit()

        return {
            "status": "success",
            "message": f"Station with ID '{station_id}' modified successfully.",
        }

    async def get_station(self, station_id: str, db: Session):
        return db.query(Station).filter_by(id=station_id).first()


command_manager = CommandManager()
