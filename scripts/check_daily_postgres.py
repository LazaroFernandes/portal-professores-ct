"""Run the daily workflow API contract on a dedicated disposable local database.
Requires TEST_DATABASE_URL pointing to 127.0.0.1 and database portal_workflow_test.
"""
import os
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch
import dotenv

dotenv.load_dotenv=lambda *a,**k:False
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src'),str(root/'backend')]
url=os.environ.get('TEST_DATABASE_URL','')
parsed=urlparse(url)
if parsed.hostname!='127.0.0.1' or parsed.path!='/portal_workflow_test':
    raise SystemExit('Use a dedicated local portal_workflow_test database.')
os.environ['DATABASE_URL']=url
from backend.tests.test_daily_workflow import DailyWorkflowTests
from backend.app.services import presence_service as presence, daily_workflow as daily
original=presence.PresenceStore
store=original()
with patch.object(presence,'_store',return_value=store):daily.store()

class PostgresDailyWorkflowTests(DailyWorkflowTests):
    def setUp(self):
        with store._connect() as c:
            c.execute('TRUNCATE portal_daily_audit, portal_followup_actions, portal_daily_details, portal_daily_attendance_records, portal_gym_visits RESTART IDENTITY CASCADE')
        with patch.object(presence,'PresenceStore',side_effect=lambda *a,**k:original()):
            super().setUp()

result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(PostgresDailyWorkflowTests))
raise SystemExit(0 if result.wasSuccessful() else 1)
