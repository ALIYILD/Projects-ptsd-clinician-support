from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ptsd_support.db.adapter import (
    DatabaseSettings,
    connect,
    split_sql_statements,
    translate_sql,
)


class DatabaseSettingsTests(unittest.TestCase):
    def test_from_target_defaults_to_sqlite_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nested" / "ptsd.db"

            with patch.dict(os.environ, {}, clear=True):
                settings = DatabaseSettings.from_target(db_path)

            self.assertEqual(settings.engine, "sqlite")
            self.assertEqual(settings.sqlite_path, db_path.resolve())
            self.assertIsNone(settings.postgres_dsn)

    def test_from_target_uses_env_sqlite_path_when_target_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_db_path = Path(tmpdir) / "env" / "ptsd.db"

            with patch.dict(
                os.environ,
                {"PTSD_SUPPORT_DB_PATH": str(env_db_path)},
                clear=True,
            ):
                settings = DatabaseSettings.from_target()

            self.assertEqual(settings.engine, "sqlite")
            self.assertEqual(settings.sqlite_path, env_db_path.resolve())

    def test_from_target_selects_postgres_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "PTSD_SUPPORT_DB_ENGINE": "postgres",
                "PTSD_SUPPORT_POSTGRES_DSN": "postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support",
            },
            clear=True,
        ):
            settings = DatabaseSettings.from_target("ignored.db")

        self.assertEqual(settings.engine, "postgres")
        self.assertEqual(
            settings.postgres_dsn,
            "postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support",
        )
        self.assertIsNone(settings.sqlite_path)


class AdapterUtilityTests(unittest.TestCase):
    def test_translate_sql_keeps_sqlite_qmarks(self):
        self.assertEqual(translate_sql("SELECT * FROM demo WHERE id = ?", "sqlite"), "SELECT * FROM demo WHERE id = ?")

    def test_translate_sql_converts_postgres_qmarks(self):
        self.assertEqual(
            translate_sql("SELECT * FROM demo WHERE id = ? AND status = ?", "postgres"),
            "SELECT * FROM demo WHERE id = %s AND status = %s",
        )

    def test_split_sql_statements_preserves_semicolons_inside_quotes(self):
        statements = split_sql_statements(
            "INSERT INTO demo(text) VALUES ('alpha;beta'); INSERT INTO demo(text) VALUES (\"gamma;delta\");"
        )
        self.assertEqual(len(statements), 2)
        self.assertIn("'alpha;beta'", statements[0])
        self.assertIn('"gamma;delta"', statements[1])


class AdapterConnectTests(unittest.TestCase):
    def test_connect_configures_sqlite_runtime(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "runtime" / "ptsd.db"
            conn = connect(db_path)
            try:
                self.assertEqual(conn.row_factory, sqlite3.Row)
                self.assertTrue(db_path.parent.exists())

                busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
                journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
                synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]
                temp_store = conn.execute("PRAGMA temp_store;").fetchone()[0]
                foreign_keys = conn.execute("PRAGMA foreign_keys;").fetchone()[0]

                self.assertEqual(busy_timeout, 30000)
                self.assertEqual(str(journal_mode).lower(), "wal")
                self.assertEqual(synchronous, 1)
                self.assertEqual(temp_store, 2)
                self.assertEqual(foreign_keys, 1)

                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute("INSERT INTO sample(name) VALUES (?)", ("alice",))
                row = conn.execute("SELECT id, name FROM sample").fetchone()

                self.assertEqual(row["name"], "alice")
                self.assertEqual(row[0], 1)
            finally:
                conn.close()

    def test_connect_requires_dsn_for_postgres(self):
        settings = DatabaseSettings(engine="postgres", postgres_dsn=None)
        with self.assertRaises(ValueError):
            connect(settings)

    def test_connect_raises_import_error_when_psycopg_missing(self):
        settings = DatabaseSettings(
            engine="postgres",
            postgres_dsn="postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support",
        )
        with patch.dict("sys.modules", {"psycopg": None}):
            with self.assertRaises(ImportError) as excinfo:
                connect(settings)
        self.assertIn("psycopg", str(excinfo.exception))


if __name__ == "__main__":
    unittest.main()
