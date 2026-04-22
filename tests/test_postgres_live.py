from __future__ import annotations

import os
import unittest

from ptsd_support.db.adapter import DatabaseSettings

try:
    from scripts.validate_postgres import validate_postgres
except ModuleNotFoundError:  # pragma: no cover
    validate_postgres = None


@unittest.skipUnless(
    os.environ.get("PTSD_SUPPORT_TEST_POSTGRES_DSN"),
    "Set PTSD_SUPPORT_TEST_POSTGRES_DSN to run live Postgres validation.",
)
class LivePostgresValidationTests(unittest.TestCase):
    def test_live_postgres_validation(self):
        settings = DatabaseSettings(
            engine="postgres",
            postgres_dsn=os.environ["PTSD_SUPPORT_TEST_POSTGRES_DSN"],
        )
        report = validate_postgres(settings)
        self.assertTrue(report.ok, msg="\n".join(f"{step.name}: {step.detail}" for step in report.steps))


if __name__ == "__main__":
    unittest.main()
