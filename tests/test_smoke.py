from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from ptsd_support.api.app import AppConfig, create_app, healthcheck
from ptsd_support.db.schema import initialize_database, connect
from ptsd_support.ingest.guidelines import ingest_guideline_seed
from ptsd_support.services.assessment import evaluate_case
from ptsd_support.services.retrieval import get_ingest_summary, list_reviews_or_trials, search_articles


class SmokeTests(unittest.TestCase):
    def test_healthcheck(self):
        self.assertEqual(healthcheck()["status"], "ok")

    def test_retrieval_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            initialize_database(db_path)
            conn = connect(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO articles(
                        canonical_key, pmid, doi, title, journal, publication_year,
                        publication_date, is_open_access, has_fulltext_link, normalized_title
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "pmid:1",
                        "1",
                        "10.1/example",
                        "PTSD psychotherapy review",
                        "Journal A",
                        2024,
                        "2024-01-01",
                        1,
                        1,
                        "ptsd psychotherapy review",
                    ),
                )
                article_id = conn.execute("SELECT id FROM articles").fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO article_publication_types(article_id, publication_type)
                    VALUES (?, ?), (?, ?)
                    """,
                    (article_id, "Review", article_id, "Clinical Trial"),
                )
                conn.execute(
                    """
                    INSERT INTO article_sources(
                        article_id, source_name, source_native_id, raw_row_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (article_id, "pubmed", "1", "{}"),
                )
                conn.commit()
            finally:
                conn.close()

            results = search_articles(db_path, "psychotherapy", publication_types=["review"], source_name="pubmed")
            self.assertEqual(len(results), 1)
            self.assertIn("Review", results[0]["publication_types"])

            filtered = list_reviews_or_trials(db_path, query="ptsd")
            self.assertEqual(len(filtered), 1)

            summary = get_ingest_summary(db_path)
            self.assertEqual(summary["articles"], 1)

    def test_assessment_red_flags(self):
        payload = {
            "patient_id": "p-1",
            "age": 34,
            "symptom_duration_weeks": 12,
            "trauma_exposure_summary": "combat trauma",
            "functional_impairment": "sleep disturbance and work impairment",
            "suicidal_ideation": True,
            "recent_attempt": True,
            "nightmares": True,
        }
        result = evaluate_case(payload).to_dict()
        self.assertTrue(result["red_flags"])
        self.assertTrue(result["clinician_review_required"])
        self.assertIn("suicidality", [item["code"] for item in result["red_flags"]])

    def test_wsgi_endpoints(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "api.db"
            log_path = Path(tmpdir) / "audit.jsonl"
            request_log_path = Path(tmpdir) / "requests.jsonl"
            initialize_database(db_path)
            seed_path = Path("/Users/aliyildirim/Projects/ptsd-clinician-support/data/raw/guidelines/ptsd_guidelines.json")
            ingest_guideline_seed(db_path, seed_path)
            conn = connect(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO articles(
                        canonical_key, pmid, doi, title, journal, publication_year,
                        publication_date, is_open_access, has_fulltext_link, normalized_title
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "pmid:9",
                        "9",
                        "10.9/example",
                        "EMDR review for PTSD",
                        "Journal B",
                        2023,
                        "2023-05-01",
                        1,
                        1,
                        "emdr review for ptsd",
                    ),
                )
                article_id = conn.execute("SELECT id FROM articles").fetchone()[0]
                conn.execute(
                    "INSERT INTO article_publication_types(article_id, publication_type) VALUES (?, ?)",
                    (article_id, "Review"),
                )
                conn.execute(
                    "INSERT INTO article_sources(article_id, source_name, source_native_id, raw_row_json) VALUES (?, ?, ?, ?)",
                    (article_id, "pubmed", "9", "{}"),
                )
                conn.commit()
            finally:
                conn.close()

            app = create_app(AppConfig(db_path=db_path, audit_log_path=log_path, request_log_path=request_log_path))

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
                }
                response = b"".join(app(environ, start_response))
                return captured["status"], response

            status, body = run_request("GET", "/health")
            self.assertEqual(status, "200 OK")
            self.assertIn(b"ptsd-clinician-support", body)
            self.assertIn(b"request_id", body)

            status, body = run_request("GET", "/literature/search", query="query=emdr&limit=5&type=review")
            self.assertEqual(status, "200 OK")
            self.assertIn(b"EMDR review for PTSD", body)

            status, body = run_request(
                "POST",
                "/assessment/evaluate",
                body=b'{"patient_id":"1","age":42,"symptom_duration_weeks":8,"trauma_exposure_summary":"trauma","functional_impairment":"yes","suicidal_ideation":true}',
            )
            self.assertEqual(status, "200 OK")
            self.assertIn(b"suicidality", body)

            status, body = run_request("GET", "/guidelines")
            self.assertEqual(status, "200 OK")
            self.assertIn(b"VA/DoD", body)

            status, body = run_request(
                "POST",
                "/cases",
                body=b'{"patient_id":"p-9","clinician_id":"c-1","age":29,"trauma_exposure_summary":"assault trauma","symptom_duration_weeks":14,"functional_impairment":"work impact","symptoms":["avoidance"]}',
            )
            self.assertEqual(status, "200 OK")
            self.assertIn(b"case_key", body)


if __name__ == "__main__":
    unittest.main()
