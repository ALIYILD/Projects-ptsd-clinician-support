from __future__ import annotations

import unittest

from ptsd_support.services.rules import build_domain_rule_output


class RulesTests(unittest.TestCase):
    def test_blocked_domain(self):
        result = build_domain_rule_output(
            "psychotherapy",
            case_evaluation={
                "red_flags": [{"code": "suicidality"}],
                "contraindications": [{"category": "acute_safety"}],
                "missing_information": [],
            },
        )
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["blockers"])

    def test_review_domain(self):
        result = build_domain_rule_output(
            "medication",
            case_evaluation={
                "red_flags": [],
                "contraindications": [],
                "missing_information": [],
            },
        )
        self.assertEqual(result["status"], "review")
        self.assertTrue(result["review_only"])


if __name__ == "__main__":
    unittest.main()
