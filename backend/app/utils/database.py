import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from config import Config

SQLDATABASE = Config.SQLDATABASE
SQLHOST = Config.SQLHOST
SQLPASSWORD = Config.SQLPASSWORD
SQLPORT = Config.SQLPORT
SQLUSER = Config.SQLUSER

DATABASE_URL =  f"postgresql://{SQLUSER}:{SQLPASSWORD}@{SQLHOST}:{SQLPORT}/{SQLDATABASE}"

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    """Get a database session for FastAPI dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        