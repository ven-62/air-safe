from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import math

TIMEZONE = ZoneInfo("Asia/Manila")
# BOOT_WAIT_SECONDS = 70
SAMPLE_INTERVAL_SECONDS = 5
READING_DURATION_SECONDS = 60

# Preparation starts 3 minutes before the actual 1-minute reading.
# This is enough for the MQ135 warm-up.
PREPARATION_SECONDS = 180

SAMPLING_SCHEDULE = {
    # "T5": {"sleep_minutes": 5, "hours": None, "windows": [4, 9, 14, 19, 24, 29, 34, 39, 44, 49, 54]},
    # "T7": {"sleep_minutes": 7, "hours": None, "windows": [4, 11, 18, 25, 32, 39, 46, 53]},
    # "T10": {"sleep_minutes": 10, "hours": None, "windows": [9, 24, 39, 54]},
    "S15": {"sleep_minutes": 15, "hours": [(11, 12)], "windows": [14, 34, 54]},
    "S10": {"sleep_minutes": 10, "hours": [(5, 7), (16, 18)], "windows": [9, 24, 39, 54]},
    "S25": {"sleep_minutes": 25, "hours": [(8, 10), (13, 15), (19, 21)], "windows": [24, 54]},
    "S55": {"sleep_minutes": 55, "hours": None, "windows": [54]},
}


def now_local() -> datetime:
    return datetime.now(TIMEZONE)


def get_sampling_mode(dt) -> str:
    hour = dt.hour
    if 5 <= hour <= 7 or 16 <= hour <= 18:
        return "S10"
    if 11 <= hour <= 12:
        return "S15"
    if 8 <= hour <= 10 or 13 <= hour <= 15 or 19 <= hour <= 21:
        return "S25"
    return "S55"
    # return "T7"  # For testing, use the fastest schedule.

def get_window(date, hour, slot_minute):
    reading_start = datetime(
        date.year, date.month, date.day, hour, slot_minute + 4, 0,
        tzinfo=TIMEZONE,
    )
    reading_end = reading_start + timedelta(seconds=READING_DURATION_SECONDS)
    prepare_start = reading_start - timedelta(seconds=PREPARATION_SECONDS)
    return prepare_start, reading_start, reading_end


def current_window(dt):
    mode = get_sampling_mode(dt)
    config = SAMPLING_SCHEDULE[mode]
    for slot_minute in config["windows"]:
        prepare_start, reading_start, reading_end = get_window(
            dt.date(), dt.hour, slot_minute
        )
        if prepare_start <= dt < reading_end:
            return mode, prepare_start, reading_start, reading_end
    return None, None, None, None


def is_prepare_window(dt):
    mode, prepare_start, reading_start, reading_end = current_window(dt)
    if mode is not None and prepare_start <= dt < reading_start:
        return True, mode, prepare_start, reading_start, reading_end
    return False, mode, prepare_start, reading_start, reading_end


def is_active_window(dt):
    mode = get_sampling_mode(dt)
    for slot_minute in SAMPLING_SCHEDULE[mode]["windows"]:
        _, reading_start, reading_end = get_window(dt.date(), dt.hour, slot_minute)
        if reading_start <= dt < reading_end:
            return True, mode, reading_start, reading_end
    return False, mode, None, None


def next_prepare_start(dt):
    candidates = []
    for day_offset in range(3):
        date = (dt + timedelta(days=day_offset)).date()
        for hour in range(24):
            check_dt = datetime(date.year, date.month, date.day, hour, tzinfo=TIMEZONE)
            mode = get_sampling_mode(check_dt)
            for slot_minute in SAMPLING_SCHEDULE[mode]["windows"]:
                prepare_start, _, _ = get_window(date, hour, slot_minute)
                if prepare_start > dt:
                    candidates.append(prepare_start)
    return min(candidates) if candidates else None


def prepare_response(mode, prepare_start, reading_start, reading_end):
    now = now_local()
    return {
        "status": "prepare",
        "action": "prepare",
        # "mode": mode,
        # "server_time": now.isoformat(),
        # "prepare_start": prepare_start.isoformat(),
        # "reading_start": reading_start.isoformat(),
        # "reading_end": reading_end.isoformat(),
        "prepare_seconds": max(0, math.ceil((reading_start - now).total_seconds())),
        # "reading_duration_seconds": READING_DURATION_SECONDS,
        # "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
    }


def active_response(mode, reading_start, reading_end):
    now = now_local()
    return {
        "status": "active",
        "action": "read",
        # "mode": mode,
        # "server_time": now.isoformat(),
        # "window_start": reading_start.isoformat(),
        # "window_end": reading_end.isoformat(),
        "remaining_seconds": max(0, math.ceil((reading_end - now).total_seconds())),
        # "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
    }


def sleep_response(reason="outside_window"):
    now = now_local()
    next_start = next_prepare_start(now)
    if next_start is None:
        sleep_seconds = 3600
    else:
        # Wake 70 seconds before preparation so /check occurs at preparation start.
        wake_time = next_start
        sleep_seconds = max(1, math.ceil((wake_time - now).total_seconds()))
    return {
        "status": "sleep",
        "action": "sleep",
        # "reason": reason,
        # "server_time": now.isoformat(),
        "sleep_seconds": sleep_seconds,
        # "next_prepare_start": next_start.isoformat() if next_start else None,
    }
