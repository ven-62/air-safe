import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database configuration using environment variablesprint("cwd:", os.getcwd())
    DB_NAME = os.getenv("DB_NAME")
    DB_HOST = os.getenv("DB_HOST")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_PORT = int(os.getenv("DB_PORT"))
    DB_USER = os.getenv("DB_USER")

    # Security configuration
    SECRET_KEY = os.getenv("SECRET_KEY")
    HF_REPO_ID = os.getenv("HF_REPO_ID")
    HF_TOKEN = os.getenv("HF_TOKEN")

    # MQTT configuration
    MQTT_HOST = os.getenv("MQTT_HOST")
    MQTT_PORT = int(os.getenv("MQTT_PORT"))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

    # OpenWeatherMap API key
    OWM_API_KEY = os.getenv("OWM_API_KEY")