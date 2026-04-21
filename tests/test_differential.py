from __future__ import annotations

import unittest

from ptsd_support.services.differential import build_differential_diagnosis


def _comparison(result: dict, condition: str) -> dict:
    for item in result["comparisons"]:
        if item["condition"] == condition:
            return item
    raise AssertionError(f"Comparison not found: {condition}")


class DifferentialTests(unittest.TestCase):
    def test_ptsd_preferred_over_asd_when_duration_exceeds_one_month(self):
        result = build_differential_diagnosis(
            {
                "trauma_exposure_summary": "Patient survived a motor vehicle collision.",
                "symptom_duration_weeks": 8,
                "functional_impairment": "Missing work shifts and avoiding driving.",
                "symptoms": ["nightmares", "flashbacks", "avoidance", "hypervigilance"],
            }
        )

        ptsd = _comparison(result, "PTSD")
        asd = _comparison(result, "Acute stress disorder")

        self.assertEqual(ptsd["status"], "higher_priority_review")
        self.assertIn(
            "Symptom duration is at least one month, which fits PTSD timing better than acute stress disorder.",
            ptsd["supporting_features"],
        )
        self.assertIn(
            "Symptom duration is beyond one month, which argues against acute stress disorder.",
            asd["contradicting_features"],
        )
        self.assertTrue(result["review_only"])

    def test_asd_considered_in_acute_post_trauma_window(self):
        result = build_differential_diagnosis(
            {
                "trauma_exposure_summary": "Assault two weeks ago.",
                "symptom_duration_days": 14,
                "functional_impairment": "Unable to return to classes.",
                "symptoms": ["intrusive memories", "nightmares", "dissociation"],
            }
        )

        asd = _comparison(result, "Acute stress disorder")
        ptsd = _comparison(result, "PTSD")

        self.assertIn(asd["status"], {"higher_priority_review", "consider"})
        self.assertIn(
            "Duration falls in the 3-day to 1-month window that fits acute stress disorder.",
            asd["supporting_features"],
        )
        self.assertIn(
            "Symptom duration is under one month, which argues against PTSD timing.",
            ptsd["contradicting_features"],
        )

    def test_complex_ptsd_and_mdd_and_gad_support_are_separated(self):
        result = build_differential_diagnosis(
            {
                "trauma_exposure_summary": "Chronic childhood abuse with repeated threats.",
                "symptom_duration_months": 24,
                "functional_impairment": "Severe relational instability and occupational decline.",
                "symptoms": [
                    "flashbacks",
                    "avoidance",
                    "hypervigilance",
                    "emotion dysregulation",
                    "worthless",
                    "relationship disturbance",
                    "depressed mood",
                    "anhedonia",
                    "excessive worry",
                ],
            }
        )

        cptsd = _comparison(result, "Complex PTSD")
        mdd = _comparison(result, "Major depressive disorder")
        gad = _comparison(result, "Generalized anxiety disorder")

        self.assertEqual(cptsd["status"], "higher_priority_review")
        self.assertIn("Repeated or prolonged trauma exposure is described.", cptsd["supporting_features"])
        self.assertIn("Depressed mood or anhedonia is present.", mdd["supporting_features"])
        self.assertIn("Persistent, difficult-to-control worry is described.", gad["supporting_features"])

    def test_substance_and_tbi_overlap_and_escalations(self):
        result = build_differential_diagnosis(
            {
                "trauma_exposure_summary": "Workplace accident with concussion.",
                "symptom_duration_weeks": 3,
                "symptoms": [
                    "after using alcohol symptoms worsen",
                    "withdrawal tremor",
                    "headache",
                    "dizziness",
                    "memory problems",
                ],
                "recent_substance_use": True,
                "withdrawal_risk": True,
                "head_injury": True,
                "loss_of_consciousness": True,
            }
        )

        substance = _comparison(result, "Substance-induced symptoms")
        tbi = _comparison(result, "TBI overlap")

        self.assertIn(
            "Symptoms appear temporally linked to substance use or withdrawal.",
            substance["supporting_features"],
        )
        self.assertIn("Head injury or TBI history is documented.", tbi["supporting_features"])
        self.assertTrue(
            any("intoxication or withdrawal" in note for note in result["escalation_notes"])
        )
        self.assertTrue(any("TBI or head-injury overlap" in note for note in result["escalation_notes"]))

    def test_psychosis_and_mania_force_rule_out_and_escalation(self):
        result = build_differential_diagnosis(
            {
                "symptoms": ["auditory hallucinations", "grandiose beliefs", "decreased need for sleep"],
                "hallucinations": True,
                "grandiosity": True,
                "decreased_need_for_sleep": True,
            }
        )

        rule_out = _comparison(result, "Psychosis/mania rule-out")
        ptsd = _comparison(result, "PTSD")

        self.assertEqual(rule_out["status"], "higher_priority_review")
        self.assertTrue(any("Psychotic symptoms" in item for item in rule_out["supporting_features"]))
        self.assertTrue(any("mania" in note.lower() for note in result["escalation_notes"]))
        self.assertTrue(
            any("alternative explanation" in item for item in ptsd["contradicting_features"])
        )

    def test_missing_data_is_reported_when_case_is_sparse(self):
        result = build_differential_diagnosis({"symptoms": ["poor sleep"]})

        self.assertTrue(result["missing_data"])
        ptsd = _comparison(result, "PTSD")
        self.assertEqual(ptsd["status"], "insufficient_data")
        self.assertTrue(ptsd["missing_data"])


if __name__ == "__main__":
    unittest.main()
