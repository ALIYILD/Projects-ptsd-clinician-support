from __future__ import annotations

from pathlib import Path

from ptsd_support.db.adapter import DatabaseSettings, connect as adapter_connect
from ptsd_support.db.migrations import run_migrations


def connect(db_path: str | Path):
    return adapter_connect(db_path)


def initialize_database(db_path: str | Path) -> None:
    run_migrations(DatabaseSettings.from_target(db_path))
