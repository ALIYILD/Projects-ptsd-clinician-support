from __future__ import annotations

from pathlib import Path

from ptsd_support.db.adapter import DatabaseSettings, connect


BASE_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _migration_dir_for(engine: str) -> Path:
    engine_dir = BASE_MIGRATIONS_DIR / engine
    if engine_dir.exists():
        return engine_dir
    return BASE_MIGRATIONS_DIR


def _list_migration_files(engine: str) -> list[Path]:
    return sorted(_migration_dir_for(engine).glob("*.sql"))


def run_migrations(target: DatabaseSettings | str | Path) -> None:
    settings = target if isinstance(target, DatabaseSettings) else DatabaseSettings.from_target(target)
    conn = connect(settings)
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
        for migration in _list_migration_files(settings.engine):
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
