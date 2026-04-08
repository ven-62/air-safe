import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database configuration using environment variables
    SQLDATABASE = os.getenv("SQLDATABASE")
    SQLHOST = os.getenv("SQLHOST")
    SQLPASSWORD = os.getenv("SQLPASSWORD")
    SQLPORT = os.getenv("SQLPORT")
    SQLUSER = os.getenv("SQLUSER")