"""
Rolling Bias Correction for Air Quality Monitoring.

Live sources:
    - OpenWeatherMap Air Pollution API -> pm25_ugm3, co_ugm3, no2_ugm3
    - Open-Meteo Forecast API          -> temperature_c, humidity_pct

Uniform feature names used everywhere (DB, inputs, history, output):
    pm25_ugm3, co_ugm3, no2_ugm3, temperature_c, humidity_pct, timestamp

Expected `history_df` schema (rows spanning the trailing 6-hour window, any cadence):
    timestamp, pm25_ugm3_api, pm25_ugm3_sensor, co_ugm3_api, co_ugm3_sensor,
    no2_ugm3_api, no2_ugm3_sensor

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

POLLUTANTS = ("pm25_ugm3", "co_ugm3", "no2_ugm3")
OWM_COMPONENT = {"pm25_ugm3": "pm2_5", "co_ugm3": "co", "no2_ugm3": "no2"}

ROLLING_WINDOW_HOURS = 6
MIN_MULTIPLIER = 0.3
MAX_MULTIPLIER = 3.0

OWM_AIR_POLLUTION_URL = "https://api.openweathermap.org/data/2.5/air_pollution"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Naga City, Bicol Region, PH — default deployment coordinates.
DEFAULT_LAT = 13.62326
DEFAULT_LON = 123.18493

REQUEST_TIMEOUT_SECONDS = 10

HISTORY_COLUMNS = ["timestamp"] + [
    f"{p}_{source}" for p in POLLUTANTS for source in ("api", "sensor")
]


def _to_utc(ts: datetime) -> pd.Timestamp:
    """Normalize any datetime (naive treated as UTC) to a tz-aware UTC Timestamp."""
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


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
        "temperature_c": current.get("temperature_2m"),
        "humidity_pct": current.get("relative_humidity_2m"),
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
    """Fetch all readings for ONE station since a cutoff, oldest first."""
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
    """Build the rolling-correction history DataFrame for one station.

    Sensor readings arrive every ~15 min (with second-level jitter); OWM pollutant
    data is hourly. Each sensor reading is paired with the most recent OWM value at
    or before its timestamp (forward-filled) via pd.merge_asof.
    """
    now = _to_utc(now or datetime.now(timezone.utc))
    cutoff = now - timedelta(hours=window_hours)

    sensor_rows = fetch_sensor_history(db, station_id, since=cutoff.to_pydatetime())
    if not sensor_rows:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    sensor_df = pd.DataFrame(
        [
            {
                "timestamp": row.timestamp,
                **{f"{p}_sensor": getattr(row, p) for p in POLLUTANTS},
            }
            for row in sensor_rows
        ]
    )
    sensor_df["timestamp"] = pd.to_datetime(sensor_df["timestamp"], utc=True)
    sensor_df = sensor_df.sort_values("timestamp")

    # Pad the OWM fetch start by 1h so the earliest sensor reading has a prior
    # hourly value to forward-fill from.
    owm_history = fetch_owm_air_pollution_history(
        (sensor_df["timestamp"].iloc[0] - timedelta(hours=1)).to_pydatetime(),
        now.to_pydatetime(),
        owm_api_key,
        lat,
        lon,
    )
    owm_df = pd.DataFrame(
        owm_history, columns=["timestamp", *POLLUTANTS]
    ).rename(columns={p: f"{p}_api" for p in POLLUTANTS})
    owm_df["timestamp"] = pd.to_datetime(owm_df["timestamp"], utc=True)
    owm_df = owm_df.sort_values("timestamp")

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
    """Return a calibrated reading using a per-pollutant rolling bias multiplier."""
    ts = _to_utc(timestamp or datetime.now(timezone.utc))

    current_row = {"timestamp": ts}
    for p in POLLUTANTS:
        current_row[f"{p}_api"] = api_data.get(p)
        current_row[f"{p}_sensor"] = sensor_data.get(p)

    current_df = pd.DataFrame([current_row])
    if history_df is None or history_df.empty:
        window_df = current_df
    else:
        window_df = pd.concat([history_df, current_df], ignore_index=True)

    window_df["timestamp"] = pd.to_datetime(window_df["timestamp"], utc=True)
    cutoff = ts - timedelta(hours=ROLLING_WINDOW_HOURS)
    window_df = window_df[window_df["timestamp"] >= cutoff].reset_index(drop=True)

    calibrated: dict = {"timestamp": ts.isoformat()}

    for p in POLLUTANTS:
        multiplier = _rolling_multiplier(window_df, p)
        api_value = api_data.get(p)
        calibrated[p] = (
            round(api_value * multiplier, 2) if api_value is not None else None
        )

    calibrated["temperature_c"] = api_data.get("temperature_c")
    calibrated["humidity_pct"] = api_data.get("humidity_pct")

    return calibrated


def _rolling_multiplier(window_df: pd.DataFrame, pollutant: str) -> float:
    """Compute the forward-filled rolling mean sensor/API ratio for one pollutant."""
    api_col = pd.to_numeric(window_df[f"{pollutant}_api"], errors="coerce")
    sensor_col = pd.to_numeric(window_df[f"{pollutant}_sensor"], errors="coerce")

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = sensor_col / api_col
    ratio = ratio.where((api_col != 0) & api_col.notna() & sensor_col.notna())

    valid_ratios = ratio.ffill().dropna()
    if valid_ratios.empty:
        return 1.0

    multiplier = float(valid_ratios.mean())
    if not np.isfinite(multiplier) or multiplier <= 0:
        return 1.0

    return min(max(multiplier, MIN_MULTIPLIER), MAX_MULTIPLIER)


if __name__ == "__main__":
    from app.core.database import SessionLocal  # adjust to your actual session factory

    STATION_ID = 1
    sensor_now = {"pm25_ugm3": 10.75, "co_ugm3": None, "no2_ugm3": 0.77}

    with SessionLocal() as db:
        result = calibrate_air_quality_live(db, STATION_ID, sensor_now)
    print(result)