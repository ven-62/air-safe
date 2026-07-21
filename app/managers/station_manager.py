from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Config
from app.schemas.station_command import StationCommand
from app.core.predictor import AirQualityPredictor
from app.core.gas_units import co_ppm_to_ugm3, no2_ppm_to_ugm3
from app.models.sensor_readings import SensorReading
from app.models.forecast_readings import ForecastReading


class StationManager:

    def __init__(self):
        self.predictor = AirQualityPredictor(
            hf_repo_id=Config.HF_REPO_ID,
            sensor_calibration_path="sensor_calibration.json",
        )

    async def process_station_data(self, station_id: str, data: dict, db: Session):
        """Process incoming data from stations: convert units, calibrate, predict, persist."""
        pm2_5 = data.get("pm2_5")              # ug/m3 (PMS7003 -- already physical units)
        mq7_ppm = data.get("mq7_ppm")          # ppm (MQ7, post Rs/Ro curve)
        mq135_ppm = data.get("mq135_ppm")      # ppm (MQ135, post Rs/Ro curve)
        humidity = data.get("humidity")        # %
        temperature = data.get("temperature")  # degC
        timestamp = data.get("timestamp")

        print(f"PM 2.5: {pm2_5}")
        print(f"MQ7 PPM: {mq7_ppm}")
        print(f"MQ135 PPM: {mq135_ppm}")
        print(f"Humidity: {humidity}")
        print(f"Temperature: {temperature}")
        print(f"Timestamp: {timestamp}")
        # reading_dt = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(timestamp)

        # # --- Stage 1 (second half): ppm -> ug/m3, temperature-corrected,
        # # only used to feed the predictor -- raw ppm is what gets persisted ---
        # co_ugm3 = co_ppm_to_ugm3(mq7_ppm, temperature_c=temperature)
        # no2_ugm3 = no2_ppm_to_ugm3(mq135_ppm, temperature_c=temperature)

        # # --- Stage 2 + prediction: add_sensor_reading() runs quantile
        # # calibration internally, then appends to the rolling history buffer ---
        # self.predictor.add_sensor_reading({
        #     "pm25": pm2_5,
        #     "co": co_ugm3,
        #     "no2": no2_ugm3,
        #     "temperature": temperature,
        #     "humidity": humidity,
        #     "timestamp": reading_dt,
        # })

        # current = self.predictor.predict_aqi()
        # forecast = self.predictor.predict_forecast()  # {"+h1": {...}, "+h2": {...}, "+h3": {...}}

        # # --- Persist the raw reading + prediction result ---
        # reading = SensorReading(
        #     station_id=station_id,
        #     timestamp=reading_dt,
        #     pm25_ugm3=pm2_5,
        #     co_ppm=mq7_ppm,
        #     no2_ppm=mq135_ppm,
        #     temperature_c=temperature,
        #     humidity_pct=humidity,
        #     aqi=current["aqi"],
        #     status=current["category"],
        # )
        # db.add(reading)
        # db.flush()  # assigns reading.id without a full commit, so ForecastReading rows can reference it

        # # --- Persist each horizon's forecast, linked back to this reading ---
        # for key, values in forecast.items():           # key like "+h1", "+h2", "+h3"
        #     horizon_hours = int(key.lstrip("+h"))
        #     db.add(ForecastReading(
        #         station_id=station_id,
        #         source_reading_id=reading.id,
        #         horizon_hours=horizon_hours,
        #         predicted_for=reading_dt + timedelta(hours=horizon_hours),
        #         pm25_ugm3=values["pm2_5_ugm3"],
        #         co_ugm3=values["co_ugm3"],
        #         no2_ugm3=values["no2_ugm3"],
        #         temperature_c=values["temperature_c"],
        #         humidity_pct=values["humidity_pct"],
        #         aqi=values["aqi"],
        #         status=values["category"],
        #     ))

        # db.commit()
        # db.refresh(reading)

        # return {
        #     "reading_id": reading.id,
        #     "current": current,
        #     "forecast": forecast,
        # }

    async def forecast():
        pass

    
station_manager = StationManager()