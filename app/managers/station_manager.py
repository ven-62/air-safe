from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Config
from app.core.predictor import AirQualityPredictor
from app.core.gas_units import (
    co_ppm_to_ugm3,
    no2_ppm_to_ugm3,
)

from app.models.sensor_readings import SensorReading
from app.models.forecast import Forecast
from app.models.aqi_predictions import AQIPrediction


def round_up_to_next_hour(dt: datetime) -> datetime:
    """
    Round datetime up to the next whole hour.

    Examples:
        07:59:56 -> 08:00:00
        07:57:58 -> 08:00:00
        07:30:00 -> 08:00:00
        08:00:00 -> 08:00:00
    """

    if (
        dt.minute == 0
        and dt.second == 0
        and dt.microsecond == 0
    ):
        return dt

    return (
        dt + timedelta(hours=1)
    ).replace(
        minute=0,
        second=0,
        microsecond=0,
    )


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
        mq7_ppm = data.get("mq7_ppm")
        mq135_ppm = data.get("mq135_ppm")
        humidity = data.get("humidity")
        temperature = data.get("temperature")
        timestamp = data.get("timestamp")

        if timestamp is None:
            raise ValueError(
                "Sensor reading is missing timestamp."
            )

        # 2. PARSE TIMESTAMP
        reading_dt = (
            timestamp
            if isinstance(timestamp, datetime)
            else datetime.fromisoformat(timestamp)
        )

        # 3. CONVERT GAS UNITS
        co_ugm3 = co_ppm_to_ugm3(
            mq7_ppm,
            temperature_c=temperature,
        )

        no2_ugm3 = no2_ppm_to_ugm3(
            mq135_ppm,
            temperature_c=temperature,
        )

        # 4. TIMESTAMP TO SAVE
        saved_timestamp = (
            round_up_to_next_hour(reading_dt)
            if is_last
            else reading_dt
        )

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

        db.add(sensor_reading)
        db.commit()
        db.refresh(sensor_reading)

        # At this point:
        #
        # sensor_reading.id
        #
        # is available and can be used as the
        # source_reading_id for the predictions.

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
        # The calibrated values stay inside predictor history.
        #

        predictor.add_db_reading(
            sensor_reading
        )

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
        aqi_prediction = AQIPrediction(
            source_reading_id=sensor_reading.id,
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
                source_reading_id=sensor_reading.id,
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

        # 13. RETURN RESULTS
        return {
            "station_id": int(station_id),
            "sensor_reading_id": sensor_reading.id,
            "timestamp": sensor_reading.timestamp,
            "aqi": aqi_result,
            "forecast": forecast_results,
        }


station_manager = StationManager()