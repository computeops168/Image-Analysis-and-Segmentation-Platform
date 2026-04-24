from __future__ import annotations

from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine

# Ensure models are registered before create_all runs.
from app.models.job import Job  # noqa: F401
from app.models.image import ImageAsset  # noqa: F401
from app.models.user import User  # noqa: F401

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_images_table()
    _migrate_jobs_table()


def _migrate_images_table() -> None:
    required_columns = {
        "user_id": "TEXT NOT NULL DEFAULT 'admin'",
        "storage_relpath": "TEXT NOT NULL DEFAULT ''",
        "sensitivity_level": "TEXT NOT NULL DEFAULT 'quarantine'",
        "sensitivity_score": "REAL NOT NULL DEFAULT 0.0",
        "contains_sensitive_regions": "INTEGER NOT NULL DEFAULT 0",
        "segmentation_model": "TEXT",
    }

    with engine.begin() as conn:
        existing_rows = conn.exec_driver_sql("PRAGMA table_info(images)").fetchall()
        existing_columns = {row[1] for row in existing_rows}
        for column_name, column_ddl in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE images ADD COLUMN {column_name} {column_ddl}"
            )


def _migrate_jobs_table() -> None:
    required_columns = {
        "user_id": "TEXT NOT NULL DEFAULT 'admin'",
    }

    with engine.begin() as conn:
        existing_rows = conn.exec_driver_sql("PRAGMA table_info(jobs)").fetchall()
        existing_columns = {row[1] for row in existing_rows}
        for column_name, column_ddl in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE jobs ADD COLUMN {column_name} {column_ddl}"
            )

def get_session():
    with Session(engine) as session:
        yield session
