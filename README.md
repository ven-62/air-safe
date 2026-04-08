ESP32 Air Quality Monitoring System

- ESP32 sends sensor data via HTTP
- FastAPI backend stores data
- React frontend displays real-time dashboard

Run backend:
uvicorn app.main:app --reload

Run frontend:
npm start