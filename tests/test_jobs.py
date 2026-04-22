from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from ptsd_support.api.app import AppConfig, create_app
from ptsd_support.db.schema import connect
from ptsd_support.services.auth import create_api_token, create_user
from ptsd_support.services.jobs import enqueue_job, process_next_job


class JobTests(unittest.TestCase):
    def test_guideline_job_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_dir = Path(tmpdir) / "jobs"
            db_path = Path(tmpdir) / "jobs.db"
            seed = Path("/Users/aliyildirim/Projects/ptsd-clinician-support/data/raw/guidelines/ptsd_guidelines.json")
            job = enqueue_job(
                queue_dir,
                "ingest_guidelines",
                {"db_path": str(db_path), "seed_path": str(seed)},
            )
            self.assertEqual(job["status"], "pending")
            result = process_next_job(queue_dir)
            self.assertEqual(result["status"], "done")
            conn = connect(db_path)
            try:
                count = conn.execute("SELECT COUNT(*) FROM guidelines").fetchone()[0]
                self.assertGreaterEqual(count, 1)
            finally:
                conn.close()

    def test_job_status_persists_and_is_exposed_via_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_dir = Path(tmpdir) / "jobs"
            db_path = Path(tmpdir) / "jobs-api.db"
            seed = Path("/Users/aliyildirim/Projects/ptsd-clinician-support/data/raw/guidelines/ptsd_guidelines.json")
            create_user(db_path, user_key="admin-1", display_name="Admin", role="admin")
            token = create_api_token(db_path, user_key="admin-1", label="jobs")
            app = create_app(
                AppConfig(
                    db_path=db_path,
                    audit_log_path=Path(tmpdir) / "audit.jsonl",
                    request_log_path=Path(tmpdir) / "requests.jsonl",
                    queue_dir=queue_dir,
                    require_auth=True,
                )
            )

            def run_request(method: str, path: str, body: bytes = b"", query: str = ""):
                captured = {}

                def start_response(status, headers):
                    captured["status"] = status
                    captured["headers"] = headers

                environ = {
                    "REQUEST_METHOD": method,
                    "PATH_INFO": path,
                    "QUERY_STRING": query,
                    "CONTENT_LENGTH": str(len(body)),
                    "wsgi.input": BytesIO(body),
                    "HTTP_AUTHORIZATION": f"Bearer {token['token']}",
                }
                response = b"".join(app(environ, start_response))
                return captured["status"], response

            status, body = run_request(
                "POST",
                "/jobs",
                body=json.dumps(
                    {
                        "job_type": "ingest_guidelines",
                        "payload": {"seed_path": str(seed), "db_path": str(db_path)},
                    }
                ).encode("utf-8"),
            )
            self.assertEqual(status, "200 OK")
            job = json.loads(body.decode("utf-8"))
            self.assertEqual(job["status"], "pending")

            processed = process_next_job(queue_dir)
            self.assertEqual(processed["status"], "done")

            status, body = run_request("GET", f"/jobs/{job['job_id']}")
            self.assertEqual(status, "200 OK")
            payload = json.loads(body.decode("utf-8"))
            self.assertEqual(payload["status"], "done")
            self.assertIn("result", payload)


if __name__ == "__main__":
    unittest.main()
