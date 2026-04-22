from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ptsd_support.db.migrations import run_migrations
from ptsd_support.services.care_plans import generate_care_plan, list_care_plans, save_care_plan
from ptsd_support.services.cases import create_case


class CarePlanTests(unittest.TestCase):
    def test_generate_and_save_care_plan(self):
        case = {
            "patient_id": "case-1",
            "nightmares": True,
            "symptoms": ["nightmares", "avoidance"],
        }
        evaluation = {"red_flags": [], "contraindications": [], "missing_information": []}
        support_plan = {"domains": ["psychotherapy", "medication"]}
        payload = generate_care_plan(case, evaluation, support_plan)
        self.assertEqual(payload["status"], "draft")
        self.assertTrue(payload["home_tasks"])

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "care.db"
            run_migrations(db)
            created = create_case(
                db,
                {
                    "patient_id": "patient-1",
                    "age": 30,
                    "trauma_exposure_summary": "assault",
                    "symptom_duration_weeks": 12,
                    "functional_impairment": "work impact",
                },
            )
            saved = save_care_plan(db, case_key=created["case_key"], plan_type="home_tasks", payload=payload)
            self.assertEqual(saved["plan_type"], "home_tasks")
            plans = list_care_plans(db, case_key=created["case_key"])
            self.assertEqual(len(plans), 1)
            self.assertEqual(saved["payload"], payload)
            self.assertEqual(plans[0]["payload"], payload)


if __name__ == "__main__":
    unittest.main()
