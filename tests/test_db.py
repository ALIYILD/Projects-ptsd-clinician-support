from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ptsd_support.db.migrations import run_migrations
from ptsd_support.db.schema import connect


class DatabaseTests(unittest.TestCase):
    def test_migrations_create_core_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "migrations.db"
            run_migrations(db_path)
            conn = connect(db_path)
            try:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertIn("schema_migrations", tables)
                self.assertIn("articles", tables)
                self.assertIn("patient_cases", tables)
                self.assertIn("users", tables)
                self.assertIn("api_tokens", tables)
                self.assertIn("job_runs", tables)
                condition = conn.execute(
                    "SELECT slug FROM conditions WHERE slug = 'ptsd'"
                ).fetchone()
                self.assertIsNotNone(condition)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
