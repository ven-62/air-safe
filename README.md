AIR-SAFE: Air Quality Monitoring System

- ESP32 sends sensor data via HTTP
- FastAPI backend stores data

Run backend:
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
