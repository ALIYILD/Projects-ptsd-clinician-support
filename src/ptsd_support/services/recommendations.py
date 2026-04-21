from __future__ import annotations

from pathlib import Path
from typing import Any

from ptsd_support.services.guidelines import list_guideline_recommendations
from ptsd_support.services.rules import build_domain_rule_output
from ptsd_support.services.retrieval import search_articles


TREATMENT_TOPICS = {
    "psychotherapy": [
        {
            "name": "Trauma-focused psychotherapy",
            "modality": "psychotherapy",
            "evidence_basis": "Guideline-supported first-line domain for PTSD treatment support.",
            "search_terms": ["cognitive processing therapy", "prolonged exposure", "emdr", "trauma-focused"],
            "cautions": ["Confirm readiness, dissociation level, safety, and stabilization before planning."],
        }
    ],
    "medication": [
        {
            "name": "Pharmacotherapy evidence review",
            "modality": "medication",
            "evidence_basis": "Evidence review only. Not a prescribing directive.",
            "search_terms": ["ssri", "snri", "sertraline", "paroxetine", "venlafaxine", "prazosin"],
            "cautions": ["Medication outputs require independent contraindication and interaction review."],
        }
    ],
    "neuromodulation": [
        {
            "name": "Neuromodulation evidence review",
            "modality": "neuromodulation",
            "evidence_basis": "Investigational or specialist-reviewed evidence domain.",
            "search_terms": ["rtms", "transcranial magnetic stimulation", "tdcs", "theta burst"],
            "cautions": ["Do not generate protocol orders. Use specialist review and seizure-risk checks."],
        }
    ],
    "supplements": [
        {
            "name": "Supplements and nutrition evidence review",
            "modality": "supplements",
            "evidence_basis": "Low-confidence area unless supported by replicated trials or guidelines.",
            "search_terms": ["omega-3", "supplement", "nutrition", "diet", "vitamin"],
            "cautions": ["Treat as evidence review only; require interaction and safety screening."],
        }
    ],
}


def _evidence_cards(db_path: str | Path, search_terms: list[str], limit_per_term: int = 3) -> list[dict[str, Any]]:
    seen: set[int] = set()
    cards: list[dict[str, Any]] = []
    for term in search_terms:
        rows = search_articles(
            db_path,
            query=term,
            limit=limit_per_term,
            publication_types=["review", "clinical trial"],
        )
        for row in rows:
            article_id = row["id"]
            if article_id in seen:
                continue
            seen.add(article_id)
            cards.append(
                {
                    "article_id": article_id,
                    "title": row["title"],
                    "pmid": row.get("pmid"),
                    "doi": row.get("doi"),
                    "journal": row.get("journal"),
                    "publication_year": row.get("publication_year"),
                    "publication_types": row.get("publication_types"),
                    "sources": row.get("sources"),
                }
            )
    return cards


def build_support_plan(
    db_path: str | Path,
    *,
    domains: list[str] | None = None,
    case_context: dict[str, Any] | None = None,
    case_evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_domains = domains or ["psychotherapy", "medication"]
    outputs = []
    for domain in selected_domains:
        if domain not in TREATMENT_TOPICS:
            continue
        rule_output = build_domain_rule_output(
            domain,
            case_evaluation=case_evaluation or {
                "red_flags": [],
                "contraindications": [],
                "missing_information": [],
            },
        )
        for topic in TREATMENT_TOPICS[domain]:
            outputs.append(
                {
                    "name": topic["name"],
                    "modality": topic["modality"],
                    "evidence_basis": topic["evidence_basis"],
                    "cautions": topic["cautions"],
                    "rule_output": rule_output,
                    "guideline_recommendations": list_guideline_recommendations(
                        db_path,
                        clinical_domain=domain,
                        modality=topic["modality"],
                        limit=10,
                    ),
                    "evidence_cards": _evidence_cards(db_path, topic["search_terms"]),
                }
            )
    return {
        "patient_context_used": bool(case_context),
        "domains": selected_domains,
        "outputs": outputs,
        "clinician_review_required": True,
        "note": "This output is evidence support only and not a diagnosis or prescribing instruction.",
    }
