"""메인/접속 증빙 API: 로그인 경계·실제 메타데이터·비밀값 제외."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from app import create_app
from backend import connection_profile
from reference.tests import test_classifier as login_fixtures

META={'session_user':'STUDENT23','current_schema':'STUDENT23','database_name':'QA_DB',
      'service_name':'QA_SERVICE','server_host':'QA_HOST','instance_name':'QA_INSTANCE'}

class MainConnectionTests(unittest.TestCase):
    def test_main_is_independent_from_basic_and_login_is_in_content(self):
        client=TestClient(create_app({'SECRET_KEY':'main-template-test'}))
        main=client.get('/')
        self.assertEqual(main.status_code,200)
        self.assertIn('data-page="main"',main.text)
        self.assertIn('id="main-account"',main.text)
        self.assertIn('id="identity-form"',main.text)
        self.assertNotIn('id="identity-dialog"',main.text)
        self.assertNotIn('id="basic-workflow"',main.text)
        self.assertEqual(main.headers['cache-control'],'no-store')
        self.assertIn('id="basic-workflow"',client.get('/basic').text)

    def test_metadata_owner_validation_and_only_allowlisted_connection_fields(self):
        conn=MagicMock()
        cfg={'DB_USER':'STUDENT23','DB_DSN':'(DESCRIPTION=SecretDSN)','DB_PASSWORD':'SecretPassword','WALLET_PASSWORD':'SecretWallet'}
        with patch.object(connection_profile,'query',side_effect=[[dict(META,private='Hidden')],[{'privilege':'CREATE TABLE'}]]):
            report=connection_profile.inspect_connection(conn,cfg)
        conn.ping.assert_called_once()
        self.assertEqual(report['session_user'],'STUDENT23')
        self.assertEqual(report['connection_alias'],'Oracle 접속 기술자')
        self.assertGreaterEqual(report['elapsed_ms'],0)
        for secret in ('SecretDSN','SecretPassword','SecretWallet','Hidden'):self.assertNotIn(secret,str(report))
        for change in ({'current_schema':'SYS'},{'session_user':'OTHER'}):
            with patch.object(connection_profile,'query',return_value=[dict(META,**change)]) as query:
                with self.assertRaisesRegex(ValueError,'발급 DB 계정'):connection_profile.inspect_connection(conn,cfg)
                query.assert_called_once()

    def test_profile_auth_readonly_errors_and_logout_relogin(self):
        fixture=login_fixtures.ClassifierTests()
        with fixture.login_project() as (_,env,people),patch('app.connection') as connect,patch('app.service.status') as basic:
            conn=connect.return_value.__enter__.return_value
            conn.username='STUDENT23'
            client=TestClient(create_app({'SECRET_KEY':'main-profile-test'}))
            self.assertEqual(client.get('/api/account/connection').status_code,401)
            connect.assert_not_called()
            login=fixture.login(client,people[0])
            self.assertEqual(login.status_code,200)
            self.assertIsInstance(login.json()['session']['logged_at'],(float,int))
            with patch.object(connection_profile,'query',side_effect=[[META],[{'privilege':'CREATE TABLE'}]]):
                result=client.get('/api/account/connection')
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json()['identity']['student_id'],people[0]['student_id'])
            self.assertEqual(result.json()['connection']['connection_alias'],'keep_dsn')
            basic.assert_not_called();conn.commit.assert_not_called()
            self.assertNotIn('StudentPassword',result.text)
            connect.side_effect=RuntimeError('ORA-12541 SecretPassword private-endpoint')
            failure=client.get('/api/account/connection')
            self.assertEqual(failure.status_code,503)
            self.assertNotIn('connection',failure.json())
            self.assertNotIn('SecretPassword',failure.text)
            connect.side_effect=None
            client.post('/api/logout',json={},headers={'X-CSRF-Token':login.json()['csrf']})
            self.assertEqual(client.get('/api/account/connection').status_code,401)
            self.assertEqual(fixture.login(client,people[0]).status_code,200)

if __name__=='__main__':unittest.main()
