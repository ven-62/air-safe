from pydantic import BaseModel

class StationCommand(BaseModel):

    command: str

    seconds: int | None = None

    sensor: str | None = None

    value: str | None = None

class MultiStationCommand(StationCommand):

    stations: list[str]
