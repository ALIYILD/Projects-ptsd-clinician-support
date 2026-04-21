from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "treatment_rules.json"


@lru_cache(maxsize=4)
def load_rules(path: str | Path = DEFAULT_RULES_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_domain_rule_output(
    domain: str,
    *,
    case_evaluation: dict[str, Any],
    rules_path: str | Path = DEFAULT_RULES_PATH,
) -> dict[str, Any]:
    rules = load_rules(rules_path)["domains"]
    if domain not in rules:
        return {
            "domain": domain,
            "status": "unsupported",
            "review_only": True,
            "reasons": [f"No deterministic rules configured for domain '{domain}'."],
            "blockers": [],
            "guideline_domains": [],
        }

    config = rules[domain]
    red_flag_codes = {item["code"] for item in case_evaluation.get("red_flags", [])}
    contraindication_codes = {item["category"] for item in case_evaluation.get("contraindications", [])}
    blockers = []
    reasons = [config["message"]]

    for code in config.get("blockers_any", []):
        if code in red_flag_codes:
            blockers.append({"type": "red_flag", "code": code})

    for code in config.get("contraindication_blockers", []):
        if code in contraindication_codes:
            blockers.append({"type": "contraindication", "code": code})

    missing = []
    for field in config.get("allowed_if_missing", []):
        if field in case_evaluation.get("missing_information", []):
            missing.append(field)

    status = "blocked" if blockers else "review"
    if missing:
        reasons.append(f"Additional data recommended before domain review: {', '.join(missing)}.")
    if blockers:
        reasons.append("One or more deterministic blockers were triggered.")
    else:
        reasons.append("No deterministic blockers were triggered from current case fields.")

    return {
        "domain": domain,
        "title": config["title"],
        "status": status,
        "review_only": True,
        "reasons": reasons,
        "blockers": blockers,
        "guideline_domains": config.get("guideline_domains", []),
        "missing_information": missing,
    }
