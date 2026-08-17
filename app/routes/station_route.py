from fastapi import APIRouter, Header, HTTPException, Depends, Body

from sqlalchemy.orm import Session


from app.core.database import get_db

from app.managers.station_manager import station_manager

from app.services.station_service import (
    now_local,
    is_active_window,
    active_response,
    sleep_response,
    SAMPLE_INTERVAL_SECONDS,
)

router = APIRouter()


# Station Boot / Check in
@router.post("/{station_id}/check")
def station_check(station_id: str):
    """
    Called by ESP32 after boot.

    Server determines whether the station should:

        1. Start reading
        2. Go to deep sleep
    """

    now = now_local()

    print(f"[CHECK] Station {station_id} at {now.isoformat()}")

    # CHECK ACTIVE WINDOW
    active, mode, window_start, window_end = is_active_window(now)

    # OUTSIDE WINDOW
    if not active:

        print(
            f"[CHECK] Station {station_id}: "
            f"OUTSIDE WINDOW"
        )

        return sleep_response(
            reason="outside_window"
        )

    # ACTIVE
    print(
        f"[CHECK] Station {station_id}: "
        f"ACTIVE ({mode})"
    )

    return active_response(
        mode=mode,
        window_start=window_start,
        window_end=window_end,
    )

# SENSOR 
@router.post("/{station_id}/readings")
async def receive_reading(
    station_id: str,
    data: dict = Body(...),
    db: Session = Depends(get_db),
):
    """
    Receive sensor data.

    The server checks the active window before saving.

    The final reading of the window is marked as `is_last=True`.

    Only when `is_last=True` will the station manager round
    the timestamp to the next hour.

    Example:

        08:58:50 -> normal timestamp
        08:58:55 -> last reading -> 09:00:00
    """

    now = now_local()

    # CHECK ACTIVE WINDOW
    active, mode, window_start, window_end = is_active_window(now)

    # WINDOW ENDED
    if not active:

        print(
            f"[READING] Station {station_id}: "
            f"WINDOW ENDED"
        )

        return sleep_response(
            reason="window_ended"
        )

    # VALIDATE DATA
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON body"
        )

    # DETERMINE LAST READING
    remaining_seconds = (window_end - now).total_seconds()

    # The reading is considered the final reading when
    # there is no more than one sampling interval remaining.
    #
    # Example with SAMPLE_INTERVAL_SECONDS = 5:
    #
    # 08:58:50 -> 10 sec remaining -> False
    # 08:58:55 ->  5 sec remaining -> True
    # 08:58:58 ->  2 sec remaining -> True
    #
    # 08:59:00 -> window already inactive and was rejected above.

    is_last = (
        remaining_seconds <= SAMPLE_INTERVAL_SECONDS
    )

    # EXTRACT SENSOR DATA
    pm2_5 = data.get("pm2_5")
    mq7_ppm = data.get("mq7_ppm")
    mq135_ppm = data.get("mq135_ppm")
    humidity = data.get("humidity")
    temperature = data.get("temperature")

    # LOG
    print("=" * 60)
    print(f"Station       : {station_id}")
    print(f"Server Time   : {now}")
    print(f"Mode          : {mode}")
    print(f"Window Start  : {window_start}")
    print(f"Window End    : {window_end}")
    print(f"Remaining     : {remaining_seconds:.3f}s")
    print(f"Is Last       : {is_last}")
    print(f"PM2.5         : {pm2_5}")
    print(f"CO (MQ7)      : {mq7_ppm}")
    print(f"NO2 (MQ135)   : {mq135_ppm}")
    print(f"Humidity      : {humidity}")
    print(f"Temperature   : {temperature}")
    print("=" * 60)

    # PROCESS / SAVE

    await station_manager.process_station_data(
        station_id,
        data,
        db,
        is_last=is_last,
    )

    # CHECK WINDOW AGAIN
    now_after = now_local()

    (
        still_active,
        current_mode,
        current_window_start,
        current_window_end,
    ) = is_active_window(now_after)

    # WINDOW ENDED WHILE PROCESSING
    if not still_active:

        print(
            f"[READING] Station {station_id}: "
            f"WINDOW ENDED AFTER PROCESSING"
        )

        return sleep_response(
            reason="window_ended"
        )

    # CONTINUE
    remaining = max(
        0,
        int(
            (
                current_window_end - now_after
            ).total_seconds()
        )
    )

    return {
        "status": "active",
        "action": "continue",
        "mode": current_mode,
        "server_time": now_after.isoformat(),
        "remaining_seconds": remaining,
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
    }

