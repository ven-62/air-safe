from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.managers.station_manager import station_manager
from app.services.station_service import (
    now_local,
    current_window,
    is_active_window,
    prepare_response,
    active_response,
    sleep_response,
)

router = APIRouter()


@router.post("/{station_id}/check")
def station_check(station_id: str):
    now = now_local()
    print(f"[CHECK] Station {station_id} at {now.isoformat()}")

    # Final one-minute measurement window.
    active, mode, reading_start, reading_end = is_active_window(now)
    if active:
        print(
            f"[CHECK] Station {station_id}: READ ({mode}) "
            f"{reading_start} -> {reading_end}"
        )
        return active_response(mode, reading_start, reading_end)

    # Three-minute preparation period before the final minute.
    mode, prepare_start, reading_start, reading_end = current_window(now)
    if mode is not None and prepare_start <= now < reading_start:
        print(
            f"[CHECK] Station {station_id}: PREPARE ({mode}) "
            f"reading starts at {reading_start}"
        )
        return prepare_response(mode, prepare_start, reading_start, reading_end)

    print(f"[CHECK] Station {station_id}: SLEEP")
    return sleep_response("outside_window")


@router.post("/{station_id}/readings")
async def receive_reading(
    station_id: str,
    data: dict = Body(...),
    db: Session = Depends(get_db),
):
    now = now_local()

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    required_fields = [
        "pm2_5", "mq7_ugm3", "mq135_ugm3", "humidity", "temperature"
    ]
    missing = [field for field in required_fields if field not in data]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing fields: {', '.join(missing)}",
        )

    print("=" * 60)
    print(f"Station       : {station_id}")
    print(f"Server Time   : {now}")
    print("AVERAGED      : True")
    print(f"Sample Count  : {data.get('sample_count', 0)}")
    print(f"PM2.5         : {data.get('pm2_5')}")
    print(f"CO (MQ7)      : {data.get('co_ugm3')}")
    print(f"NO2 (MQ135)   : {data.get('no2_ugm3')}")
    print(f"Humidity      : {data.get('humidity')}")
    print(f"Temperature   : {data.get('temperature')}")
    print("=" * 60)

    await station_manager.process_station_data(
        station_id,
        data,
        db,
        is_last=True,
    )

    # The reading has finished. Tell the ESP32 exactly how long
    # to sleep until the NEXT preparation phase.
    next_sleep = sleep_response("reading_complete")
    print(f"[READINGS] Station {station_id}: SLEEP for {next_sleep['sleep_seconds']} seconds")
    return {
        "status": "success",
        "action": "sleep",
        "message": "Averaged reading stored",
        "sleep_seconds": next_sleep["sleep_seconds"],
        "next_prepare_start": next_sleep["next_prepare_start"],
    }
