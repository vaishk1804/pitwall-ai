# app/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase 
from app.core.config import get_settings

class Base(DeclarativeBase):
  pass

def get_engine(url: str | None = None):
  settings = get_settings()
  db_url = url or settings.database_url
  return create_engine(db_url, pool_pre_ping=True, echo=settings.debug)

def get_session_factory(url: str | None = None):
  engine= get_engine(url)
  return sessionmaker(autocommit=False, autoflush=False, bind=engine)

SessionLocal = get_session_factory()

def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()