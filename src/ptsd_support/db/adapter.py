from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


DatabaseEngine = Literal["sqlite", "postgres"]


@dataclass(frozen=True)
class DatabaseSettings:
    engine: DatabaseEngine
    sqlite_path: Path | None = None
    postgres_dsn: str | None = None

    @classmethod
    def from_target(cls, target: str | Path | None = None) -> "DatabaseSettings":
        env_engine = os.environ.get("PTSD_SUPPORT_DB_ENGINE", "").strip().lower()
        if env_engine == "postgres":
            return cls(engine="postgres", postgres_dsn=os.environ.get("PTSD_SUPPORT_POSTGRES_DSN"))

        if target is None:
            target = os.environ.get("PTSD_SUPPORT_DB_PATH", "data/processed/ptsd_support.db")
        return cls(engine="sqlite", sqlite_path=Path(target).expanduser().resolve())


def connect(settings_or_target: DatabaseSettings | str | Path) -> sqlite3.Connection:
    settings = (
        settings_or_target
        if isinstance(settings_or_target, DatabaseSettings)
        else DatabaseSettings.from_target(settings_or_target)
    )
    if settings.engine == "postgres":
        raise NotImplementedError(
            "Postgres runtime is prepared but not yet implemented in the adapter layer. "
            "Set PTSD_SUPPORT_DB_ENGINE=sqlite or omit it to use the verified SQLite path."
        )

    assert settings.sqlite_path is not None
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn
