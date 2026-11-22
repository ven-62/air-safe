import asyncio
import json
import math

import paho.mqtt.client as mqtt

from app.core.database import get_db
from app.models.stations import Station
from app.managers.station_manager import station_manager
from app.services.station_service import (
    now_local,
    current_window,
    is_active_window,
    prepare_response,
    active_response,
    sleep_response,
)
from app.config import Config

MQTT_HOST = Config.MQTT_HOST
MQTT_PORT = Config.MQTT_PORT

MQTT_USERNAME = Config.MQTT_USERNAME
MQTT_PASSWORD = Config.MQTT_PASSWORD

CHECK_TOPIC = "station/+/check"
READING_TOPIC = "station/+/reading"


class MQTTManager:

    def __init__(self):
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="airsafe-fastapi",
        )

        self.client.username_pw_set(
            MQTT_USERNAME,
            MQTT_PASSWORD,
        )

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.loop = None

    def start(self, loop):
        self.loop = loop

        self.client.connect(
            MQTT_HOST,
            MQTT_PORT,
            keepalive=60,
        )

        self.client.loop_start()

        print("[MQTT] Client started")

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"[MQTT] Connected to broker: {reason_code}")

        client.subscribe(CHECK_TOPIC, qos=1)
        client.subscribe(READING_TOPIC, qos=1)

        print(f"[MQTT] Subscribed: {CHECK_TOPIC}")
        print(f"[MQTT] Subscribed: {READING_TOPIC}")

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"[MQTT] Disconnected: {reason_code}")

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            print()
            print("=" * 60)
            print(f"[MQTT] Message received")
            print(f"[MQTT] Topic   : {topic}")
            print(f"[MQTT] Payload : {payload}")
            print("=" * 60)

            parts = topic.split("/")

            if len(parts) != 3:
                print("[MQTT] Invalid topic")
                return

            station_id = parts[1]
            message_type = parts[2]

            if self.loop is None:
                print("[MQTT] Event loop is not available")
                return

            if message_type == "check":
                future = asyncio.run_coroutine_threadsafe(
                    self.handle_check(station_id, payload),
                    self.loop,
                )
                future.add_done_callback(self._log_task_exception)

            elif message_type == "reading":
                future = asyncio.run_coroutine_threadsafe(
                    self.handle_reading(station_id, payload),
                    self.loop,
                )
                future.add_done_callback(self._log_task_exception)

        except Exception as exc:
            print(f"[MQTT] Message error: {exc}")

    @staticmethod
    def _log_task_exception(future):
        # run_coroutine_threadsafe() hands back a concurrent.futures.Future.
        # If handle_check()/handle_reading() raises, that exception is
        # stored on the future and NEVER surfaces unless something calls
        # .result()/.exception() on it — otherwise the station's message
        # just silently vanishes with no server-side log at all, which is
        # indistinguishable from a dropped MQTT message. This callback
        # makes sure a crash is always printed instead of swallowed.
        exc = future.exception()
        if exc is not None:
            print(f"[MQTT] Handler task failed: {exc!r}")

    async def handle_check(self, station_id, data):
        print(f"[CHECK] RECEIVED from station {station_id}")

        now = now_local()
        print(f"[CHECK] Station {station_id} at {now.isoformat()}")

        active, mode, reading_start, reading_end = is_active_window(now)

        if active:
            response = active_response(
                mode, reading_start, reading_end
            )
        else:
            mode, prepare_start, reading_start, reading_end = current_window(now)

            if mode is not None and prepare_start <= now < reading_start:
                response = prepare_response(
                    mode, prepare_start, reading_start, reading_end
                )
            else:
                response = sleep_response("outside_window")

        print(f"[CHECK] Response: {response}")
        self.publish_command(station_id, response)

    # async def handle_check(self, station_id, data):
    #     print(f"[CHECK] RECEIVED from station {station_id}")

    #     now = now_local()

    #     print(f"[CHECK] Station {station_id} at {now.isoformat()}")

    #     # ---------------------------------------------------------
    #     # ACTIVE READING WINDOW
    #     # ---------------------------------------------------------

    #     active, mode, reading_start, reading_end = is_active_window(now)

    #     if active:
    #         print(
    #             f"[CHECK] Station {station_id}: READ ({mode}) "
    #             f"{reading_start} -> {reading_end}"
    #         )

    #         response = active_response(
    #             mode,
    #             reading_start,
    #             reading_end,
    #         )

    #         self.publish_command(
    #             station_id,
    #             response,
    #         )

    #         return

    #     # ---------------------------------------------------------
    #     # PREPARATION WINDOW
    #     # ---------------------------------------------------------

    #     mode, prepare_start, reading_start, reading_end = current_window(now)

    #     if (
    #         mode is not None
    #         and prepare_start <= now < reading_start
    #     ):

    #         print(
    #             f"[CHECK] Station {station_id}: PREPARE ({mode}) "
    #             f"reading starts at {reading_start}"
    #         )

    #         response = prepare_response(
    #             mode,
    #             prepare_start,
    #             reading_start,
    #             reading_end,
    #         )

    #         self.publish_command(
    #             station_id,
    #             response,
    #         )

    #         return

    #     # ---------------------------------------------------------
    #     # OUTSIDE WINDOW
    #     # ---------------------------------------------------------

    #     print(f"[CHECK] Station {station_id}: SLEEP")

    #     response = sleep_response(
    #         "outside_window"
    #     )

    #     self.publish_command(
    #         station_id,
    #         response,
    #     )

    async def handle_reading(self, station_id, data):

        now = now_local()

        print("=" * 60)
        print(f"[READING] Station       : {station_id}")
        print(f"[READING] Server Time   : {now}")
        print(f"[READING] AVERAGED      : True")
        print(f"[READING] Sample Count  : {data.get('sample_count', 0)}")
        print(f"[READING] PM2.5         : {data.get('pm2_5')}")
        print(f"[READING] CO (MQ7)      : {data.get('mq7_ugm3')}")
        print(f"[READING] NO2 (MQ135)   : {data.get('mq135_ugm3')}")
        print(f"[READING] Humidity      : {data.get('humidity')}")
        print(f"[READING] Temperature   : {data.get('temperature')}")
        print(f"[READING] Location      : {data.get('lat')}, {data.get('lon')}")
        print("=" * 60)

        # ---------------------------------------------------------
        # VALIDATE
        # ---------------------------------------------------------

        required_fields = [
            "pm2_5",
            "mq7_ugm3",
            "mq135_ugm3",
            "humidity",
            "temperature",
        ]

        missing = [
            field
            for field in required_fields
            if field not in data
        ]

        if missing:
            print(
                f"[MQTT] Missing fields: {', '.join(missing)}"
            )

            self.publish_command(
                station_id,
                {
                    "status": "error",
                    "action": "sleep",
                    "sleep_seconds": 60,
                },
            )

            return

        # ---------------------------------------------------------
        # OPTIONAL GPS LOCATION
        # ---------------------------------------------------------
        # lat/lon are NOT in required_fields on purpose: old firmware,
        # and cycles before the first GPS fix, send no location and
        # must still be accepted.

        location = self._parse_location(data)

        # ---------------------------------------------------------
        # DATABASE SESSION
        # ---------------------------------------------------------

        db = next(get_db())

        try:

            if location is not None:
                self.update_station_location(station_id, location, db)

            await station_manager.process_station_data(
                station_id,
                data,
                db,
                is_last=True,
            )

        except Exception as exc:

            import traceback
            tb = traceback.format_exc()
            print(tb)

            db.rollback()

            self.publish_command(
                station_id,
                {
                    "status": "error",
                    "action": "sleep",
                    "sleep_seconds": 60,
                    "debug": tb.strip().splitlines()[-4:],
                },
            )

            return

        finally:
            db.close()

        # ---------------------------------------------------------
        # TELL ESP32 TO SLEEP
        # ---------------------------------------------------------

        next_sleep = sleep_response(
            "reading_complete"
        )

        response = {
            "status": "success",
            "action": "sleep",
            "message": "Averaged reading stored",
            "sleep_seconds": next_sleep["sleep_seconds"],
            "next_prepare_start": next_sleep[
                "next_prepare_start"
            ],
        }

        print(
            f"[READING] Station {station_id}: "
            f"SLEEP for {response['sleep_seconds']} seconds"
        )

        self.publish_command(
            station_id,
            response,
        )

    @staticmethod
    def _parse_location(data):
        """Return {'lat','lon','hdop','sats'} or None if absent/invalid."""
        lat = data.get("lat")
        lon = data.get("lon")

        if lat is None or lon is None:
            return None

        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return None

        # Reject out-of-range values and the (0, 0) "null island" default.
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None
        if lat == 0.0 and lon == 0.0:
            return None

        return {
            "lat": lat,
            "lon": lon,
            "hdop": data.get("gps_hdop"),
            "sats": data.get("gps_sats"),
        }

    @staticmethod
    def _distance_m(lat1, lon1, lat2, lon2):
        """Haversine distance in metres."""
        r = 6371000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = p2 - p1
        dlmb = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        )
        return 2 * r * math.asin(math.sqrt(a))

    def update_station_location(self, station_id, location, db):
        """
        Save the GPS position into stations.latitude / stations.longitude
        (the same columns /monitor/stations already serves to the frontend).

        Only writes when the stored position is empty or differs by more
        than MOVE_THRESHOLD_M, so GPS jitter doesn't cause a DB write on
        every reading. Never raises: a location problem must not stop the
        sensor reading from being stored.
        """
        MOVE_THRESHOLD_M = 50.0

        try:
            station = (
                db.query(Station)
                .filter(Station.id == int(station_id))
                .first()
            )

            if station is None:
                print(f"[GPS] Unknown station {station_id}, location ignored")
                return

            if (
                station.latitude is not None
                and station.longitude is not None
                and self._distance_m(
                    station.latitude,
                    station.longitude,
                    location["lat"],
                    location["lon"],
                ) <= MOVE_THRESHOLD_M
            ):
                return  # same place, nothing to update

            station.latitude = location["lat"]
            station.longitude = location["lon"]
            db.commit()

            print(
                f"[GPS] Station {station_id} location updated: "
                f"{location['lat']}, {location['lon']}"
            )

        except Exception as exc:
            db.rollback()
            print(f"[GPS] Could not update station {station_id} location: {exc!r}")

    def publish_command(self, station_id, payload):

        topic = f"station/{station_id}/command"

        message = json.dumps(
            payload,
            default=str,
        )

        result = self.client.publish(
            topic,
            message,
            qos=1,
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:

            print(
                f"[MQTT] Published command → {topic}"
            )

            print(
                f"[MQTT] {message}"
            )

        else:

            print(
                f"[MQTT] Failed publishing command: "
                f"{result.rc}"
            )


mqtt_manager = MQTTManager()