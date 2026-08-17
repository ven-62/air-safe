"""
calibrate_sensors.py

Build frozen quantile-mapping calibration files for each station.

Purpose:
    Align the statistical distribution of physical sensor measurements
    with the distribution of the API-derived training data.

Calibration flow:

    Sensor distribution
           |
           | percentile
           v
    Training distribution
           |
           v
    Aligned sensor value

The resulting JSON files are used during deployment by
quantile_normalizer.py.

IMPORTANT:
    This script should be run using the calibration period only.
    Do NOT include future deployment/evaluation data when generating
    the calibration mappings.
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd


# CONFIGURATION

INPUT_CSV = "calibration_data.csv"

OUTPUT_DIR = Path("calibration")

# Use finer quantiles
# 5% intervals are a good practical choice.
PERCENTILES = np.arange(0, 101, 5, dtype=float)

# Minimum observations required to build a calibration mapping.
# 30 days of hourly data ≈ 720 observations.
MIN_CALIBRATION_SAMPLES = 300


# COLUMN DEFINITIONS

# Physical sensor columns
SENSOR_COLUMNS = {
    "pm2_5_ugm3": "pm2_5_sensor",
    "co_ugm3": "co_sensor",
    "no2_ugm3": "no2_sensor",
    "temperature_c": "temperature_sensor",
    "humidity_pct": "humidity_sensor",
}

# API / training-domain columns
API_COLUMNS = {
    "pm2_5_ugm3": "pm2_5_api",
    "co_ugm3": "co_api",
    "no2_ugm3": "no2_api",
    "temperature_c": "temperature_api",
    "humidity_pct": "humidity_api",
}


# VALIDATION

def validate_columns(df: pd.DataFrame):
    required = ["timestamp", "station_id"]

    required.extend(SENSOR_COLUMNS.values())
    required.extend(API_COLUMNS.values())

    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(
            "Missing required columns:\n"
            + "\n".join(f"  - {col}" for col in missing)
        )


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean obviously invalid sensor/API observations.

    This does NOT perform calibration.
    It only removes invalid rows.
    """

    df = df.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    # Remove invalid timestamps
    df = df.dropna(subset=["timestamp"])

    # Remove duplicate timestamp/station combinations
    df = (
        df.sort_values(["station_id", "timestamp"])
          .drop_duplicates(
              subset=["station_id", "timestamp"],
              keep="last"
          )
    )

    # Convert numeric columns
    numeric_columns = (
        list(SENSOR_COLUMNS.values())
        + list(API_COLUMNS.values())
    )

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # Remove rows with missing required values
    df = df.dropna(
        subset=numeric_columns
    )

    # Basic physical validity checks

    # Pollutants cannot be negative
    for column in [
        "pm2_5_sensor",
        "co_sensor",
        "no2_sensor",
        "pm2_5_api",
        "co_api",
        "no2_api",
    ]:
        df = df[df[column] >= 0]

    # Humidity must be 0-100%
    for column in [
        "humidity_sensor",
        "humidity_api",
    ]:
        df = df[
            (df[column] >= 0)
            & (df[column] <= 100)
        ]

    # Reasonable temperature range.
    # Adjust if your study requires a different range.
    for column in [
        "temperature_sensor",
        "temperature_api",
    ]:
        df = df[
            (df[column] >= -20)
            & (df[column] <= 60)
        ]

    return df.reset_index(drop=True)


# QUANTILE TABLE

def calculate_quantiles(values):
    """
    Calculate the selected empirical quantiles.

    Returns:
        {
            "percentiles": [...],
            "values": [...]
        }
    """

    values = np.asarray(values, dtype=float)

    values = values[
        np.isfinite(values)
    ]

    if len(values) == 0:
        raise ValueError(
            "Cannot calculate quantiles from empty data."
        )

    quantile_values = np.percentile(
        values,
        PERCENTILES
    )

    return {
        "percentiles": PERCENTILES.tolist(),
        "values": quantile_values.tolist(),
    }


# BUILD ONE STATION'S CALIBRATION

def build_station_calibration(
    station_df: pd.DataFrame,
    station_id: str
):
    """
    Build a frozen quantile mapping for one station.

    For every feature:

        sensor value
             ↓
        sensor percentile
             ↓
        training/API percentile
             ↓
        aligned value
    """

    calibration = {
        "_metadata": {
            "station_id": str(station_id),
            "method": "empirical_quantile_mapping",
            "percentile_step": 5,
            "source": "30-day sensor/API collocation",
            "frozen": True,
            "sample_count": int(len(station_df)),
        }
    }

    for feature, sensor_column in SENSOR_COLUMNS.items():

        api_column = API_COLUMNS[feature]

        sensor_values = station_df[
            sensor_column
        ].to_numpy(dtype=float)

        api_values = station_df[
            api_column
        ].to_numpy(dtype=float)

        # Sensor distribution

        sensor_quantiles = calculate_quantiles(
            sensor_values
        )

        # Training/API distribution

        api_quantiles = calculate_quantiles(
            api_values
        )

        calibration[feature] = {
            "percentiles": sensor_quantiles["percentiles"],

            # CDF of the sensor
            "sensor_values": sensor_quantiles["values"],

            # Target/training-domain CDF
            "training_values": api_quantiles["values"],
        }

    return calibration


# MAIN

def main():

    print("=" * 60)
    print("SENSOR QUANTILE CALIBRATION")
    print("=" * 60)

    # Load

    print(f"\nLoading: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)

    validate_columns(df)

    print(f"Raw rows: {len(df):,}")

    # Clean

    df = clean_data(df)

    print(f"Clean rows: {len(df):,}")

    # Prepare output directory

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Process every station independently

    stations = sorted(
        df["station_id"]
        .dropna()
        .astype(str)
        .unique()
    )

    print(f"\nStations found: {stations}")

    for station_id in stations:

        station_df = (
            df[
                df["station_id"].astype(str)
                == station_id
            ]
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        print("\n" + "-" * 60)
        print(f"Station: {station_id}")
        print(f"Observations: {len(station_df):,}")

        if len(station_df) < MIN_CALIBRATION_SAMPLES:
            raise ValueError(
                f"{station_id} only has "
                f"{len(station_df)} observations. "
                f"At least {MIN_CALIBRATION_SAMPLES} "
                f"are required."
            )

        # Build mapping
        calibration = build_station_calibration(
            station_df,
            station_id
        )

        # Save
        output_file = (
            OUTPUT_DIR
            / f"{station_id}_quantile_mapping.json"
        )

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                calibration,
                f,
                indent=2
            )

        print(
            f"Saved calibration: {output_file}"
        )

        # Print summary
        for feature in SENSOR_COLUMNS:

            sensor_q = calibration[
                feature
            ]["sensor_values"]

            train_q = calibration[
                feature
            ]["training_values"]

            print(
                f"\n{feature}"
            )

            print(
                f"  Sensor range: "
                f"{sensor_q[0]:.4f} → "
                f"{sensor_q[-1]:.4f}"
            )

            print(
                f"  Training range: "
                f"{train_q[0]:.4f} → "
                f"{train_q[-1]:.4f}"
            )

    print("\n" + "=" * 60)
    print("CALIBRATION COMPLETE")
    print("=" * 60)

    print(
        "\nCalibration files are now frozen."
    )

    print(
        "Do NOT update them using future deployment/evaluation data."
    )


if __name__ == "__main__":
    main()