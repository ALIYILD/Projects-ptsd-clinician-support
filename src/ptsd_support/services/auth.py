from __future__ import annotations

import hashlib
import secrets
from pathlib import Path
from typing import Any

from ptsd_support.db.adapter import fetch_scalar, insert_and_get_id
from ptsd_support.db.schema import connect, initialize_database


VALID_ROLES = {"viewer", "clinician", "admin"}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        raise LookupError("Expected database row")
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _token_prefix(token: str) -> str:
    return token[:8]


def create_user(
    db_path: str | Path,
    *,
    user_key: str,
    display_name: str,
    role: str,
    is_active: bool = True,
) -> dict[str, Any]:
    if role not in VALID_ROLES:
        raise ValueError(f"Unsupported role: {role}")
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO organizations(org_key, name, is_active)
            VALUES (?, ?, ?)
            ON CONFLICT(org_key) DO NOTHING
            """,
            ("default-org", "Default Organization", 1),
        )
        conn.execute(
            """
            INSERT INTO users(user_key, display_name, role, is_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_key) DO UPDATE SET
                display_name = excluded.display_name,
                role = excluded.role,
                is_active = excluded.is_active
            """,
            (user_key, display_name, role, 1 if is_active else 0),
        )
        user_id = fetch_scalar(conn, "SELECT id FROM users WHERE user_key = ?", (user_key,))
        organization_id = fetch_scalar(conn, "SELECT id FROM organizations WHERE org_key = ?", ("default-org",))
        conn.execute(
            """
            INSERT INTO user_organization_memberships(user_id, organization_id, membership_role, is_default)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, organization_id) DO UPDATE SET
                membership_role = excluded.membership_role
            """,
            (user_id, organization_id, role, 1),
        )
        row = conn.execute(
            "SELECT user_key, display_name, role, is_active, created_at FROM users WHERE user_key = ?",
            (user_key,),
        ).fetchone()
        conn.commit()
        return _row_to_dict(row)
    finally:
        conn.close()


def create_organization(
    db_path: str | Path,
    *,
    org_key: str,
    name: str,
    is_active: bool = True,
) -> dict[str, Any]:
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO organizations(org_key, name, is_active)
            VALUES (?, ?, ?)
            ON CONFLICT(org_key) DO UPDATE SET
                name = excluded.name,
                is_active = excluded.is_active
            """,
            (org_key, name, 1 if is_active else 0),
        )
        row = conn.execute(
            "SELECT org_key, name, is_active, created_at FROM organizations WHERE org_key = ?",
            (org_key,),
        ).fetchone()
        conn.commit()
        return _row_to_dict(row)
    finally:
        conn.close()


def add_user_membership(
    db_path: str | Path,
    *,
    user_key: str,
    org_key: str,
    membership_role: str = "member",
    is_default: bool = False,
) -> dict[str, Any]:
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        user_id = fetch_scalar(conn, "SELECT id FROM users WHERE user_key = ?", (user_key,))
        organization_id = fetch_scalar(conn, "SELECT id FROM organizations WHERE org_key = ?", (org_key,))
        if user_id is None:
            raise ValueError(f"Unknown user_key: {user_key}")
        if organization_id is None:
            raise ValueError(f"Unknown org_key: {org_key}")
        if is_default:
            conn.execute(
                "UPDATE user_organization_memberships SET is_default = 0 WHERE user_id = ?",
                (user_id,),
            )
        conn.execute(
            """
            INSERT INTO user_organization_memberships(user_id, organization_id, membership_role, is_default)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, organization_id) DO UPDATE SET
                membership_role = excluded.membership_role,
                is_default = excluded.is_default
            """,
            (user_id, organization_id, membership_role, 1 if is_default else 0),
        )
        row = conn.execute(
            """
            SELECT u.user_key, o.org_key, o.name, m.membership_role, m.is_default
            FROM user_organization_memberships m
            JOIN users u ON u.id = m.user_id
            JOIN organizations o ON o.id = m.organization_id
            WHERE u.user_key = ? AND o.org_key = ?
            """,
            (user_key, org_key),
        ).fetchone()
        conn.commit()
        return _row_to_dict(row)
    finally:
        conn.close()


def create_api_token(
    db_path: str | Path,
    *,
    user_key: str,
    label: str | None = None,
) -> dict[str, Any]:
    initialize_database(db_path)
    token = f"ptsd_{secrets.token_urlsafe(24)}"
    conn = connect(db_path)
    try:
        user_id = fetch_scalar(conn, "SELECT id FROM users WHERE user_key = ?", (user_key,))
        if user_id is None:
            raise ValueError(f"Unknown user_key: {user_key}")
        insert_and_get_id(
            conn,
            """
            INSERT INTO api_tokens(user_id, token_hash, token_prefix, label)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, _hash_token(token), _token_prefix(token), label),
        )
        row = conn.execute(
            """
            SELECT u.user_key, u.display_name, u.role, t.label, t.token_prefix, t.created_at
            FROM api_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = ?
            """,
            (_hash_token(token),),
        ).fetchone()
        conn.commit()
        payload = _row_to_dict(row)
        payload["token"] = token
        return payload
    finally:
        conn.close()


def list_api_tokens(
    db_path: str | Path,
    *,
    user_key: str | None = None,
) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        if user_key:
            rows = conn.execute(
                """
                SELECT u.user_key, u.display_name, u.role, t.label, t.token_prefix,
                       t.created_at, t.last_used_at, t.revoked_at
                FROM api_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE u.user_key = ?
                ORDER BY t.created_at DESC, t.id DESC
                """,
                (user_key,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT u.user_key, u.display_name, u.role, t.label, t.token_prefix,
                       t.created_at, t.last_used_at, t.revoked_at
                FROM api_tokens t
                JOIN users u ON u.id = t.user_id
                ORDER BY t.created_at DESC, t.id DESC
                """
            ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def revoke_api_token(
    db_path: str | Path,
    *,
    token_prefix: str,
    user_key: str | None = None,
) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        if user_key:
            row = conn.execute(
                """
                SELECT t.id, u.user_key, t.token_prefix, t.label, t.created_at, t.last_used_at, t.revoked_at
                FROM api_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_prefix = ? AND u.user_key = ?
                ORDER BY t.created_at DESC, t.id DESC
                LIMIT 1
                """,
                (token_prefix, user_key),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT t.id, u.user_key, t.token_prefix, t.label, t.created_at, t.last_used_at, t.revoked_at
                FROM api_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_prefix = ?
                ORDER BY t.created_at DESC, t.id DESC
                LIMIT 1
                """,
                (token_prefix,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Unknown token_prefix: {token_prefix}")
        token_row = _row_to_dict(row)
        conn.execute(
            "UPDATE api_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE id = ?",
            (token_row["id"],),
        )
        updated = conn.execute(
            """
            SELECT u.user_key, t.token_prefix, t.label, t.created_at, t.last_used_at, t.revoked_at
            FROM api_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.id = ?
            """,
            (token_row["id"],),
        ).fetchone()
        conn.commit()
        return _row_to_dict(updated)
    finally:
        conn.close()


def authenticate_token(db_path: str | Path, token: str) -> dict[str, Any] | None:
    token = token.strip()
    if not token:
        return None
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT
                u.user_key,
                u.display_name,
                u.role,
                u.is_active,
                t.label,
                t.token_prefix,
                t.created_at,
                t.last_used_at,
                t.revoked_at
            FROM api_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = ?
            """,
            (_hash_token(token),),
        ).fetchone()
        if row is None:
            return None
        payload = _row_to_dict(row)
        if payload["revoked_at"] or not payload["is_active"]:
            return None
        memberships = conn.execute(
            """
            SELECT o.org_key, o.name, m.membership_role, m.is_default
            FROM user_organization_memberships m
            JOIN organizations o ON o.id = m.organization_id
            JOIN users u ON u.id = m.user_id
            WHERE u.user_key = ? AND o.is_active = 1
            ORDER BY m.is_default DESC, o.org_key
            """,
            (payload["user_key"],),
        ).fetchall()
        payload["organizations"] = [_row_to_dict(row) for row in memberships]
        payload["default_org_key"] = next(
            (org["org_key"] for org in payload["organizations"] if org["is_default"]),
            payload["organizations"][0]["org_key"] if payload["organizations"] else None,
        )
        conn.execute(
            "UPDATE api_tokens SET last_used_at = CURRENT_TIMESTAMP WHERE token_hash = ?",
            (_hash_token(token),),
        )
        conn.commit()
        return payload
    finally:
        conn.close()


def list_users(db_path: str | Path) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT user_key, display_name, role, is_active, created_at
            FROM users
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def actor_org_keys(actor: dict[str, Any]) -> set[str]:
    organizations = actor.get("organizations") or []
    return {org["org_key"] for org in organizations if org.get("org_key")}


def role_allows(user_role: str, allowed_roles: set[str]) -> bool:
    if user_role == "admin":
        return True
    return user_role in allowed_roles
