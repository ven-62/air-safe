from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.stations import Station
from app.models.sensor_readings import SensorReading
from app.models.calibrated_readings import CalibratedReading
from app.models.aqi_predictions import AQIPrediction
from app.models.forecast import Forecast

from app.managers.station_manager import station_manager


# HORIZON -> RESPONSE KEY
#
# Matches the shape Data.js already expects from
# GET/WS /monitor/forecast/{station_id}.
_HORIZON_KEYS = {
    1: "next_first_hour",
    2: "next_second_hour",
    3: "next_third_hour",
}

# "No data yet" shape for /monitor/read/{station_id}. Keeps the
# response shape stable (same keys, null values) instead of a 404,
# so the frontend doesn't need special-case handling for a brand
# new station that hasn't reported in yet.
_EMPTY_COMPONENTS = [
    {"name": "pm25_ugm3", "value": None},
    {"name": "co_ugm3", "value": None},
    {"name": "no2_ugm3", "value": None},
    {"name": "temp_c", "value": None},
    {"name": "humidity_pct", "value": None},
    {"name": "aqi", "value": None},
]


def _category_from_aqi(aqi_value: Optional[float], predictor) -> Optional[str]:
    """
    Recompute the AQI category label from a stored AQI number, using
    the same bins/labels the predictor used to produce it.

    AQIPrediction only stores the numeric `aqi`, not the category
    string, so this is re-derived on read rather than duplicated in
    the database.
    """

    if aqi_value is None:
        return None

    category = pd.cut(
        [aqi_value],
        bins=predictor.aqi_bins,
        labels=predictor.aqi_labels,
    )[0]

    return str(category)


def _components_from_values(
    pm25_ugm3, co_ugm3, no2_ugm3, temperature_c, humidity_pct, aqi
) -> List[Dict[str, any]]:
    return [
        {"name": "pm25_ugm3", "value": pm25_ugm3},
        {"name": "co_ugm3", "value": co_ugm3},
        {"name": "no2_ugm3", "value": no2_ugm3},
        {"name": "temp_c", "value": temperature_c},
        {"name": "humidity_pct", "value": humidity_pct},
        {"name": "aqi", "value": aqi},
    ]


class DashboardManager:
    """
    Reads pollutant/forecast/history/station data from the database.

    Tables involved:

        SensorReading       raw ESP32 readings
        CalibratedReading   calibrated version of each SensorReading,
                             paired by (station_id, timestamp)
        AQIPrediction       current-AQI prediction, FK -> CalibratedReading
        Forecast            1/2/3-hour forecast rows, FK -> CalibratedReading
        Station             station metadata (name, city, lat/lng)
    """

    # CURRENT READING + AQI

    async def get_pollutant_data(self, station_id: str, db: Session) -> Dict[str, any]:
        """
        Latest raw reading for a station, paired with its predicted
        AQI/category if one has been computed yet.

        /monitor/read/{station_id}
        """

        latest_reading = (
            db.query(SensorReading)
            .filter(SensorReading.station_id == int(station_id))
            .order_by(SensorReading.timestamp.desc())
            .first()
        )

        if latest_reading is None:
            return {
                "station_id": str(station_id),
                "timestamp": None,
                "status": "No Data",
                "components": _EMPTY_COMPONENTS,
            }

        aqi_prediction = self._latest_aqi_prediction(
            db, station_id, timestamp=latest_reading.timestamp
        )

        aqi_value = aqi_prediction.aqi if aqi_prediction else None
        category = (
            _category_from_aqi(aqi_value, station_manager.get_predictor(str(station_id)))
            if aqi_value is not None
            else "No Data"
        )

        return {
            "station_id": str(station_id),
            "timestamp": latest_reading.timestamp.isoformat(),
            "status": category,
            "components": _components_from_values(
                latest_reading.pm25_ugm3,
                latest_reading.co_ugm3,
                latest_reading.no2_ugm3,
                latest_reading.temperature_c,
                latest_reading.humidity_pct,
                aqi_value,
            ),
        }

    def _latest_aqi_prediction(
        self, db: Session, station_id: str, timestamp=None
    ) -> Optional[AQIPrediction]:
        """
        Find the AQIPrediction tied to this station's calibrated
        reading. Prefers the prediction from the exact same timestamp
        as the given raw reading (they're produced together in the
        same pipeline run); falls back to the most recent one for the
        station if no exact match exists.
        """

        base_query = (
            db.query(AQIPrediction)
            .join(
                CalibratedReading,
                AQIPrediction.source_reading_id == CalibratedReading.id,
            )
            .filter(CalibratedReading.station_id == int(station_id))
        )

        if timestamp is not None:
            matched = (
                base_query.filter(CalibratedReading.timestamp == timestamp)
                .order_by(AQIPrediction.id.desc())
                .first()
            )

            if matched is not None:
                return matched

        return (
            base_query.order_by(CalibratedReading.timestamp.desc(), AQIPrediction.id.desc())
            .first()
        )

    # FORECAST

    async def get_forecast_data(self, station_id: str, db: Session) -> Dict[str, any]:
        """
        The 1/2/3-hour forecast generated from the station's most
        recent calibrated reading.

        /monitor/forecast/{station_id}
        """

        latest_calibrated = (
            db.query(CalibratedReading)
            .filter(CalibratedReading.station_id == int(station_id))
            .order_by(CalibratedReading.timestamp.desc())
            .first()
        )

        if latest_calibrated is None:
            return {
                "station_id": str(station_id),
                "forecast": {},
            }

        forecast_rows = (
            db.query(Forecast)
            .filter(Forecast.source_reading_id == latest_calibrated.id)
            .all()
        )

        forecast_payload = {}

        for row in forecast_rows:
            key = _HORIZON_KEYS.get(row.horizon_hours)

            if key:
                forecast_payload[key] = _components_from_values(
                    row.pm25_ugm3,
                    row.co_ugm3,
                    row.no2_ugm3,
                    row.temperature_c,
                    row.humidity_pct,
                    row.aqi,
                )

        return {
            "station_id": str(station_id),
            "forecast": forecast_payload,
        }

    # STATIONS

    def get_all_stations(self, db: Session) -> List[Dict[str, any]]:
        """
        All registered stations.

        /monitor/stations
        """

        stations = db.query(Station).order_by(Station.id).all()

        return [
            {
                "station_id": str(station.id),
                "name": station.name,
                "city": station.city,
                "latitude": station.latitude,
                "longitude": station.longitude,
            }
            for station in stations
        ]

    # HISTORY

    async def get_latest_history(
        self, station_id: str, db: Session, limit: int = 24
    ) -> List[Dict[str, any]]:
        """
        Last `limit` raw readings for a station (newest first), each
        paired with its predicted AQI if one exists.

        /monitor/history/{station_id}
        """

        rows = (
            db.query(SensorReading, AQIPrediction)
            .outerjoin(
                CalibratedReading,
                and_(
                    CalibratedReading.station_id == SensorReading.station_id,
                    CalibratedReading.timestamp == SensorReading.timestamp,
                ),
            )
            .outerjoin(
                AQIPrediction,
                AQIPrediction.source_reading_id == CalibratedReading.id,
            )
            .filter(SensorReading.station_id == int(station_id))
            .order_by(SensorReading.timestamp.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "timestamp": reading.timestamp.timestamp(),
                "pm25_ugm3": reading.pm25_ugm3,
                "co_ugm3": reading.co_ugm3,
                "no2_ugm3": reading.no2_ugm3,
                "temp_c": reading.temperature_c,
                "humidity_pct": reading.humidity_pct,
                "aqi": aqi_prediction.aqi if aqi_prediction else None,
            }
            for reading, aqi_prediction in rows
        ]


dashboard_manager = DashboardManager()