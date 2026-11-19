"""운영은 메인 로그인만 사용하며 API·강사 권한·CSRF·Secure 쿠키는 유지합니다."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from instructor.hosting import create_hosted_app
from reference.tests import test_classifier as fixtures

ENVIRONMENT = {'SECRET_KEY': 'hosted-auth-test-secret-' * 3,
               'RENDER_EXTERNAL_HOSTNAME': 'classroom.example.invalid'}


class HostedAuthTests(unittest.TestCase):
    def test_intro_never_requires_basic_credentials(self):
        for legacy in ({}, {'OML_ACCESS_USER': '', 'OML_ACCESS_PASSWORD': 'short'}):
            with self.subTest(legacy=bool(legacy)), TestClient(
                    create_hosted_app({**ENVIRONMENT, **legacy}),
                    base_url='https://classroom.example.invalid') as client:
                for path in ('/', '/?login=1', '/healthz', '/static/css/style.css'):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200, path)
                    self.assertNotIn('www-authenticate', response.headers)
                response = client.get('/', headers={'Authorization': 'Basic invalid-old-browser-value'})
                self.assertEqual(response.status_code, 200)

    def test_main_login_logout_and_api_guards(self):
        fixture = fixtures.ClassifierTests()
        with (fixture.login_project() as (_, env, people),
              patch('app.connection') as connect,
              patch('app.service.status', return_value={})):
            connect.return_value.__enter__.return_value.username = people[0]['db_user']
            with TestClient(create_hosted_app(ENVIRONMENT),
                            base_url='https://classroom.example.invalid') as client:
                for path in ('/api/status', '/api/assignments/mission/selection',
                             '/download/assignment-guide.html', '/instructor/python-web-lecture.html'):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 401, path)
                    self.assertNotIn('www-authenticate', response.headers)
                self.assertEqual(client.post('/api/initialize', json={}).status_code, 403)
                connect.assert_not_called()
                login = fixture.login(client, people[0])
                self.assertEqual(login.status_code, 200, login.text)
                cookie = login.headers['set-cookie'].lower()
                for flag in ('secure', 'httponly', 'samesite=strict'):
                    self.assertIn(flag, cookie)
                self.assertEqual(client.get('/api/session').json()['identity']['student_id'],
                                 people[0]['student_id'])
                self.assertEqual(client.get('/api/status').status_code, 200)
                self.assertEqual(client.get('/instructor/python-web-lecture.html').status_code, 200)
                response = client.post('/api/logout', json={},
                                       headers={'X-CSRF-Token': login.json()['csrf']})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(client.get('/api/status').status_code, 401)

    def test_student_cannot_open_instructor_lecture(self):
        fixture = fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch('app.connection'):
            with TestClient(create_hosted_app(ENVIRONMENT),
                            base_url='https://classroom.example.invalid') as client:
                self.assertEqual(fixture.login(client, people[1]).status_code, 200)
                self.assertEqual(client.get('/instructor/python-web-lecture.html').status_code, 403)

    def test_secret_and_hostname_restrictions_remain(self):
        for secret in ('', 'short'):
            with self.subTest(secret_length=len(secret)), self.assertRaises(ValueError):
                create_hosted_app({**ENVIRONMENT, 'SECRET_KEY': secret})
        with self.assertRaises(ValueError):
            create_hosted_app({**ENVIRONMENT, 'OML_ALLOWED_HOSTS': '*.example.invalid'})
        with TestClient(create_hosted_app(ENVIRONMENT),
                        base_url='https://untrusted.example.invalid') as client:
            self.assertEqual(client.get('/').status_code, 400)
