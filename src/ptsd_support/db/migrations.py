from __future__ import annotations

from pathlib import Path

from ptsd_support.db.adapter import DatabaseSettings, connect


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _list_migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run_migrations(target: DatabaseSettings | str | Path) -> None:
    conn = connect(target)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = {
            row[0]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for migration in _list_migration_files():
            version = migration.name
            if version in applied:
                continue
            sql = migration.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)",
                (version,),
            )
            conn.commit()
    finally:
        conn.close()
