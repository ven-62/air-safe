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
