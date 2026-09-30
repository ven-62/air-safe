import asyncio
import json

import paho.mqtt.client as mqtt

from app.core.database import get_db
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
        # DATABASE SESSION
        # ---------------------------------------------------------

        db = next(get_db())

        try:

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