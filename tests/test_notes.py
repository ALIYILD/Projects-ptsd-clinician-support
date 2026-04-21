from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ptsd_support.db.migrations import run_migrations
from ptsd_support.services.cases import create_case
from ptsd_support.services.notes import draft_clinician_note, list_note_drafts, save_note_draft


class NotesTests(unittest.TestCase):
    def test_draft_and_save_note(self):
        payload = draft_clinician_note(
            case={"patient_id": "p1"},
            case_evaluation={"assessment_summary": "summary", "triage_note": "triage"},
            support_plan={"domains": ["psychotherapy"]},
            note_type="assessment",
        )
        self.assertEqual(payload["note_type"], "assessment")
        self.assertTrue(payload["sections"])

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "notes.db"
            run_migrations(db)
            created = create_case(
                db,
                {
                    "patient_id": "patient-2",
                    "age": 33,
                    "trauma_exposure_summary": "disaster trauma",
                    "symptom_duration_weeks": 6,
                    "functional_impairment": "home impact",
                },
            )
            saved = save_note_draft(db, case_key=created["case_key"], note_type="assessment", payload=payload)
            self.assertEqual(saved["note_type"], "assessment")
            self.assertEqual(len(list_note_drafts(db, case_key=created["case_key"])), 1)


if __name__ == "__main__":
    unittest.main()
