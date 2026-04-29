import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_data_dir() -> Path:
    """Get data directory. Create directory if needed."""
    current_dir = Path(__file__).resolve().parent
    tubechallenge_dir = current_dir.parent
    root_dir = tubechallenge_dir.parent
    data_dir = root_dir / "data"

    data_dir.mkdir(parents=True, exist_ok=True)  # create directory if missing

    return data_dir


def get_default_sqlite_url() -> str:
    """Get default SQLite path."""
    db_dir = get_data_dir()
    db_path = db_dir / "tube_challenge.db"

    return f"sqlite:///{db_path}"


DATABASE_URL = os.getenv("TUBE_CHALLENGE_DB_URL", get_default_sqlite_url())

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Get database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
