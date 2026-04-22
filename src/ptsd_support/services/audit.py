from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SENSITIVE_KEYS = {
    "authorization",
    "http_authorization",
    "x-api-key",
    "http_x_api_key",
    "api_key",
    "token",
    "token_hash",
    "access_token",
    "refresh_token",
    "secret",
    "password",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("_", "-")
            if normalized in SENSITIVE_KEYS or "token" in normalized or "secret" in normalized or "password" in normalized:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def append_jsonl_event(log_path: str | Path, event: dict[str, Any]) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **_redact(event),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def append_audit_event(log_path: str | Path, event: dict[str, Any]) -> None:
    append_jsonl_event(log_path, {"stream": "audit", **event})


def append_request_event(log_path: str | Path, event: dict[str, Any]) -> None:
    append_jsonl_event(log_path, {"stream": "request", **event})


def read_jsonl_events(
    log_path: str | Path,
    *,
    limit: int = 100,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    path = Path(log_path)
    if not path.exists():
        return []
    filters = {key: value for key, value in (filters or {}).items() if value not in (None, "", [])}
    lines = path.read_text(encoding="utf-8").splitlines()
    items = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not _matches_filters(payload, filters):
            continue
        items.append(payload)
        if len(items) >= limit:
            break
    return items


def _matches_filters(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        if key == "contains":
            if str(expected).lower() not in json.dumps(payload, ensure_ascii=True).lower():
                return False
            continue
        actual = payload.get(key)
        if actual is None:
            return False
        if str(actual).lower() != str(expected).lower():
            return False
    return True
