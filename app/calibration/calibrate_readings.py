"""
Rolling Bias Correction for Air Quality Monitoring.

Live sources:
    - OpenWeatherMap Air Pollution API -> pm2.5, co, no2
    - Open-Meteo Forecast API          -> temperature, humidity

Expected `history_df` schema (rows spanning the trailing 6-hour window, any cadence):
    datetime_ph, pm25_api, pm25_sensor, co_api, co_sensor, no2_api, no2_sensor

`sensor_data` : {"pm25_ugm3": float|None, "co_ugm3": float|None, "no2_ugm3": float|None}
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sensor_readings import SensorReading  # adjust to your actual import path
from app.config import Config

OWM_API_KEY = Config.OWM_API_KEY

# Canonical internal pollutant keys — decoupled from any one source's field names,
# so a single mapping controls how each source's naming is translated.
POLLUTANTS = ("pm25", "co", "no2")
SENSOR_ATTR = {"pm25": "pm25_ugm3", "co": "co_ugm3", "no2": "no2_ugm3"}  # SensorReading columns
OWM_COMPONENT = {"pm25": "pm2_5", "co": "co", "no2": "no2"}  # OWM JSON component keys
OUTPUT_KEY = {"pm25": "pm25_ugm3", "co": "co_ugm3", "no2": "no2_ugm3"}  # final output keys

ROLLING_WINDOW_HOURS = 6
MIN_MULTIPLIER = 0.3
MAX_MULTIPLIER = 3.0

OWM_AIR_POLLUTION_URL = "https://api.openweathermap.org/data/2.5/air_pollution"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Naga City, Bicol Region, PH — default deployment coordinates.
DEFAULT_LAT = 13.62326
DEFAULT_LON = 123.18493

REQUEST_TIMEOUT_SECONDS = 10

HISTORY_COLUMNS = ["datetime_ph"] + [
    f"{p}_{source}" for p in POLLUTANTS for source in ("api", "sensor")
]


def fetch_owm_air_pollution(
    owm_api_key: str = OWM_API_KEY, lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON
) -> dict:
    """Fetch current PM2.5, CO, NO2 from the OpenWeatherMap Air Pollution API."""
    params = {"lat": lat, "lon": lon, "appid": owm_api_key}
    response = requests.get(
        OWM_AIR_POLLUTION_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    components = response.json()["list"][0]["components"]

    return {p: components.get(OWM_COMPONENT[p]) for p in POLLUTANTS}


def fetch_open_meteo_weather(
    lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON
) -> dict:
    """Fetch current temperature and relative humidity from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m",
    }
    response = requests.get(
        OPEN_METEO_FORECAST_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    current = response.json()["current"]

    return {
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
    }


def fetch_current_api_data(
    owm_api_key: str = OWM_API_KEY, lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON
) -> dict:
    """Combine OWM pollutant data and Open-Meteo weather data into one dict."""
    api_data = fetch_owm_air_pollution(owm_api_key, lat, lon)
    api_data.update(fetch_open_meteo_weather(lat, lon))
    return api_data


def fetch_owm_air_pollution_history(
    start: datetime,
    end: datetime,
    owm_api_key: str = OWM_API_KEY,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
) -> list[dict]:
    """Fetch hourly historical PM2.5/CO/NO2 from OWM between start and end (UTC)."""
    params = {
        "lat": lat,
        "lon": lon,
        "start": int(start.timestamp()),
        "end": int(end.timestamp()),
        "appid": owm_api_key,
    }
    response = requests.get(
        f"{OWM_AIR_POLLUTION_URL}/history",
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    entries = response.json()["list"]

    return [
        {
            "timestamp": datetime.fromtimestamp(e["dt"], tz=timezone.utc),
            **{p: e["components"].get(OWM_COMPONENT[p]) for p in POLLUTANTS},
        }
        for e in entries
    ]


def fetch_sensor_history(
    db: Session, station_id: int, since: datetime
) -> list[SensorReading]:
    """Fetch all sensor readings for a station since a cutoff timestamp, oldest first."""
    stmt = (
        select(SensorReading)
        .where(SensorReading.station_id == station_id)
        .where(SensorReading.timestamp >= since)
        .order_by(SensorReading.timestamp.asc())
    )
    return list(db.execute(stmt).scalars().all())


def build_history_df(
    db: Session,
    station_id: int,
    owm_api_key: str = OWM_API_KEY,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    window_hours: int = ROLLING_WINDOW_HOURS,
    now: Optional[datetime] = None,
) -> pd.DataFrame:
    """Build the rolling-correction history DataFrame from DB sensor readings + OWM history.

    Sensor readings arrive every 15-30 min; OWM pollutant data is hourly. Each sensor
    reading is paired with the most recent OWM value at or before its timestamp
    (forward-filled), via pd.merge_asof.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    sensor_rows = fetch_sensor_history(db, station_id, since=cutoff)
    if not sensor_rows:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    sensor_df = pd.DataFrame(
        [
            {
                "timestamp": row.timestamp,
                **{f"{p}_sensor": getattr(row, SENSOR_ATTR[p]) for p in POLLUTANTS},
            }
            for row in sensor_rows
        ]
    ).sort_values("timestamp")

    # Pad the OWM fetch start by 1h so the earliest sensor reading has a prior
    # hourly value to forward-fill from, even if it lands right at the window edge.
    owm_history = fetch_owm_air_pollution_history(
        sensor_df["timestamp"].iloc[0] - timedelta(hours=1),
        now,
        owm_api_key,
        lat,
        lon,
    )
    owm_df = pd.DataFrame(owm_history).rename(columns={p: f"{p}_api" for p in POLLUTANTS})
    if owm_df.empty:
        owm_df = pd.DataFrame(columns=["timestamp"] + [f"{p}_api" for p in POLLUTANTS])
    owm_df = owm_df.sort_values("timestamp").rename(columns={"datetime_ph": "timestamp"})

    merged = pd.merge_asof(sensor_df, owm_df, on="timestamp", direction="backward")

    return merged[HISTORY_COLUMNS]


def calibrate_air_quality_live(
    db: Session,
    station_id: int,
    sensor_data: dict,
    owm_api_key: str = OWM_API_KEY,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    timestamp: Optional[datetime] = None,
) -> dict:
    """Pull live API data + DB sensor history, then apply rolling bias correction."""
    api_data = fetch_current_api_data(owm_api_key, lat, lon)
    history_df = build_history_df(db, station_id, owm_api_key, lat, lon, now=timestamp)
    return calibrate_air_quality(api_data, sensor_data, history_df, timestamp)


def calibrate_air_quality(
    api_data: dict,
    sensor_data: dict,
    history_df: pd.DataFrame,
    timestamp: Optional[datetime] = None,
) -> dict:
    """Return a calibrated pollutant reading using a rolling bias multiplier."""
    ts = timestamp or datetime.now(timezone.utc)

    current_row = {"timestamp": ts}
    for p in POLLUTANTS:
        current_row[f"{p}_api"] = api_data.get(p)
        current_row[f"{p}_sensor"] = sensor_data.get(SENSOR_ATTR[p])

    if history_df is None or history_df.empty:
        window_df = pd.DataFrame([current_row])
    else:
        window_df = pd.concat(
            [history_df, pd.DataFrame([current_row])], ignore_index=True
        )
    cutoff = ts - timedelta(hours=ROLLING_WINDOW_HOURS)
    window_df = window_df[window_df["timestamp"] >= cutoff].reset_index(drop=True)

    calibrated: dict = {
        "timestamp": ts.isoformat() if isinstance(ts, datetime) else ts
    }

    for p in POLLUTANTS:
        multiplier = _rolling_multiplier(window_df, p)
        api_value = api_data.get(p)
        calibrated[OUTPUT_KEY[p]] = (
            round(api_value * multiplier, 2) if api_value is not None else None
        )

    calibrated["temperature_c"] = api_data.get("temperature")
    calibrated["humidity_pct"] = api_data.get("humidity")

    return calibrated


def _rolling_multiplier(window_df: pd.DataFrame, pollutant: str) -> float:
    """Compute the forward-filled rolling mean sensor/API ratio for one pollutant."""
    api_col = pd.to_numeric(window_df[f"{pollutant}_api"], errors="coerce")
    sensor_col = pd.to_numeric(window_df[f"{pollutant}_sensor"], errors="coerce")

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = sensor_col / api_col
    ratio = ratio.where((api_col != 0) & api_col.notna() & sensor_col.notna())

    ratio_filled = ratio.ffill()
    valid_ratios = ratio_filled.dropna()

    if valid_ratios.empty:
        return 1.0

    multiplier = float(valid_ratios.mean())
    if not np.isfinite(multiplier) or multiplier <= 0:
        return 1.0

    return min(max(multiplier, MIN_MULTIPLIER), MAX_MULTIPLIER)


if __name__ == "__main__":
    from app.core.database import SessionLocal  # adjust to your actual session factory

    STATION_ID = 1
    sensor_now = {"pm25_ugm3": 27.5, "co_ugm3": None, "no2_ugm3": None}

    with SessionLocal() as db:
        result = calibrate_air_quality_live(db, STATION_ID, sensor_now)
    print(result)