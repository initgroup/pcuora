"""세션 유휴 30분·쿠키 충돌·명시적 재시작 경계를 실제 Oracle 없이 검사합니다."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
import app as application
from backend import basic_dataset, mission_guide
from reference.tests import test_classifier as login_fixtures

class SessionRuntimeTests(unittest.TestCase):
    def test_foreign_generic_cookie_cannot_replace_oml_login(self):
        fixture = login_fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch("app.connection"):
            client = TestClient(application.create_app({"SECRET_KEY": "session-cookie-qa"}))
            response = fixture.login(client, people[0])
            self.assertEqual(response.status_code, 200)
            owned = [c for c in client.cookies.jar if c.name != "session"]
            self.assertEqual(len(owned), 1, "OML must not use another localhost app's generic session cookie")
            self.assertIn("httponly", response.headers["set-cookie"].lower())
            self.assertIn("samesite=strict", response.headers["set-cookie"].lower())
            client.cookies.set("session", "unrelated-local-application")
            result = client.get("/api/session")
            self.assertEqual(result.json()["identity"]["db_user"], people[0]["db_user"])
            self.assertEqual(client.cookies.get("session"), "unrelated-local-application")
            self.assertNotIn("set-cookie", result.headers, "An unchanged session must not overwrite a concurrent login")

    def test_all_menu_links_keep_login_until_exact_idle_boundary(self):
        fixture = login_fixtures.ClassifierTests()
        now = [10000.0]
        with fixture.login_project() as (_, env, people), patch("app.connection"):
            client = TestClient(application.create_app({"SECRET_KEY": "menu-timeout-qa", "SESSION_CLOCK": lambda: now[0]}))
            response = fixture.login(client, people[0])
            self.assertEqual(response.json()["session"]["timeout_seconds"], 1800)
            for delta in (60, 300, 600, 900, 1200, 1799):
                now[0] = 10000 + delta
                for route in ("/", "/basic", "/data", "/models", "/predictions", "/mission", "/creative"):
                    self.assertEqual(client.get(route).status_code, 200, route)
                    status = client.get("/api/session").json()
                    self.assertEqual(status["identity"]["db_user"], people[0]["db_user"], (route, delta))
                    self.assertEqual(status["session"]["expires_at"], 11800, "Passive reads must not keep login alive")
            now[0] = 11800
            expired = client.get("/api/session").json()
            self.assertIsNone(expired["identity"])
            self.assertTrue(expired["session"]["expired"])

    def test_help_schema_and_authenticated_reads_share_1800_second_extension(self):
        fixture = login_fixtures.ClassifierTests()
        now = [10000.0]
        with fixture.login_project() as (_, env, people), patch("app.connection") as connection, patch("app.service.status", return_value={}):
            connection.return_value.__enter__.return_value.username = people[0]["db_user"]
            client = TestClient(application.create_app({"SECRET_KEY": "activity-timeout-qa", "SESSION_CLOCK": lambda: now[0]}))
            fixture.login(client, people[0])
            routes = (
                "/api/status",
                "/api/basic/dataset/schema",
                "/api/assignments/mission/schema?mission=esports&kind=training",
                "/api/assignments/mission/schema?mission=esports&kind=procedure",
                "/api/assignments/mission/guide?mission=esports&operation=setup",
                "/api/assignments/mission/selection",
                "/instructor/python-web-lecture.html",
            )
            for route in routes:
                now[0] += 1700
                result = client.get(route)
                self.assertEqual(result.status_code, 200, (route, result.text[:160]))
                self.assertEqual(float(result.headers["X-Session-Expires-At"]), now[0] + 1800, route)
                self.assertEqual(client.get("/api/session").json()["session"]["expires_at"], now[0] + 1800)
            now[0] += 1800
            result = client.get("/api/status")
            self.assertEqual(result.status_code, 401)
            self.assertEqual(result.json()["code"], "SESSION_TIMEOUT")

    def test_pool_cleanup_or_db_error_does_not_log_out_web_session(self):
        fixture = login_fixtures.ClassifierTests()
        now = [10000.0]
        with fixture.login_project() as (_, env, people), patch("app.connection") as connection, patch("app.close_connections") as close:
            client = TestClient(application.create_app({"SECRET_KEY": "pool-session-qa", "SESSION_CLOCK": lambda: now[0]}))
            fixture.login(client, people[0])
            now[0] += 120
            close.reset_mock()
            connection.side_effect = RuntimeError("DPY-4011 connection closed")
            self.assertEqual(client.get("/api/status").status_code, 503)
            self.assertIsNotNone(client.get("/api/session").json()["identity"])
            close.assert_not_called()

    def test_logout_and_explicit_server_restart_still_revoke_old_cookie(self):
        fixture = login_fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch("app.connection"):
            config = {"SECRET_KEY": "explicit-restart-qa"}
            first = TestClient(application.create_app(config))
            login = fixture.login(first, people[0])
            copied = TestClient(application.create_app(config))
            copied.cookies.update(first.cookies)
            self.assertIsNone(copied.get("/api/session").json()["identity"])
            headers = {"X-CSRF-Token": login.json()["csrf"]}
            self.assertEqual(first.post("/api/logout", json={}, headers=headers).status_code, 200)
            self.assertIsNone(first.get("/api/session").json()["identity"])

if __name__ == "__main__":
    unittest.main()
