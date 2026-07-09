from app.schemas.station_command import StationCommand


class StationManager:

    async def process_station_data(self, station_id: str, data: dict):
        """Process incoming data from stations. This is a placeholder implementation; to be replace with actual processing logic."""
        pass

station_manager = StationManager()
