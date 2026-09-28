"""
Inference pipeline for the Air Quality Random Forest models.

Architecture:

    ESP32
       ↓
    FastAPI
       ↓
    Unit conversion
       ↓
    SensorReading saved to database
       ↓
    AirQualityPredictor.add_db_reading()
       ↓
    Fixed quantile mapping
       ↓
    In-memory _history
       ↓
    Lag / rolling features
       ↓
    Random Forest
       ↓
    AQI + 1/2/3-hour forecast


IMPORTANT:

- SensorReading in the database contains values already converted
  to the model's physical units:
      PM2.5  → µg/m³
      CO     → µg/m³
      NO2    → µg/m³
      Temp   → °C
      RH     → %

- The predictor applies the FIXED quantile calibration to those
  values before putting them into _history.

- The database is the permanent history.
- _history is only a temporary in-memory feature buffer.
- After a server restart, _history is rebuilt from the database.

- Each station must have its own AirQualityPredictor instance and
  its own quantile calibration JSON.
"""

import json
import os
from collections import deque

import joblib
import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download

from app.calibration.calibrate_readings import calibrate_air_quality_live
# COLUMN ALIASES

_COLUMN_ALIASES = {
    "pm25": "pm2_5_ugm3",
    "pm2_5": "pm2_5_ugm3",
    "pm2.5": "pm2_5_ugm3",
    "pm25_ugm3": "pm2_5_ugm3",
    "pm2_5_ugm3": "pm2_5_ugm3",
    "co": "co_ugm3",
    "co_ugm3": "co_ugm3",
    "no2": "no2_ugm3",
    "no2_ugm3": "no2_ugm3",
    "temperature": "temperature_c",
    "temp": "temperature_c",
    "temperature_c": "temperature_c",
    "humidity": "humidity_pct",
    "humidity_pct": "humidity_pct",
}


_TIMESTAMP_KEYS = (
    "timestamp",
    "datetime",
    "datetime_ph",
    "time",
)


_REQUIRED_SENSOR_COLS = [
    "pm2_5_ugm3",
    "co_ugm3",
    "no2_ugm3",
    "temperature_c",
    "humidity_pct",
]


class AirQualityPredictor:
    """
    Loads the trained Random Forest models and performs inference.

    Each station should have its own instance:

        predictor_st01
        predictor_st02

    Each instance has:

        - its own _history
        - its own quantile calibration
        - the same pre-trained RF models
    """

    def __init__(
        self,
        model_dir="app/core/saved_models",
        config_path=None,
        history_size=24,
        hf_repo_id=None,
        hf_revision=None,
        hf_token=None,
    ):

        # Model configuration
        self.model_dir = model_dir
        self.hf_repo_id = hf_repo_id
        self.hf_revision = hf_revision
        self.hf_token = hf_token

        config_path = config_path or self._resolve_file("model_config.json")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.features_a = self.config["ALL_FEATURES_A"]
        self.features_b = self.config["ALL_FEATURES_B"]
        self.forecast_features = self.config["FORECAST_FEATURES"]
        self.horizons = self.config["HORIZONS"]
        self.aqi_bins = self.config["aqi_bins"]
        self.aqi_labels = self.config["aqi_labels"]

        # Load models
        self.reg = self._load_model("rf_aqi_regressor_naga.joblib")

        self.forecast_models = {
            h: self._load_model(f"rf_forecast_h{h}_naga.joblib") for h in self.horizons
        }

        # Temporary in-memory history
        self.history_size = history_size
        self._history = deque(maxlen=history_size)

        # Fixed quantile calibration
        # Fixed quantile calibration is optional.
        #
        # If a calibration file exists, sensor values are mapped into the
        # training/API domain before prediction.
        #
        # If no calibration file is supplied, the predictor uses the raw
        # physical sensor values directly. This allows the station to make
        # predictions before calibration has been generated.

    # MODEL HELPERS
    def _resolve_file(self, filename):
        """
        Resolve a model/config file either locally
        or from Hugging Face.
        """

        if self.hf_repo_id:

            return hf_hub_download(
                repo_id=self.hf_repo_id,
                filename=filename,
                revision=self.hf_revision,
                token=self.hf_token,
            )

        path = os.path.join(self.model_dir, filename)

        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found at {path}")

        return path

    def _load_model(self, filename):
        return joblib.load(self._resolve_file(filename))

    # INPUT NORMALIZATION / VALIDATION

    def _normalize_reading(self, reading):
        """
        Convert a dictionary into the canonical model format.

        IMPORTANT:
        Values passed here are ALREADY converted into model units.

        Example:

            pm2_5_ugm3 → µg/m³
            co_ugm3    → µg/m³
            no2_ugm3   → µg/m³
            temperature_c → °C
            humidity_pct → %
        """

        out = {}

        for key, value in reading.items():

            key_lower = key.lower()

            # ----------------------------------------------
            # Timestamp
            # ----------------------------------------------

            if key_lower in _TIMESTAMP_KEYS:

                out["datetime_ph"] = pd.to_datetime(value)

            # ----------------------------------------------
            # Sensor/model fields
            # ----------------------------------------------

            elif key_lower in _COLUMN_ALIASES:

                numeric_value = float(value)

                if not np.isfinite(numeric_value):
                    raise ValueError(f"Invalid value for {key}: " f"{value}")

                canonical_name = _COLUMN_ALIASES[key_lower]

                out[canonical_name] = numeric_value

        # Check timestamp

        if "datetime_ph" not in out:

            raise ValueError("Reading must contain a timestamp.")

        # Check required fields

        missing = [col for col in _REQUIRED_SENSOR_COLS if col not in out]

        if missing:

            raise ValueError(f"Reading is missing: {missing}")

        # Physical validation

        if out["pm2_5_ugm3"] < 0:

            raise ValueError("PM2.5 cannot be negative.")

        if out["co_ugm3"] < 0:

            raise ValueError("CO cannot be negative.")

        if out["no2_ugm3"] < 0:

            raise ValueError("NO2 cannot be negative.")

        if not (0 <= out["humidity_pct"] <= 100):

            raise ValueError("Humidity must be between 0 and 100%.")

        if not (-20 <= out["temperature_c"] <= 60):

            raise ValueError("Temperature is outside the expected range.")

        return out

    # DATABASE → PREDICTOR

    def _db_reading_to_dict(self, db_reading):
        """
        Convert a SQLAlchemy SensorReading object into
        the dictionary format used by the predictor.

        Your SQLAlchemy model contains:

            pm25_ugm3
            co_ugm3
            no2_ugm3
            temperature_c
            humidity_pct
            timestamp
        """

        return {
            "pm25_ugm3": db_reading.pm25_ugm3,
            "co_ugm3": db_reading.co_ugm3,
            "no2_ugm3": db_reading.no2_ugm3,
            "temperature_c": db_reading.temperature_c,
            "humidity_pct": db_reading.humidity_pct,
            "timestamp": db_reading.timestamp,
        }

    def add_db_reading(self, db_reading, db, station_id=None):
        """
        Add an already-saved SQLAlchemy SensorReading
        into the predictor.

        FLOW:

            Database SensorReading
                    ↓
            normalize/validate
                    ↓
            optional quantile calibration
                    ↓
            _history

        If no calibration is configured, the normalized raw values are
        placed directly into _history.

        This method DOES NOT write to the database.

        The route/service should save the SensorReading
        first, then call this method.
        """

        reading = self._db_reading_to_dict(db_reading)

        return self.add_reading(reading, db, station_id=station_id)

    def add_reading(self, reading, db, station_id):
        normalized = self._normalize_reading(reading)  # allow None sensor values
        ts = normalized["datetime_ph"]

        sensor_data = {
            "pm25_ugm3": normalized.get("pm2_5_ugm3"),
            "co_ugm3": normalized.get("co_ugm3"),
            "no2_ugm3": normalized.get("no2_ugm3"),
        }
        cal = calibrate_air_quality_live(db, station_id, sensor_data, timestamp=ts)

        aligned = {
            "pm2_5_ugm3": cal["pm25_ugm3"],
            "co_ugm3": cal["co_ugm3"],
            "no2_ugm3": cal["no2_ugm3"],
            "temperature_c": cal["temperature_c"],
            "humidity_pct": cal["humidity_pct"],
            "datetime_ph": ts,
        }
        self._history.append(aligned)
        return aligned

    def add_calibrated_reading(self, db_reading):
        """Load an already-calibrated CalibratedReading into history.

        This is used when rebuilding predictor history from the database.
        It intentionally does NOT apply the quantile normalizer again.
        """
        reading = {
            "pm25_ugm3": db_reading.pm25_ugm3,
            "co_ugm3": db_reading.co_ugm3,
            "no2_ugm3": db_reading.no2_ugm3,
            "temperature_c": db_reading.temperature_c,
            "humidity_pct": db_reading.humidity_pct,
            "timestamp": db_reading.timestamp,
        }

        normalized = self._normalize_reading(reading)
        self._history.append(normalized)
        return normalized

    def predict_raw(self, reading, update_history=True):
        """
        Predict AQI and optionally forecast directly from raw sensor data.

        This is useful when the station has no calibration file yet.

        The supplied values are assumed to already be in the predictor's
        physical units (µg/m³, °C, %).

        If update_history=True, the reading is added to _history before
        prediction. Forecasting therefore uses the new raw reading and
        whatever previous history is available.
        """

        if update_history:
            self.add_reading(reading)

        elif len(self._history) == 0:
            raise ValueError(
                "Cannot predict_raw(update_history=False): "
                "predictor history is empty."
            )

        aqi = self.predict_aqi()
        forecast = self.predict_forecast()

        return {
            "aqi": aqi,
            "forecast": forecast,
        }

    # RESTORE HISTORY AFTER SERVER RESTART

    def restore_history(self, db_readings):
        """
        Rebuild _history from SensorReading records
        retrieved from the database.

        db_readings MUST be ordered:

            oldest → newest

        Example:

            [
                reading_01,
                reading_02,
                ...
                reading_24
            ]

        This method does NOT modify the database.
        """

        self._history.clear()

        for db_reading in db_readings:

            self.add_db_reading(db_reading)

    # FEATURE ENGINEERING

    @staticmethod
    def _time_features(dt):

        hour = dt.hour
        dow = dt.dayofweek
        month = dt.month

        return {
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "dow_sin": np.sin(2 * np.pi * dow / 7),
            "dow_cos": np.cos(2 * np.pi * dow / 7),
            "month_sin": np.sin(2 * np.pi * month / 12),
            "month_cos": np.cos(2 * np.pi * month / 12),
        }

    def _build_feature_row(self):
        """
        Build the current feature row using the
        calibrated readings stored in _history.
        """

        if len(self._history) == 0:

            raise ValueError(
                "No readings available. " "Restore history from the database first."
            )

        hist_df = (
            pd.DataFrame(list(self._history))
            .sort_values("datetime_ph")
            .reset_index(drop=True)
        )

        latest = hist_df.iloc[-1]

        # Current values

        row = {col: latest[col] for col in self.forecast_features}

        # Time features

        row.update(self._time_features(latest["datetime_ph"]))

        # Lag features

        for col in self.forecast_features:

            series = hist_df[col]

            for lag in (1, 2, 3):

                if len(series) > lag:

                    row[f"{col}_lag{lag}"] = series.iloc[-1 - lag]

                else:

                    # Same fallback behavior as
                    # your original predictor.
                    row[f"{col}_lag{lag}"] = series.iloc[0]

        # Rolling features

        for col in self.forecast_features:

            series = hist_df[col]

            roll3 = series.tail(3)
            roll6 = series.tail(6)

            row[f"{col}_roll3_mean"] = roll3.mean()

            row[f"{col}_roll3_std"] = roll3.std() if len(roll3) > 1 else 0.0

            row[f"{col}_roll6_mean"] = roll6.mean()

        return latest, row

    # AQI PREDICTION

    def _predict_aqi_from_values(
        self,
        pm2_5_ugm3,
        co_ugm3,
        no2_ugm3,
        temperature_c,
        dt,
    ):
        """
        Run the AQI Random Forest using calibrated
        pollutant values.
        """

        row = {
            "pm2_5_ugm3": pm2_5_ugm3,
            "co_ugm3": co_ugm3,
            "no2_ugm3": no2_ugm3,
            "temperature_c": temperature_c,
            **self._time_features(dt),
        }

        X = pd.DataFrame([row])[self.features_a]

        aqi_pred = float(
            np.clip(
                self.reg.predict(X)[0],
                0,
                500,
            )
        )

        category = pd.cut(
            [aqi_pred],
            bins=self.aqi_bins,
            labels=self.aqi_labels,
        )[0]

        return {
            "aqi": round(aqi_pred, 2),
            "category": str(category),
        }

    def predict_aqi(self):
        """
        Predict current AQI from the latest
        calibrated database reading in history.
        """

        latest, _ = self._build_feature_row()

        result = self._predict_aqi_from_values(
            latest["pm2_5_ugm3"],
            latest["co_ugm3"],
            latest["no2_ugm3"],
            latest["temperature_c"],
            latest["timestamp"],
        )

        return result

    # FORECASTING

    def predict_horizon(self, h: int):
        """
        Predict one forecast horizon.

        The forecasting model predicts DELTA.

            future = current + predicted_delta
        """

        if h not in self.forecast_models:

            raise ValueError(
                f"No model for horizon {h}. " f"Available horizons: " f"{self.horizons}"
            )

        latest, row = self._build_feature_row()

        X = pd.DataFrame([row])[self.features_b]

        current_vals = np.array(
            [latest[c] for c in self.forecast_features],
            dtype=float,
        )

        # Predict delta

        delta_pred = self.forecast_models[h].predict(X)[0]

        # Convert delta → absolute forecast

        abs_pred = current_vals + delta_pred

        # Prevent physically impossible negative
        # pollutant forecasts.

        forecasted = dict(
            zip(
                self.forecast_features,
                abs_pred,
            )
        )

        for col in (
            "pm2_5_ugm3",
            "co_ugm3",
            "no2_ugm3",
        ):

            forecasted[col] = max(0.0, float(forecasted[col]))

        # Humidity
        if "humidity_pct" in forecasted:

            forecasted["humidity_pct"] = np.clip(
                forecasted["humidity_pct"],
                0,
                100,
            )

        # Future timestamp

        future_dt = latest["datetime_ph"] + pd.Timedelta(hours=h)

        # AQI from forecasted pollutants

        aqi_result = self._predict_aqi_from_values(
            forecasted["pm2_5_ugm3"],
            forecasted["co_ugm3"],
            forecasted["no2_ugm3"],
            forecasted["temperature_c"],
            future_dt,
        )

        return {
            "timestamp": str(future_dt),
            "horizon": f"t+{h}h",
            **{
                col: round(
                    float(value),
                    3,
                )
                for col, value in forecasted.items()
            },
            **aqi_result,
        }

    def predict_h1(self):
        return self.predict_horizon(1)

    def predict_h2(self):
        return self.predict_horizon(2)

    def predict_h3(self):
        return self.predict_horizon(3)

    def predict_forecast(self):
        """
        Return all available forecast horizons.
        """

        forecasts = {}

        for h in self.horizons:

            result = self.predict_horizon(h)

            result.pop(
                "horizon",
                None,
            )

            forecasts[f"+h{h}"] = result

        return forecasts

