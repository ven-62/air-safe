"""
WebSocket connection manager.

Keeps track of every connected frontend client, grouped by:

    channel     -> "read" or "forecast"
    station_id  -> "1", "2", ...

This lets the server push a new reading/forecast to every client
currently watching a given station, on any channel, the moment it
is computed - without the frontend needing to poll or refresh.

This module does NOT touch the database, the predictor, or any
calibration/AQI/forecast logic. It only fans out already-built
payloads to connected WebSocket clients.
"""

import asyncio
from typing import Dict, Set

from fastapi import WebSocket


class WebSocketManager:
    """
    Manages WebSocket connections for real-time station broadcasts.

    Two independent channels are supported per station:

        "read"     -> latest sensor reading / current AQI
                       (mirrors GET /monitor/read/{station_id})

        "forecast" -> 1/2/3-hour forecast
                       (mirrors GET /monitor/forecast/{station_id})

    Multiple stations and multiple simultaneous clients per
    station/channel are supported.
    """

    def __init__(self):
        self._connections: Dict[str, Dict[str, Set[WebSocket]]] = {
            "read": {},
            "forecast": {},
        }
        self._lock = asyncio.Lock()

    # CONNECT

    async def connect(self, channel: str, station_id: str, websocket: WebSocket):
        station_id = str(station_id)

        await websocket.accept()

        async with self._lock:
            self._connections[channel].setdefault(station_id, set()).add(websocket)

        print(f"[WS] {channel} client connected: station {station_id}")

    # DISCONNECT

    async def disconnect(self, channel: str, station_id: str, websocket: WebSocket):
        station_id = str(station_id)

        async with self._lock:
            clients = self._connections[channel].get(station_id)

            if clients is not None:
                clients.discard(websocket)

                if not clients:
                    self._connections[channel].pop(station_id, None)

        print(f"[WS] {channel} client disconnected: station {station_id}")

    # BROADCAST

    async def broadcast(self, channel: str, station_id: str, message: dict):
        """
        Send `message` (JSON-serializable) to every client currently
        connected to `channel` for `station_id`. Silently does
        nothing if nobody is connected.
        """

        station_id = str(station_id)

        async with self._lock:
            # Snapshot so we don't mutate the set while iterating.
            clients = list(self._connections[channel].get(station_id, ()))

        if not clients:
            return

        dead = []

        for websocket in clients:
            try:
                await websocket.send_json(message)
            except Exception:
                # Client likely disconnected without a clean close
                # handshake; mark it for removal.
                dead.append(websocket)

        if dead:
            async with self._lock:
                live = self._connections[channel].get(station_id)

                if live is not None:
                    for websocket in dead:
                        live.discard(websocket)

                    if not live:
                        self._connections[channel].pop(station_id, None)

    async def broadcast_reading(self, station_id: str, payload: dict):
        """ Broadcast a new sensor reading / current AQI to /monitor/read/{station_id}. """
        await self.broadcast("read", station_id, payload)

    async def broadcast_forecast(self, station_id: str, payload: dict):
        """ Broadcast a new 1/2/3-hour forecast to /monitor/forecast/{station_id}. """
        await self.broadcast("forecast", station_id, payload)


# Single shared instance used across the app (routes + station_manager).
ws_manager = WebSocketManager()