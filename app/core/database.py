from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import Config

DB_URL = (
    f"postgresql+psycopg2://{Config.DB_USER}:{Config.DB_PASSWORD}"
    f"@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}?sslmode=require"
)

engine = create_engine(DB_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

@event.listens_for(engine, "connect")
def set_postgresql_timezone(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET TIME ZONE 'Asia/Manila';")
    cursor.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
