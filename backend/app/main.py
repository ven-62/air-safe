from fastapi import FastAPI
from app.routes.sensor_routes import router
from app.utils.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ESP32 Air Monitoring API")

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"status": "API running"}