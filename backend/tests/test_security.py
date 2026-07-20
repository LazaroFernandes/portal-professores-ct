from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.core.security import create_session, hash_password, read_session, verify_password


class SecurityTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_scrypt_hash_accepts_only_correct_password(self) -> None:
        encoded = hash_password("senha forte")
        self.assertTrue(verify_password("senha forte", encoded))
        self.assertFalse(verify_password("outra", encoded))

    def test_signed_session_rejects_tampering(self) -> None:
        with patch.dict(os.environ, {"SESSION_SECRET": "test-secret"}, clear=False):
            get_settings.cache_clear()
            token, csrf = create_session({"role": "professor", "name": "Ana"})
            self.assertEqual(read_session(token)["csrf"], csrf)
            self.assertIsNone(read_session(token + "x"))

    def test_health_check(self) -> None:
        with patch.dict(os.environ, {"SESSION_SECRET": "test-secret"}, clear=False):
            get_settings.cache_clear()
            from backend.app.main import app

            response = TestClient(app).get("/api/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")

    def test_login_sets_http_only_session_and_csrf_protects_logout(self) -> None:
        with patch.dict(
            os.environ,
            {"SESSION_SECRET": "test-secret", "APP_PASSWORD": "admin-test"},
            clear=False,
        ):
            get_settings.cache_clear()
            from backend.app.main import app

            client = TestClient(app)
            response = client.post("/api/auth/login", json={"password": "admin-test"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("httponly", response.headers["set-cookie"].lower())
            self.assertEqual(client.post("/api/auth/logout").status_code, 403)
            csrf = response.json()["csrf_token"]
            self.assertEqual(
                client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code,
                204,
            )


if __name__ == "__main__":
    unittest.main()
