from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ptsd_support.db.schema import initialize_database
from ptsd_support.services.cases import (
    add_case_review,
    create_case,
    get_case_by_key,
    list_case_reviews,
    list_cases,
    record_case_recommendation,
)


class CaseServiceTests(unittest.TestCase):
    def test_case_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cases.db"
            initialize_database(db_path)
            created = create_case(
                db_path,
                {
                    "patient_id": "patient-1",
                    "clinician_id": "clinician-1",
                    "age": 41,
                    "trauma_exposure_summary": "motor vehicle accident",
                    "symptom_duration_weeks": 18,
                    "functional_impairment": "work impairment",
                    "symptoms": ["nightmares", "avoidance"],
                    "flags": {"nightmares": True},
                },
            )
            self.assertEqual(created["patient_id"], "patient-1")
            fetched = get_case_by_key(db_path, created["case_key"])
            self.assertEqual(fetched["age"], 41)
            self.assertEqual(len(list_cases(db_path)), 1)

            review = add_case_review(
                db_path,
                created["case_key"],
                reviewer_id="reviewer-1",
                review_type="assessment",
                review_status="needs_review",
                note="Needs suicide risk clarification",
                payload={"risk": "unclear"},
            )
            self.assertEqual(review["review_status"], "needs_review")
            self.assertEqual(len(list_case_reviews(db_path, created["case_key"])), 1)

            rec = record_case_recommendation(
                db_path,
                created["case_key"],
                recommendation_domain="psychotherapy",
                payload={"status": "review"},
            )
            self.assertEqual(rec["recommendation_domain"], "psychotherapy")


if __name__ == "__main__":
    unittest.main()
