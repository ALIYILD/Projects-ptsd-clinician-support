from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal


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


class DBRow(dict):
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class DBCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    @property
    def description(self) -> Any:
        return getattr(self._cursor, "description", None)

    def fetchone(self) -> DBRow | None:
        row = self._cursor.fetchone()
        return _normalize_row(row)

    def fetchall(self) -> list[DBRow]:
        return [_normalize_row(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        for row in self._cursor:
            normalized = _normalize_row(row)
            if normalized is not None:
                yield normalized

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class DBConnection:
    def __init__(self, engine: DatabaseEngine, raw_connection: Any) -> None:
        self.engine = engine
        self._conn = raw_connection
        self.row_factory = getattr(raw_connection, "row_factory", None)

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> DBCursor:
        translated_sql = translate_sql(sql, self.engine)
        cursor = self._conn.execute(translated_sql, tuple(params or ()))
        return DBCursor(cursor)

    def executescript(self, sql: str) -> None:
        if self.engine == "sqlite":
            self._conn.executescript(sql)
            return
        for statement in split_sql_statements(sql):
            self._conn.execute(statement)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def _normalize_row(row: Any) -> DBRow | None:
    if row is None:
        return None
    if isinstance(row, DBRow):
        return row
    if isinstance(row, sqlite3.Row):
        return DBRow(dict(row))
    if isinstance(row, dict):
        return DBRow(row)
    if hasattr(row, "_asdict"):
        return DBRow(row._asdict())
    if isinstance(row, (list, tuple)):
        return DBRow({str(i): value for i, value in enumerate(row)})
    return DBRow({"value": row})


def translate_sql(sql: str, engine: DatabaseEngine) -> str:
    if engine == "sqlite":
        return sql
    if "?" not in sql:
        return sql
    parts = sql.split("?")
    return "%s".join(parts)


def split_sql_statements(sql: str) -> list[str]:
    statements = []
    current: list[str] = []
    in_single = False
    in_double = False
    for char in sql:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def fetch_scalar(conn: DBConnection, sql: str, params: Iterable[Any] | None = None) -> Any:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return row[0]


def insert_and_get_id(conn: DBConnection, sql: str, params: Iterable[Any] | None = None) -> int:
    if conn.engine == "postgres" and "returning" not in sql.lower():
        sql = f"{sql.rstrip()} RETURNING id"
    cursor = conn.execute(sql, params)
    if conn.engine == "postgres":
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Expected RETURNING id row from Postgres insert.")
        return int(row[0])
    return int(fetch_scalar(conn, "SELECT last_insert_rowid()"))


def connect(settings_or_target: DatabaseSettings | str | Path) -> DBConnection:
    settings = (
        settings_or_target
        if isinstance(settings_or_target, DatabaseSettings)
        else DatabaseSettings.from_target(settings_or_target)
    )
    if settings.engine == "postgres":
        if not settings.postgres_dsn:
            raise ValueError("PTSD_SUPPORT_POSTGRES_DSN must be set when PTSD_SUPPORT_DB_ENGINE=postgres.")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise ImportError(
                "Postgres runtime requires psycopg. Install the optional dependency group with `pip install -e '.[postgres]'`."
            ) from exc
        raw = psycopg.connect(settings.postgres_dsn, row_factory=dict_row)
        return DBConnection("postgres", raw)

    assert settings.sqlite_path is not None
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(settings.sqlite_path, timeout=30)
    raw.execute("PRAGMA busy_timeout = 30000;")
    raw.execute("PRAGMA journal_mode = WAL;")
    raw.execute("PRAGMA synchronous = NORMAL;")
    raw.execute("PRAGMA temp_store = MEMORY;")
    raw.execute("PRAGMA foreign_keys = ON;")
    raw.row_factory = sqlite3.Row
    return DBConnection("sqlite", raw)
