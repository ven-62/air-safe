from app.schemas.station_command import StationCommand
from app.schemas.station_command import MultiStationCommand

class CommandManager:

    async def execute_command(self, station_id, command: StationCommand):
        pass

    async def execute_many(self, stations, command: MultiStationCommand):
        pass

    async def execute_all(self, command: StationCommand):
        pass
     
    async def add_station(self, name: str, latitude: float, longitude: float):
        pass

    async def remove_station(self, station_id: str):
        pass

    async def modify_station(self, station_id: str, name: str = None, latitude: float = None, longitude: float = None):
        pass

    async def get_station(self, station_id: str):
        pass

command_manager = CommandManager()