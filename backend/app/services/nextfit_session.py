"""Durable v2 session shared across workers and deployments. Never exposed by API."""
import base64
import json
import os
import time
from contextlib import closing

from nextfit_v2_client import NextFitV2Client, TokenExpiredError


class PersistentNextFitClient(NextFitV2Client):
    def __init__(self, store, unit, token='', refresh_token=None):
        self.store = store
        self.key = f'nextfit_v2_session:{unit}'
        saved = store.state(self.key)
        pair = json.loads(saved) if saved else {'access_token': token, 'refresh_token': refresh_token}
        if not pair.get('access_token'):
            raise TokenExpiredError('A conexão com o NEXT precisa ser autenticada novamente.')
        super().__init__(pair['access_token'], unit, pair.get('refresh_token'))

    def _adopt(self, pair):
        self._token = pair['access_token']
        self.refresh_token = pair.get('refresh_token')
        self.session.headers['Authorization'] = f'Bearer {self._token}'

    def _refresh_access_token(self):
        # The transaction lock covers read + rotation + atomic persistence. A second
        # worker uses the winning pair instead of rotating an obsolete refresh token.
        with closing(self.store._connect()) as connection:
            with connection:
                if self.store.postgres:
                    connection.execute('SELECT pg_advisory_xact_lock(72102103)')
                else:
                    connection.execute('BEGIN IMMEDIATE')
                row = self.store._execute(connection,
                    'SELECT value FROM portal_gym_presence_state WHERE key = ?', (self.key,)).fetchone()
                pair = json.loads(row['value']) if row else None
                if pair and pair['access_token'] != self._token:
                    self._adopt(pair)
                    return True
                # Use a separate client; adopt only AFTER the transaction commits.
                fresh = NextFitV2Client(self._token, self._codigo_unidade, self.refresh_token)
                if not fresh._refresh_access_token():
                    return False
                pair = {'access_token': fresh._token, 'refresh_token': fresh.refresh_token,
                        'updated_at': time.time()}
                self.store._execute(connection,
                    'INSERT INTO portal_gym_presence_state (key,value) VALUES (?,?) '
                    'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                    (self.key, json.dumps(pair)))
        self._adopt(pair)
        return True

    def maintain(self):
        # JWT claims are used ONLY to schedule refresh, never to authorize a user.
        try:
            expires = json.loads(base64.urlsafe_b64decode(self._token.split('.')[1] + '==='))['exp']
        except (ValueError, KeyError, IndexError, TypeError):
            expires = 0
        if float(expires) <= time.time() + 3600 and not self._refresh_access_token():
            raise TokenExpiredError('A conexão com o NEXT precisa ser autenticada novamente.')


def client(store):
    unit = os.environ.get('NEXTFIT_CODIGO_UNIDADE', '').strip()
    if not unit:
        raise RuntimeError('Unidade NEXT não configurada.')
    return PersistentNextFitClient(store, unit, os.environ.get('NEXTFIT_V2_TOKEN','').strip(),
                                   os.environ.get('NEXTFIT_V2_REFRESH_TOKEN','').strip() or None)


def maintain_session():
    from .presence_service import _store
    client(_store()).maintain()
