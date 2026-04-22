from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from ptsd_support.api.app import AppConfig, create_app
from ptsd_support.services.auth import (
    add_user_membership,
    authenticate_token,
    create_api_token,
    create_organization,
    create_user,
    list_api_tokens,
    rotate_api_token,
    revoke_api_token,
)


class AuthTests(unittest.TestCase):
    def test_token_authentication_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "auth.db"
            create_user(
                db_path,
                user_key="clinician-1",
                display_name="Clinician One",
                role="clinician",
            )
            token = create_api_token(db_path, user_key="clinician-1", label="test")
            actor = authenticate_token(db_path, token["token"])
            self.assertIsNotNone(actor)
            self.assertEqual(actor["user_key"], "clinician-1")
            self.assertEqual(actor["role"], "clinician")
            self.assertEqual(actor["default_org_key"], "default-org")
            self.assertTrue(actor["organizations"])

    def test_user_can_have_named_org_membership(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "auth-org.db"
            create_user(
                db_path,
                user_key="clinician-2",
                display_name="Clinician Two",
                role="clinician",
            )
            create_organization(db_path, org_key="clinic-a", name="Clinic A")
            add_user_membership(
                db_path,
                user_key="clinician-2",
                org_key="clinic-a",
                membership_role="clinician",
                is_default=True,
            )
            token = create_api_token(db_path, user_key="clinician-2", label="org")
            actor = authenticate_token(db_path, token["token"])
            self.assertEqual(actor["default_org_key"], "clinic-a")
            self.assertIn("clinic-a", {org["org_key"] for org in actor["organizations"]})

    def test_api_requires_auth_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "auth-api.db"
            create_user(
                db_path,
                user_key="viewer-1",
                display_name="Viewer One",
                role="viewer",
            )
            token = create_api_token(db_path, user_key="viewer-1", label="viewer")
            app = create_app(
                AppConfig(
                    db_path=db_path,
                    audit_log_path=Path(tmpdir) / "audit.jsonl",
                    request_log_path=Path(tmpdir) / "requests.jsonl",
                    queue_dir=Path(tmpdir) / "jobs",
                    require_auth=True,
                )
            )

            def run_request(path: str, auth_token: str | None = None):
                captured = {}

                def start_response(status, headers):
                    captured["status"] = status
                    captured["headers"] = headers

                environ = {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": path,
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "wsgi.input": BytesIO(b""),
                }
                if auth_token:
                    environ["HTTP_AUTHORIZATION"] = f"Bearer {auth_token}"
                body = b"".join(app(environ, start_response))
                return captured["status"], body

            status, _ = run_request("/guidelines")
            self.assertEqual(status, "401 Unauthorized")

            status, body = run_request("/auth/me", token["token"])
            self.assertEqual(status, "200 OK")
            self.assertIn(b"viewer-1", body)

    def test_token_list_and_revoke(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "auth-revoke.db"
            create_user(
                db_path,
                user_key="viewer-2",
                display_name="Viewer Two",
                role="viewer",
            )
            token = create_api_token(db_path, user_key="viewer-2", label="revoke-me")
            listed = list_api_tokens(db_path, user_key="viewer-2")
            self.assertEqual(len(listed), 1)
            revoked = revoke_api_token(db_path, token_prefix=token["token_prefix"], user_key="viewer-2")
            self.assertIsNotNone(revoked["revoked_at"])
            self.assertIsNone(authenticate_token(db_path, token["token"]))

    def test_expired_token_is_rejected_and_rotation_issues_new_token(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "auth-expire.db"
            create_user(
                db_path,
                user_key="viewer-3",
                display_name="Viewer Three",
                role="viewer",
            )
            expired = create_api_token(db_path, user_key="viewer-3", label="expired", ttl_days=-1)
            self.assertIsNone(authenticate_token(db_path, expired["token"]))

            active = create_api_token(db_path, user_key="viewer-3", label="rotate-me")
            rotated = rotate_api_token(db_path, token_prefix=active["token_prefix"], user_key="viewer-3", ttl_days=30)
            self.assertIsNone(authenticate_token(db_path, active["token"]))
            self.assertIsNotNone(authenticate_token(db_path, rotated["new_token"]["token"]))

    def test_admin_request_log_read_endpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "auth-admin-api.db"
            create_user(
                db_path,
                user_key="admin-1",
                display_name="Admin One",
                role="admin",
            )
            token = create_api_token(db_path, user_key="admin-1", label="admin")
            app = create_app(
                AppConfig(
                    db_path=db_path,
                    audit_log_path=Path(tmpdir) / "audit.jsonl",
                    request_log_path=Path(tmpdir) / "requests.jsonl",
                    queue_dir=Path(tmpdir) / "jobs",
                    require_auth=True,
                )
            )

            def run_request(method: str, path: str, body: bytes = b""):
                captured = {}

                def start_response(status, headers):
                    captured["status"] = status
                    captured["headers"] = headers

                environ = {
                    "REQUEST_METHOD": method,
                    "PATH_INFO": path,
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": str(len(body)),
                    "wsgi.input": BytesIO(body),
                    "HTTP_AUTHORIZATION": f"Bearer {token['token']}",
                }
                response = b"".join(app(environ, start_response))
                return captured["status"], response

            status, _ = run_request("GET", "/auth/me")
            self.assertEqual(status, "200 OK")
            status, body = run_request("GET", "/admin/requests")
            self.assertEqual(status, "200 OK")
            self.assertIn(b"/auth/me", body)


if __name__ == "__main__":
    unittest.main()
