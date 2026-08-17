from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import math

TIMEZONE = ZoneInfo("Asia/Manila")

# ESP32 waits this long after boot before contacting the server.
BOOT_WAIT_SECONDS = 70

# ESP32 sends a sensor reading every 5 seconds.
SAMPLE_INTERVAL_SECONDS = 5


# SAMPLING MODES

# Each window is:
#
# S55:
#   xx:54:00 -> xx:58:59
#
# S25:
#   xx:24:00 -> xx:28:59
#   xx:54:00 -> xx:58:59
#
# S15:
#   xx:14:00 -> xx:18:59
#   xx:34:00 -> xx:38:59
#   xx:54:00 -> xx:58:59
#
# S10:
#   xx:09:00 -> xx:13:59
#   xx:24:00 -> xx:28:59
#   xx:39:00 -> xx:43:59
#   xx:54:00 -> xx:58:59
#
# This matches the intention of your original ESP32 code,
# but uses proper half-open 5-minute windows.


SAMPLING_SCHEDULE = {
    "S10": {
        "sleep_minutes": 10,
        "hours": [
            (5, 7),
            (16, 18),
        ],
        "windows": [9, 24, 39, 54],
    },

    "S15": {
        "sleep_minutes": 15,
        "hours": [
            (11, 12),
        ],
        "windows": [14, 34, 54],
    },

    "S25": {
        "sleep_minutes": 25,
        "hours": [
            (8, 10),
            (13, 15),
            (19, 21),
        ],
        "windows": [24, 54],
    },

    "S55": {
        "sleep_minutes": 55,
        "hours": None,
        "windows": [54],
    },
}


# TIME FUNCTIONS
def now_local() -> datetime:
    """
    Returns the current server time in Philippine time.
    """
    return datetime.now(TIMEZONE)


def get_sampling_mode(dt) -> str:
    """
    Determine which sampling mode applies to the current hour.
    """

    hour = dt.hour

    # S10
    if 5 <= hour <= 7 or 16 <= hour <= 18:
        return "S10"

    # S15
    if 11 <= hour <= 12:
        return "S15"

    # S25
    if 8 <= hour <= 10 or 13 <= hour <= 15 or 19 <= hour <= 21:
        return "S25"

    # S55
    return "S55"


def is_active_window(dt) -> tuple[bool, str, datetime | None, datetime | None]:
    """
    Determine whether the current server time is inside
    a valid 5-minute sensor reading window.

    Returns:

        active
        mode
        next_window
    """

    mode = get_sampling_mode(dt)
    config = SAMPLING_SCHEDULE[mode]

    current_minute = dt.minute
    current_second = dt.second

    for start_minute in config["windows"]:

        # Window is [start, start + 5 minutes)
        start = dt.replace(
            minute=start_minute,
            second=0,
            microsecond=0
        )

        end = start + timedelta(minutes=5)

        if start <= dt < end:
            return True, mode, start, end

    return False, mode, None, None


def next_reading_window(dt) -> datetime | None:
    """
    Find the next reading window.

    Returns the exact datetime at which the next window starts.
    """

    candidates = []

    # Check today and tomorrow.
    for day_offset in range(0, 2):

        date = (dt + timedelta(days=day_offset)).date()

        # Use noon as the base datetime for getting the schedule.
        base = datetime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=12,
            minute=0,
            second=0,
            tzinfo=TIMEZONE
        )

        # Determine schedules for every hour of the day.
        for hour in range(24):

            check_dt = base.replace(hour=hour)

            mode = get_sampling_mode(check_dt)
            config = SAMPLING_SCHEDULE[mode]

            for minute in config["windows"]:

                candidate = check_dt.replace(
                    minute=minute,
                    second=0,
                    microsecond=0
                )

                if candidate > dt:
                    candidates.append(candidate)

    if not candidates:
        return None

    return min(candidates)


def seconds_until_next_window(dt) -> int:
    """
    Number of seconds until the next reading window.
    """

    next_window = next_reading_window(dt)

    if next_window is None:
        return 60

    seconds = (next_window - dt).total_seconds()

    return max(1, math.ceil(seconds))


# SERVER RESPONSE HELPERS
def active_response(mode, window_start, window_end) -> dict:
    """
    Response sent when the ESP32 is allowed to operate.
    """

    now = now_local()

    remaining = max(
        0,
        math.ceil((window_end - now).total_seconds())
    )

    return {
        "status": "active",
        "action": "read",
        "mode": mode,
        "server_time": now.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "remaining_seconds": remaining,
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS
    }


def sleep_response(reason="outside_window") -> dict:
    """
    Response telling the ESP32 to deep sleep.
    """

    now = now_local()

    sleep_until = next_reading_window(now)

    if sleep_until is None:
        sleep_seconds = 3600
    else:
        # IMPORTANT:
        #
        # ESP32 will spend 70 seconds booting before contacting
        # the server again.
        #
        # Therefore we subtract BOOT_WAIT_SECONDS here.
        #
        # Example:
        #
        # next window = 10:24:00
        # current     = 10:10:00
        #
        # time = 14 min
        #
        # ESP sleeps:
        # 14 min - 70 sec
        #
        # Then:
        # wake -> wait 70 sec -> contact server at ~10:24
        #
        sleep_seconds = math.ceil(
            (sleep_until - now).total_seconds()
        )

        sleep_seconds = max(
            1,
            sleep_seconds - BOOT_WAIT_SECONDS
        )

    return {
        "status": "sleep",
        "action": "sleep",
        "reason": reason,
        "server_time": now.isoformat(),
        "sleep_seconds": sleep_seconds,
        "sleep_until": sleep_until.isoformat()
        if sleep_until else None
    }
