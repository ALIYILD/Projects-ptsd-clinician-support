from __future__ import annotations

import json
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from urllib.parse import parse_qs

from ptsd_support.services.auth import (
    actor_org_keys,
    authenticate_token,
    create_api_token,
    list_api_tokens,
    revoke_api_token,
    role_allows,
)
from ptsd_support.services.assessment import evaluate_case
from ptsd_support.services.audit import append_audit_event, append_request_event
from ptsd_support.services.care_plans import generate_care_plan, list_care_plans, save_care_plan
from ptsd_support.services.cases import (
    add_case_review,
    create_case,
    get_case_by_key,
    list_case_reviews,
    list_cases,
    record_case_recommendation,
)
from ptsd_support.services.differential import build_differential_diagnosis
from ptsd_support.services.guidelines import list_guideline_recommendations, list_guidelines
from ptsd_support.services.jobs import enqueue_job, get_job, list_jobs, retry_job
from ptsd_support.services.notes import draft_clinician_note, list_note_drafts, save_note_draft
from ptsd_support.services.recommendations import build_support_plan
from ptsd_support.services.retrieval import get_ingest_summary, search_articles


def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "ptsd-clinician-support"}


@dataclass
class AppConfig:
    db_path: Path
    audit_log_path: Path
    request_log_path: Path
    queue_dir: Path | None = None
    require_auth: bool = False


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


def _extract_bearer_token(environ) -> str | None:
    authorization = environ.get("HTTP_AUTHORIZATION", "")
    if authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()
    api_key = environ.get("HTTP_X_API_KEY", "").strip()
    return api_key or None


def _auth_error(start_response, status: str, error: str, request_id: str) -> list[bytes]:
    return _json_response(start_response, status, {"error": error, "request_id": request_id})


def _require_actor(config: AppConfig, environ, start_response, request_id: str, allowed_roles: set[str]):
    if not config.require_auth:
        return {"user_key": "local-dev", "role": "admin", "display_name": "Local Dev"}, None
    token = _extract_bearer_token(environ)
    if not token:
        return None, ("401 Unauthorized", "authentication_required")
    actor = authenticate_token(config.db_path, token)
    if actor is None:
        return None, ("401 Unauthorized", "invalid_api_token")
    if not role_allows(actor["role"], allowed_roles):
        return None, ("403 Forbidden", "insufficient_role")
    return actor, None


def _allowed_roles(method: str, path: str) -> set[str] | None:
    if method == "GET" and path == "/health":
        return None
    if method == "GET" and path in {"/literature/search", "/literature/summary", "/guidelines", "/guidelines/recommendations", "/auth/me", "/auth/tokens"}:
        return {"viewer", "clinician", "admin"}
    if method == "POST" and path == "/auth/tokens":
        return {"viewer", "clinician", "admin"}
    if method == "POST" and path == "/auth/tokens/revoke":
        return {"viewer", "clinician", "admin"}
    if path == "/jobs":
        return {"admin"}
    if path.startswith("/jobs/"):
        return {"admin"}
    return {"clinician", "admin"}


def _case_scope(actor: dict | None) -> set[str] | None:
    if actor is None or actor.get("role") == "admin":
        return None
    return actor_org_keys(actor)


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

            actor = None
            allowed_roles = _allowed_roles(method, path)
            if allowed_roles is not None:
                actor, auth_error = _require_actor(config, environ, start_response, request_id, allowed_roles)
                if auth_error is not None:
                    response = _auth_error(start_response, auth_error[0], auth_error[1], request_id)
                    append_request_event(
                        config.request_log_path,
                        {
                            "request_id": request_id,
                            "method": method,
                            "path": path,
                            "status": 401 if auth_error[0].startswith("401") else 403,
                            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                        },
                    )
                    return response

            if method == "GET" and path == "/auth/me":
                payload = {"actor": actor, "request_id": request_id}
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "actor": actor["user_key"] if actor else None,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path == "/auth/tokens":
                requested_user_key = query.get("user_key", [None])[0]
                if actor and actor["role"] != "admin":
                    requested_user_key = actor["user_key"]
                payload = {
                    "rows": list_api_tokens(config.db_path, user_key=requested_user_key),
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
                        "actor": actor["user_key"] if actor else None,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path == "/auth/tokens":
                data = _read_json(environ)
                target_user_key = data.get("user_key") or (actor["user_key"] if actor else None)
                if actor and actor["role"] != "admin":
                    target_user_key = actor["user_key"]
                payload = create_api_token(
                    config.db_path,
                    user_key=target_user_key,
                    label=data.get("label"),
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
                        "actor": actor["user_key"] if actor else None,
                        "target_user_key": target_user_key,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path == "/auth/tokens/revoke":
                data = _read_json(environ)
                target_user_key = data.get("user_key")
                if actor and actor["role"] != "admin":
                    target_user_key = actor["user_key"]
                payload = revoke_api_token(
                    config.db_path,
                    token_prefix=data["token_prefix"],
                    user_key=target_user_key,
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
                        "actor": actor["user_key"] if actor else None,
                        "token_prefix": data["token_prefix"],
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
                        "actor": actor["user_key"] if actor else None,
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
                        "actor": actor["user_key"] if actor else None,
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
                        "actor": actor["user_key"] if actor else None,
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
                        "actor": actor["user_key"] if actor else None,
                        "query": query,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path == "/jobs":
                payload = {
                    "rows": list_jobs(
                        config.db_path,
                        status=query.get("status", [None])[0],
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
                        "actor": actor["user_key"] if actor else None,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path.startswith("/jobs/") and path.endswith("/retry"):
                job_id = path.split("/")[2]
                payload = retry_job(
                    config.queue_dir or config.db_path.parent / "jobs",
                    config.db_path,
                    job_id,
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
                        "actor": actor["user_key"] if actor else None,
                        "job_id": job_id,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path == "/jobs":
                data = _read_json(environ)
                payload = dict(data.get("payload") or {})
                payload.setdefault("db_path", str(config.db_path))
                job = enqueue_job(
                    config.queue_dir or config.db_path.parent / "jobs",
                    data["job_type"],
                    payload,
                    requested_by=actor["user_key"] if actor else None,
                )
                job["request_id"] = request_id
                append_audit_event(
                    config.audit_log_path,
                    {
                        "event": "job_enqueue",
                        "path": path,
                        "job_type": data["job_type"],
                        "requested_by": actor["user_key"] if actor else None,
                    },
                )
                response = _json_response(start_response, "200 OK", job)
                append_request_event(
                    config.request_log_path,
                    {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status": 200,
                        "actor": actor["user_key"] if actor else None,
                        "job_type": data["job_type"],
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path.startswith("/jobs/"):
                job_id = path.split("/")[2]
                payload = get_job(config.db_path, job_id)
                if payload is None:
                    return _json_response(
                        start_response,
                        "404 Not Found",
                        {"error": "job_not_found", "job_id": job_id, "request_id": request_id},
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
                        "actor": actor["user_key"] if actor else None,
                        "job_id": job_id,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path == "/cases":
                payload = {
                    "rows": list_cases(
                        config.db_path,
                        patient_id=query.get("patient_id", [None])[0],
                        organization_keys=_case_scope(actor),
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
                        "actor": actor["user_key"] if actor else None,
                        "query": query,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "POST" and path == "/cases":
                case = _read_json(environ)
                case.setdefault("organization_key", actor.get("default_org_key") if actor else "default-org")
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
                payload = {
                    "rows": list_case_reviews(
                        config.db_path,
                        case_key,
                        organization_keys=_case_scope(actor),
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
                        "case_key": case_key,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    },
                )
                return response

            if method == "GET" and path.startswith("/cases/") and path.endswith("/care-plans"):
                case_key = path.split("/")[2]
                payload = {
                    "rows": list_care_plans(
                        config.db_path,
                        case_key=case_key,
                        organization_keys=_case_scope(actor),
                    ),
                    "request_id": request_id,
                }
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {"request_id": request_id, "method": method, "path": path, "status": 200, "case_key": case_key, "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
                )
                return response

            if method == "GET" and path.startswith("/cases/") and path.endswith("/notes"):
                case_key = path.split("/")[2]
                payload = {
                    "rows": list_note_drafts(
                        config.db_path,
                        case_key=case_key,
                        organization_keys=_case_scope(actor),
                    ),
                    "request_id": request_id,
                }
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {"request_id": request_id, "method": method, "path": path, "status": 200, "case_key": case_key, "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
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
                    organization_keys=_case_scope(actor),
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

            if method == "POST" and path.startswith("/cases/") and path.endswith("/care-plans"):
                case_key = path.split("/")[2]
                data = _read_json(environ)
                payload = save_care_plan(
                    config.db_path,
                    case_key=case_key,
                    plan_type=data.get("plan_type", "home_tasks"),
                    payload=data["payload"],
                    created_by=data.get("created_by"),
                    organization_keys=_case_scope(actor),
                )
                payload["request_id"] = request_id
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {"request_id": request_id, "method": method, "path": path, "status": 200, "case_key": case_key, "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
                )
                return response

            if method == "POST" and path.startswith("/cases/") and path.endswith("/notes"):
                case_key = path.split("/")[2]
                data = _read_json(environ)
                payload = save_note_draft(
                    config.db_path,
                    case_key=case_key,
                    note_type=data.get("note_type", "assessment"),
                    payload=data["payload"],
                    created_by=data.get("created_by"),
                    organization_keys=_case_scope(actor),
                )
                payload["request_id"] = request_id
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {"request_id": request_id, "method": method, "path": path, "status": 200, "case_key": case_key, "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
                )
                return response

            if method == "GET" and path.startswith("/cases/"):
                case_key = path.split("/")[2]
                payload = get_case_by_key(
                    config.db_path,
                    case_key,
                    organization_keys=_case_scope(actor),
                )
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

            if method == "POST" and path == "/decision-support/differential":
                data = _read_json(environ)
                case = data.get("case", {})
                payload = build_differential_diagnosis(case)
                payload["request_id"] = request_id
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {"request_id": request_id, "method": method, "path": path, "status": 200, "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
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
                            organization_keys=_case_scope(actor),
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

            if method == "POST" and path == "/care-plans/generate":
                data = _read_json(environ)
                case = data.get("case", {})
                case_evaluation = data.get("case_evaluation") or evaluate_case(case).to_dict()
                support_plan = data.get("support_plan") or build_support_plan(
                    config.db_path,
                    domains=data.get("domains"),
                    case_context=case,
                    case_evaluation=case_evaluation,
                )
                payload = generate_care_plan(case, case_evaluation, support_plan)
                if data.get("case_key"):
                    saved = save_care_plan(
                        config.db_path,
                        case_key=data["case_key"],
                        plan_type=data.get("plan_type", "home_tasks"),
                        payload=payload,
                        created_by=data.get("created_by"),
                        organization_keys=_case_scope(actor),
                    )
                    payload["saved"] = saved
                payload["request_id"] = request_id
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {"request_id": request_id, "method": method, "path": path, "status": 200, "case_key": data.get("case_key"), "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
                )
                return response

            if method == "POST" and path == "/notes/draft":
                data = _read_json(environ)
                case = data.get("case", {})
                case_evaluation = data.get("case_evaluation") or evaluate_case(case).to_dict()
                support_plan = data.get("support_plan")
                differential = data.get("differential")
                care_plan = data.get("care_plan")
                payload = draft_clinician_note(
                    case=case,
                    case_evaluation=case_evaluation,
                    support_plan=support_plan,
                    differential=differential,
                    care_plan=care_plan,
                    note_type=data.get("note_type", "assessment"),
                )
                if data.get("case_key"):
                    saved = save_note_draft(
                        config.db_path,
                        case_key=data["case_key"],
                        note_type=data.get("note_type", "assessment"),
                        payload=payload,
                        created_by=data.get("created_by"),
                        organization_keys=_case_scope(actor),
                    )
                    payload["saved"] = saved
                payload["request_id"] = request_id
                response = _json_response(start_response, "200 OK", payload)
                append_request_event(
                    config.request_log_path,
                    {"request_id": request_id, "method": method, "path": path, "status": 200, "case_key": data.get("case_key"), "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
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
