from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ptsd_support.services.audit import append_request_event, read_jsonl_events


class AuditTests(unittest.TestCase):
    def test_request_event_redacts_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "requests.jsonl"
            append_request_event(
                log_path,
                {
                    "path": "/auth/tokens",
                    "actor": "admin-1",
                    "authorization": "Bearer secret-token",
                    "payload": {"token": "plaintext", "label": "secondary"},
                },
            )
            rows = read_jsonl_events(log_path, limit=10)
            self.assertEqual(rows[0]["authorization"], "[REDACTED]")
            self.assertEqual(rows[0]["payload"]["token"], "[REDACTED]")
            self.assertEqual(rows[0]["payload"]["label"], "secondary")

    def test_request_event_filters_match_subset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "requests.jsonl"
            append_request_event(log_path, {"path": "/health", "status": 200, "actor": "local-dev"})
            append_request_event(log_path, {"path": "/auth/me", "status": 200, "actor": "admin-1"})
            append_request_event(log_path, {"path": "/jobs", "status": 403, "actor": "viewer-1"})

            filtered = read_jsonl_events(log_path, filters={"status": 200, "contains": "/auth"})
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]["path"], "/auth/me")


if __name__ == "__main__":
    unittest.main()
