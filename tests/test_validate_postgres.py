from __future__ import annotations

import io
import importlib.util
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from ptsd_support.db.adapter import DatabaseSettings


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_postgres.py"
_SPEC = importlib.util.spec_from_file_location("validate_postgres_local", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
validate_postgres = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = validate_postgres
_SPEC.loader.exec_module(validate_postgres)


class ValidatePostgresTests(unittest.TestCase):
    def test_validate_configuration_rejects_non_postgres_engine(self):
        settings = DatabaseSettings(engine="sqlite")

        step = validate_postgres.validate_configuration(settings)

        self.assertFalse(step.ok)
        self.assertIn("not postgres", step.detail)

    def test_validate_configuration_requires_dsn(self):
        settings = DatabaseSettings(engine="postgres", postgres_dsn=None)

        step = validate_postgres.validate_configuration(settings)

        self.assertFalse(step.ok)
        self.assertIn("DSN is missing", step.detail)

    @patch.object(validate_postgres, "fetch_scalar")
    @patch.object(validate_postgres, "run_migrations")
    @patch.object(validate_postgres, "connect")
    def test_validate_postgres_runs_connect_migrations_and_health_checks(
        self,
        mock_connect: MagicMock,
        mock_run_migrations: MagicMock,
        mock_fetch_scalar: MagicMock,
    ):
        settings = DatabaseSettings(
            engine="postgres",
            postgres_dsn="postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support",
        )
        preflight_conn = MagicMock()
        health_conn = MagicMock()
        mock_connect.side_effect = [preflight_conn, health_conn]
        mock_fetch_scalar.side_effect = ["PostgreSQL 16.2", 1]

        report = validate_postgres.validate_postgres(settings)

        self.assertTrue(report.ok)
        self.assertEqual([step.name for step in report.steps], ["config", "connect", "migrations", "health", "server_version"])
        mock_connect.assert_has_calls([call(settings), call(settings)])
        mock_run_migrations.assert_called_once_with(settings)
        mock_fetch_scalar.assert_has_calls([call(health_conn, "SELECT version()"), call(health_conn, "SELECT 1 AS ok")])
        preflight_conn.close.assert_called_once_with()
        health_conn.close.assert_called_once_with()

    @patch.object(validate_postgres, "connect")
    def test_validate_postgres_reports_connection_failure(self, mock_connect: MagicMock):
        settings = DatabaseSettings(
            engine="postgres",
            postgres_dsn="postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support",
        )
        mock_connect.side_effect = ImportError("psycopg missing")

        report = validate_postgres.validate_postgres(settings)

        self.assertFalse(report.ok)
        self.assertEqual(report.steps[-1].name, "connect")
        self.assertIn("ImportError", report.steps[-1].detail)

    @patch.object(validate_postgres, "validate_postgres")
    @patch.object(validate_postgres, "resolve_settings")
    def test_main_returns_zero_and_prints_report(
        self,
        mock_resolve_settings: MagicMock,
        mock_validate_postgres: MagicMock,
    ):
        settings = DatabaseSettings(
            engine="postgres",
            postgres_dsn="postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support",
        )
        report = validate_postgres.ValidationReport(
            ok=True,
            settings=settings,
            steps=[validate_postgres.ValidationStep(name="config", ok=True, detail="configured")],
        )
        mock_resolve_settings.return_value = settings
        mock_validate_postgres.return_value = report

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = validate_postgres.main([])

        self.assertEqual(exit_code, 0)
        self.assertIn("engine=postgres", output.getvalue())


if __name__ == "__main__":
    unittest.main()
