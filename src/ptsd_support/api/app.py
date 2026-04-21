from __future__ import annotations

import json
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from urllib.parse import parse_qs

from ptsd_support.services.assessment import evaluate_case
from ptsd_support.services.audit import append_audit_event, append_request_event
from ptsd_support.services.cases import (
    add_case_review,
    create_case,
    get_case_by_key,
    list_case_reviews,
    list_cases,
    record_case_recommendation,
)
from ptsd_support.services.guidelines import list_guideline_recommendations, list_guidelines
from ptsd_support.services.recommendations import build_support_plan
from ptsd_support.services.retrieval import get_ingest_summary, search_articles


def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "ptsd-clinician-support"}


@dataclass
class AppConfig:
    db_path: Path
    audit_log_path: Path
    request_log_path: Path


def _json_response(start_response, status: str, payload: dict | list) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ]
    start_response(status, headers)
    return [body]


def _read_json(environ) -> dict:
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError:
        length = 0
    raw = environ["wsgi.input"].read(length) if length > 0 else b"{}"
    return json.loads(raw.decode("utf-8") or "{}")


def create_app(config: AppConfig):
    def application(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        query = parse_qs(environ.get("QUERY_STRING", ""))
        request_id = environ.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        started_at = perf_counter()

        try:
            if method == "GET" and path == "/health":
                payload = {**healthcheck(), "request_id": request_id}
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path == "/literature/search":
                payload = {
                    "rows": search_articles(
                        config.db_path,
                        query=query.get("query", [""])[0],
                        limit=int(query.get("limit", ["10"])[0]),
                        publication_types=query.get("type"),
                        source_name=query.get("source", [None])[0],
                        open_access_only=query.get("open_access_only", ["false"])[0].lower() == "true",
                        year_from=int(query["year_from"][0]) if "year_from" in query else None,
                        year_to=int(query["year_to"][0]) if "year_to" in query else None,
                    )
                }
                payload["request_id"] = request_id
                append_audit_event(
                    config.audit_log_path,
                    {"event": "literature_search", "path": path, "params": query},
                )
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "query": query,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path == "/literature/summary":
                payload = {**get_ingest_summary(config.db_path), "request_id": request_id}
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path == "/guidelines":
                payload = {"rows": list_guidelines(config.db_path), "request_id": request_id}
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path == "/guidelines/recommendations":
                payload = {
                    "rows": list_guideline_recommendations(
                        config.db_path,
                        clinical_domain=query.get("clinical_domain", [None])[0],
                        modality=query.get("modality", [None])[0],
                        limit=int(query.get("limit", ["25"])[0]),
                    ),
                    "request_id": request_id,
                }
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "query": query,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path == "/cases":
                payload = {
                    "rows": list_cases(config.db_path, patient_id=query.get("patient_id", [None])[0]),
                    "request_id": request_id,
                }
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "query": query,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path == "/cases":
                case = _read_json(environ)
                payload = create_case(config.db_path, case)
                payload["request_id"] = request_id
                append_audit_event(
                    config.audit_log_path,
                    {"event": "case_create", "path": path, "patient_id": case.get("patient_id")},
                )
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "patient_id": case.get("patient_id"),
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path.startswith("/cases/") and path.endswith("/reviews"):
                case_key = path.split("/")[2]
                payload = {"rows": list_case_reviews(config.db_path, case_key), "request_id": request_id}
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "case_key": case_key,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path.startswith("/cases/") and path.endswith("/reviews"):
                case_key = path.split("/")[2]
                data = _read_json(environ)
                payload = add_case_review(
                    config.db_path,
                    case_key,
                    reviewer_id=data["reviewer_id"],
                    review_type=data["review_type"],
                    review_status=data["review_status"],
                    note=data.get("note", ""),
                    payload=data.get("payload"),
                )
                append_audit_event(
                    config.audit_log_path,
                    {"event": "case_review_add", "path": path, "case_key": case_key},
                )
                payload["request_id"] = request_id
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "case_key": case_key,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path.startswith("/cases/"):
                case_key = path.split("/")[2]
                payload = get_case_by_key(config.db_path, case_key)
                if payload is None:
                    return _json_response(start_response, "404 Not Found", {"error": "case_not_found", "case_key": case_key, "request_id": request_id})
                payload["request_id"] = request_id
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "case_key": case_key,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path == "/assessment/evaluate":
                case = _read_json(environ)
                payload = evaluate_case(case).to_dict()
                payload["request_id"] = request_id
                append_audit_event(
                    config.audit_log_path,
                    {"event": "assessment_evaluate", "path": path, "patient_id": case.get("patient_id")},
                )
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "patient_id": case.get("patient_id"),
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path == "/recommendations/support-plan":
                data = _read_json(environ)
                case = data.get("case")
                case_evaluation = evaluate_case(case).to_dict() if case else None
                payload = build_support_plan(
                    config.db_path,
                    domains=data.get("domains"),
                    case_context=case,
                    case_evaluation=case_evaluation,
                )
                if data.get("case_key"):
                    for domain in data.get("domains", []):
                        record_case_recommendation(
                            config.db_path,
                            data["case_key"],
                            recommendation_domain=domain,
                            payload=payload,
                        )
                append_audit_event(
                    config.audit_log_path,
                    {"event": "support_plan", "path": path, "domains": data.get("domains", [])},
                )
                payload["request_id"] = request_id
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "domains": data.get("domains", []),
                        "case_key": data.get("case_key"),
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            response = _json_response(
                start_response,
                "404 Not Found",
                {"error": "not_found", "path": path, "request_id": request_id},
            )
            append_request_event(
                config.request_log_path,
                {
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status": 404,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            return response
        except Exception as exc:
            error_id = str(uuid.uuid4())
            append_request_event(
                config.request_log_path,
                {
                    "request_id": request_id,
                    "error_id": error_id,
                    "method": method,
                    "path": path,
                    "status": 500,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            return _json_response(
                start_response,
                "500 Internal Server Error",
                {"error": "internal_error", "message": str(exc), "request_id": request_id, "error_id": error_id},
            )

    return application
