import base64
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from backend.app.services.presence_service import PresenceStore
from backend.app.services.nextfit_session import PersistentNextFitClient
from nextfit_v2_client import NextFitV2Client, TokenExpiredError


def jwt(exp):
    return 'test.' + base64.urlsafe_b64encode(json.dumps({'exp': exp}).encode()).decode().rstrip('=') + '.signature'


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = PresenceStore(Path(self.temp.name)/'state.db')
        self.old = jwt(time.time()-100)
        self.new = jwt(time.time()+36000)

    def client(self):
        return PersistentNextFitClient(self.store,'unit',self.old,'old+refresh&value')

    def response(self, refresh=True):
        return Mock(status_code=200, json=lambda: dict(access_token=self.new, **({'refresh_token':'new-refresh'} if refresh else {})))

    def test_persists_pair_and_new_instance_ignores_old_environment(self):
        with patch('nextfit_v2_client.requests.post',return_value=self.response()) as post:
            self.assertTrue(self.client()._refresh_access_token())
        new=self.client()
        self.assertEqual(new._token,self.new)
        self.assertEqual(new.refresh_token,'new-refresh')
        self.assertEqual(post.call_args.kwargs['data']['refresh_token'],'old+refresh&value')

    def test_two_workers_rotate_once(self):
        clients=[self.client(),self.client()]
        with patch('nextfit_v2_client.requests.post',return_value=self.response()) as post:
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(lambda c:c._refresh_access_token(),clients)),[True,True])
            self.assertEqual(post.call_count,1)
        self.assertTrue(all(c._token==self.new for c in clients))

    def test_preserves_refresh_when_provider_omits_new_one(self):
        with patch('nextfit_v2_client.requests.post',return_value=self.response(False)):
            self.client()._refresh_access_token()
        self.assertEqual(self.client().refresh_token,'old+refresh&value')

    def test_rejected_refresh_preserves_previous_pair_and_has_sanitized_error(self):
        c=self.client()
        with patch('nextfit_v2_client.requests.post',return_value=Mock(status_code=400)):
            with self.assertRaises(TokenExpiredError) as error: c.maintain()
        self.assertNotIn('old+refresh',str(error.exception))
        self.assertIsNone(self.store.state(c.key))
        self.assertEqual(c._token,self.old)

    def test_db_failure_does_not_claim_success_or_adopt_unpersisted_token(self):
        c=self.client(); execute=self.store._execute
        def fail(conn,sql,args=()):
            if sql.startswith('INSERT'): raise RuntimeError('disk unavailable')
            return execute(conn,sql,args)
        with patch('nextfit_v2_client.requests.post',return_value=self.response()), patch.object(self.store,'_execute',side_effect=fail):
            with self.assertRaises(RuntimeError):c._refresh_access_token()
        self.assertEqual(c._token,self.old)
        self.assertIsNone(self.store.state(c.key))

    def test_keepalive_only_rotates_near_expiry(self):
        with patch('nextfit_v2_client.requests.post',return_value=self.response()) as post:
            self.client().maintain()
            self.client().maintain()
            self.assertEqual(post.call_count,1)

    def test_401_refresh_retries_original_read_with_new_authorization(self):
        c=self.client()
        with patch.object(c.session,'get',side_effect=[Mock(status_code=401),Mock(status_code=200,ok=True,json=lambda:{'Content':[]})]) as get, patch('nextfit_v2_client.requests.post',return_value=self.response()):
            self.assertEqual(c._get('/test',{}),{'Content':[]})
            self.assertEqual(get.call_count,2)
        self.assertEqual(c.session.headers['Authorization'],'Bearer '+self.new)

    def test_units_have_separate_pairs(self):
        with patch('nextfit_v2_client.requests.post',return_value=self.response()): self.client().maintain()
        other=PersistentNextFitClient(self.store,'other',self.old,'other-refresh')
        self.assertEqual(other.refresh_token,'other-refresh')
