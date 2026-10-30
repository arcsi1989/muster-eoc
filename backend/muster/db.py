from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine


def create_fresh_engine(database_path: Path) -> Engine:
    """Creates the engine and empty tables. Every backend start begins a fresh scenario."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine
