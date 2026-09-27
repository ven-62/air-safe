from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Config
from app.core.predictor import AirQualityPredictor
from app.core.gas_units import (
    co_ppm_to_ugm3,
    no2_ppm_to_ugm3,
)

from app.models.sensor_readings import SensorReading
from app.models.calibrated_readings import CalibratedReading
from app.models.forecast import Forecast
from app.models.aqi_predictions import AQIPrediction

from app.core.websocket_manager import ws_manager


def round_up_to_next_hour(dt: datetime) -> datetime:
    """
    Round a timestamp up to the next whole hour, but ONLY when it's
    the last reading of that hour (minute == 59). Any other reading
    keeps its original timestamp untouched.

    Examples:
        07:59:56 -> 08:00:00   (last reading of the hour -> rounded)
        07:59:00 -> 08:00:00   (last reading of the hour -> rounded)
        07:30:00 -> 07:30:00   (mid-hour reading -> unchanged)
        08:00:00 -> 08:00:00   (already on the hour -> unchanged)
    """

    if dt.minute in (58, 59, 60, 1):
        return (
            dt + timedelta(hours=1)
        ).replace(
            minute=0,
            second=0,
            microsecond=0,
        )

    return dt


# =========================================================================
# PAYLOAD BUILDERS
#
# These convert predictor output into the same "components" list shape
# already used by DashboardManager.get_pollutant_data() /
# get_forecast_data(), so Data.js's existing WebSocket parsing code
# works unchanged.
# =========================================================================

def _reading_to_ws_payload(sensor_reading, aqi_result: dict) -> dict:
    """
    Build the /monitor/read/{station_id} WebSocket message for a
    newly saved sensor reading.
    """

    return {
        "station_id": str(sensor_reading.station_id),
        "timestamp": sensor_reading.timestamp.isoformat(),
        "status": aqi_result["category"],
        "components": [
            {"name": "pm25_ugm3", "value": sensor_reading.pm25_ugm3},
            {"name": "co_ugm3", "value": sensor_reading.co_ugm3},
            {"name": "no2_ugm3", "value": sensor_reading.no2_ugm3},
            {"name": "temp_c", "value": sensor_reading.temperature_c},
            {"name": "humidity_pct", "value": sensor_reading.humidity_pct},
            {"name": "aqi", "value": aqi_result["aqi"]},
        ],
    }


def _forecast_result_to_components(result: dict) -> list:
    return [
        {"name": "pm25_ugm3", "value": result["pm2_5_ugm3"]},
        {"name": "co_ugm3", "value": result["co_ugm3"]},
        {"name": "no2_ugm3", "value": result["no2_ugm3"]},
        {"name": "temp_c", "value": result["temperature_c"]},
        {"name": "humidity_pct", "value": result["humidity_pct"]},
        {"name": "aqi", "value": result["aqi"]},
    ]


def _forecast_to_ws_payload(station_id: str, forecast_results: dict) -> dict:
    """
    Build the /monitor/forecast/{station_id} WebSocket message from
    predictor.predict_forecast() output (keys "+h1", "+h2", "+h3").
    """

    horizon_keys = {
        "+h1": "next_first_hour",
        "+h2": "next_second_hour",
        "+h3": "next_third_hour",
    }

    forecast_payload = {}

    for horizon_key, result in forecast_results.items():
        mapped_key = horizon_keys.get(horizon_key)

        if mapped_key:
            forecast_payload[mapped_key] = _forecast_result_to_components(result)

    return {
        "station_id": str(station_id),
        "forecast": forecast_payload,
    }


class StationManager:

    def __init__(self):

        self.stn1_predictor = AirQualityPredictor(
            # hf_repo_id=Config.HF_REPO_ID,
            # hf_token=Config.HF_TOKEN,
            # sensor_calibration_path="calibration/1_quantile_mapping.json",
        )

        self.stn2_predictor = AirQualityPredictor(
            # hf_repo_id=Config.HF_REPO_ID,
            # hf_token=Config.HF_TOKEN,   
            # sensor_calibration_path="calibration/2_quantile_mapping.json",
        )

    # GET PREDICTOR
    def get_predictor(self, station_id: str):

        if station_id == "1":
            return self.stn1_predictor

        elif station_id == "2":
            return self.stn2_predictor

        raise ValueError(
            f"Unknown station_id: {station_id}"
        )

    # PROCESS STATION DATA
    async def process_station_data(
        self,
        station_id: str,
        data: dict,
        db: Session,
        is_last: bool = False,
    ):
        """
        Complete station pipeline:

        1. Receive ESP32 data
        2. Convert gas units
        3. Save raw sensor reading
        4. Load reading into predictor
        5. Predict current AQI
        6. Predict 1/2/3-hour forecasts
        7. Save predictions
        """

        # 1. GET SENSOR DATA
        pm2_5 = data.get("pm2_5")
        co_ugm3 = data.get("mq7_ugm3")
        no2_ugm3 = data.get("mq135_ugm3")
        humidity = data.get("humidity")
        temperature = data.get("temperature")
        timestamp = data.get("timestamp")

        if timestamp is None:
            timestamp = datetime.now(ZoneInfo("Asia/Manila")).strftime("%Y-%m-%dT%H:%M:%S")
            # raise ValueError(
            #     "Sensor reading is missing timestamp."
            # )

        # 2. PARSE TIMESTAMP
        reading_dt = (
            timestamp
            if isinstance(timestamp, datetime)
            else datetime.fromisoformat(timestamp)
        )

        # 3. CONVERT GAS UNITS
        # co_ugm3 = co_ppm_to_ugm3(
        #     mq7_ppm,
        #     temperature_c=temperature,
        # )

        # no2_ugm3 = no2_ppm_to_ugm3(
        #     mq135_ppm,
        #     temperature_c=temperature,
        # )

        # 4. TIMESTAMP TO SAVE
        #
        # round_up_to_next_hour() only rounds when this is truly the
        # last reading of the hour (minute == 59); any other reading
        # keeps its original timestamp.
        saved_timestamp = round_up_to_next_hour(reading_dt)

        # 5. SAVE SENSOR READING
        sensor_reading = SensorReading(
            station_id=int(station_id),

            timestamp=saved_timestamp,

            pm25_ugm3=pm2_5,
            co_ugm3=co_ugm3,
            no2_ugm3=no2_ugm3,

            temperature_c=temperature,
            humidity_pct=humidity,
        )

        print(
            f"PM2.5: {pm2_5}, CO: {co_ugm3}, NO2: {no2_ugm3}, "
            f"Temp: {temperature}, Humidity: {humidity}, "
            f"Timestamp: {saved_timestamp}"
        )

        db.add(sensor_reading)
        db.commit()
        db.refresh(sensor_reading)

        # At this point:
        #
        # sensor_reading.id
        #
        # is available and is used as the
        # source_reading_id for the predictions.

        # =====================================================================
        # 6. GET STATION PREDICTOR
        predictor = self.get_predictor(
            station_id
        )

        # 7. ADD DATABASE READING TO PREDICTOR
        #
        # IMPORTANT:
        #
        # We are NOT inserting another SensorReading.
        #
        # The SensorReading already exists in the database.
        #
        # The predictor takes that database object and
        # internally performs the calibration/normalization.
        #
        # The calibrated values stay inside predictor history
        # (in-memory only - the database row itself is untouched).
        #

        calibrated = predictor.add_db_reading(
            sensor_reading, db, station_id=station_id
        )

        # 7b. SAVE THE CALIBRATED READING
        #
        # `calibrated` is the dict returned by the predictor after
        # applying quantile mapping (or the raw values unchanged, if
        # the station has no calibration file yet). This is the
        # "calibrate -> save calibrated data to DB" step: it's a
        # separate row from the raw SensorReading, timestamped the
        # same, so the two can be paired later by (station_id, timestamp).

        calibrated_reading = CalibratedReading(
            station_id=int(station_id),
            timestamp=sensor_reading.timestamp,
            pm25_ugm3=calibrated["pm2_5_ugm3"],
            co_ugm3=calibrated["co_ugm3"],
            no2_ugm3=calibrated["no2_ugm3"],
            temperature_c=calibrated["temperature_c"],
            humidity_pct=calibrated["humidity_pct"],
        )

        db.add(calibrated_reading)
        db.commit()
        db.refresh(calibrated_reading)

        try:
            # 8. CURRENT AQI
            aqi_result = predictor.predict_aqi()

            # Example:
            #
            # {
            #     "timestamp": "...",
            #     "aqi": 42.31,
            #     "category": "Good"
            # }

            # 9. SAVE CURRENT AQI
            #
            # source_reading_id points at the CalibratedReading, not
            # the raw SensorReading - that's what the AQIPrediction/
            # Forecast foreign keys are defined against.
            aqi_prediction = AQIPrediction(
                source_reading_id=calibrated_reading.id,
                aqi=aqi_result["aqi"],
            )

            db.add(
                aqi_prediction
            )

            # 10. FORECAST +1, +2, +3 HOURS
            forecast_results = (
                predictor.predict_forecast()
            )

            # Example:
            #
            # {
            #     "+h1": {...},
            #     "+h2": {...},
            #     "+h3": {...}
            # }

            # 11. SAVE EACH FORECAST
            for horizon_key, result in forecast_results.items():

                # "+h1" -> 1
                # "+h2" -> 2
                # "+h3" -> 3

                horizon = int(
                    horizon_key.replace("+h", "")
                )

                forecast = Forecast(
                    station_id=int(station_id),
                    source_reading_id=calibrated_reading.id,
                    horizon_hours=horizon,
                    pm25_ugm3=result["pm2_5_ugm3"],
                    co_ugm3=result["co_ugm3"],
                    no2_ugm3=result["no2_ugm3"],
                    temperature_c=result["temperature_c"],
                    humidity_pct=result["humidity_pct"],
                    aqi=result["aqi"],
                )

                db.add(forecast)

            # 12. COMMIT ALL PREDICTIONS
            db.commit()

        except ValueError as exc:
            # Not enough predictor history yet to build a feature row
            # (e.g. right after a server restart, before history has
            # been restored). The raw sensor reading is already saved;
            # just skip AQI/forecast for this cycle instead of
            # crashing the ESP32 ingestion endpoint.
            db.rollback()

            print(
                f"[StationManager] Skipping AQI/forecast for station "
                f"{station_id}: {exc}"
            )

            return {
                "station_id": int(station_id),
                "sensor_reading_id": sensor_reading.id,
                "timestamp": sensor_reading.timestamp,
            }

        # =====================================================================
        # 13. BROADCAST OVER WEBSOCKET
        #
        # Anyone currently connected to:
        #
        #   /monitor/read/{station_id}
        #   /monitor/forecast/{station_id}
        #
        # gets this update pushed immediately. Data.js updates the
        # dashboard as soon as the message arrives - no polling, no
        # page refresh. Stations broadcast independently, so this
        # works the same for any number of stations.

        await ws_manager.broadcast_reading(
            station_id,
            _reading_to_ws_payload(sensor_reading, aqi_result),
        )

        await ws_manager.broadcast_forecast(
            station_id,
            _forecast_to_ws_payload(station_id, forecast_results),
        )

        # 14. RETURN RESULTS
        return {
            "station_id": int(station_id),
            "sensor_reading_id": sensor_reading.id,
            "timestamp": sensor_reading.timestamp,
            "aqi": aqi_result,
            "forecast": forecast_results,
        }


station_manager = StationManager()