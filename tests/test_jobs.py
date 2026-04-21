from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ptsd_support.db.schema import connect
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


if __name__ == "__main__":
    unittest.main()
