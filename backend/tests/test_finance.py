import unittest
from datetime import date
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.services.finance_service import normalize, dashboard, unique, cents, read_payables
from backend.app.api.finance import router
from backend.app.core.security import current_user


def movement(id=1, amount=100, when='2026-10-05', **extra):
    return dict(id=id, valor=amount, tipo='Entrada', status='Efetivado', dataEfetivacao=when, dataMovimentacao='2026-09-01', **extra)


class FinanceTests(unittest.TestCase):
    def test_no_double_count_received_invoice_or_paid_bill(self):
        s = normalize([movement()], [{'id':2,'status':'Recebido','valor':100}], [{'Id':3,'Status':2,'Valor':100}])
        self.assertEqual(len(s['rows']),1)
        d=dashboard(date(2026,10,1),s,date(2026,10,28))
        self.assertEqual(d['summary']['actual_in'],10000)

    def test_id_dedup_preserves_distinct_equal_transactions(self):
        a=movement(); b=movement(id=2)
        rows,n=unique([a,a,b],'id')
        self.assertEqual((len(rows),n),(2,1))
        with self.assertRaises(ValueError): unique([a,movement(amount=99)],'id')

    def test_decimal_and_invalid_amount(self):
        self.assertEqual(cents('10.015'),1002)
        with self.assertRaises(ValueError): cents('NaN')

    def test_effective_date_not_creation_date(self):
        s=normalize([movement()],[],[])
        self.assertEqual(dashboard(date(2026,9,1),s,date(2026,10,28))['summary']['actual_in'],0)

    def test_transfer_method_is_not_removed(self):
        s=normalize([movement(tipoMetodo='Transferencia')],[],[])
        self.assertEqual(len(s['rows']),1)

    def test_only_unique_internal_transfer_pair_is_excluded(self):
        a=movement(descricao='Transferência de conta Next Fit Pay para conta bancária',codigoContaFinanc=1,tipoMetodo='Transferencia')
        b={**a,'id':2,'tipo':'Saida','codigoContaFinanc':2}
        s=normalize([a,b,movement(id=3,tipoMetodo='Transferencia')],[],[])
        d=dashboard(date(2026,10,1),s,date(2026,10,28))
        self.assertEqual(d['summary']['actual_in'],10000)
        self.assertEqual(d['summary']['actual_out'],0)
        self.assertEqual(len(d['internal_transfers']),2)
        s=normalize([a,b,{**b,'id':4}],[],[])
        self.assertEqual(s['quality']['internal_transfer_pairs'],0)
        self.assertEqual(s['quality']['issues']['unmatched_internal_transfer'],3)

    def test_open_partial_uses_balance_not_nominal(self):
        s=normalize([], [{'id':1,'status':'Aberto','valor':100,'dataVencimento':'2026-10-30','receberRecebimento':{'saldo':25}}],[])
        self.assertEqual(s['rows'][0]['amount'],2500)

    def test_payable_status_three_without_payment_not_cash(self):
        s=normalize([],[],[{'Id':1,'Status':3,'Valor':100},{'Id':2,'Status':1,'Valor':30,'DataVencimento':'2026-10-30'}])
        self.assertEqual(len(s['rows']),1)
        self.assertEqual(s['rows'][0]['amount'],3000)

    def test_uncertain_partial_payable_is_flagged(self):
        s=normalize([],[],[{'Id':1,'Status':1,'Valor':100,'PagarPagamento':{'ValorPago':20}}])
        self.assertEqual(s['rows'],[])
        self.assertEqual(s['quality']['issues']['unresolved_payable_balance'],1)

    def test_forecast_is_incremental_and_excludes_elapsed_days(self):
        s=normalize([movement(1,100,'2026-09-30'),movement(2,100,'2026-09-26')],
                    [{'id':3,'status':'Aberto','valor':60,'dataVencimento':'2026-10-30'}],[])
        d=dashboard(date(2026,10,1),s,date(2026,10,28))
        self.assertEqual(d['summary']['estimate'],4000)
        self.assertEqual(d['summary']['projected_in'],10000)

    def test_pending_settlement_is_not_added_again(self):
        row=movement(); row['status']='AguardandoEfetivacao';row['dataMovimentacao']='2026-10-30'
        s=normalize([row],[{'id':2,'status':'Aberto','valor':100,'dataVencimento':'2026-10-30'}],[])
        d=dashboard(date(2026,10,1),s,date(2026,10,28))
        self.assertEqual(d['summary']['projected_in'],10000)
        self.assertEqual(len(d['settlements']),1)

    def test_overdue_is_visible_but_not_forecast_as_guaranteed(self):
        s=normalize([],[{'id':2,'status':'Aberto','valor':100,'dataVencimento':'2026-09-05'}],[])
        d=dashboard(date(2026,10,1),s,date(2026,10,28))
        self.assertEqual(len(d['overdue']),1)
        self.assertEqual(d['summary']['projected_in'],0)

    def test_historical_month_never_invents_forecast(self):
        s=normalize([movement(1,100,'2026-08-30')],[{'id':2,'status':'Aberto','valor':100,'dataVencimento':'2026-09-30'}],[])
        d=dashboard(date(2026,9,1),s,date(2026,10,28))
        self.assertEqual(d['summary']['projected_in'],0)
        self.assertTrue(d['closed'])

    def test_next_month_uses_complete_baseline_and_february_handles_31st(self):
        s=normalize([movement(1,100,'2026-01-31')],[],[])
        d=dashboard(date(2026,2,1),s,date(2026,2,10))
        self.assertEqual(d['summary']['estimate'],10000)
        self.assertEqual(d['weeks'][-1]['end'],'2026-02-28')
        self.assertEqual(dashboard(date(2026,3,1),s,date(2026,2,10))['baseline']['month'],'2026-01')

    def test_incomplete_payable_pagination_fails(self):
        with patch('backend.app.services.finance_service._store'), patch('backend.app.services.finance_service.session_client') as client:
            client.return_value._get.return_value={'Content':[{'Id':1}],'Total':2,'Last':True}
            with self.assertRaises(ValueError): read_payables()


class FinanceAccessTests(unittest.TestCase):
    def setUp(self):
        self.app=FastAPI();self.app.include_router(router);self.client=TestClient(self.app)

    def test_anonymous_and_professor_denied_before_fetch(self):
        with patch('backend.app.api.finance.request_dashboard') as load:
            self.assertEqual(self.client.get('/api/admin/finance').status_code,401)
            self.app.dependency_overrides[current_user]=lambda:{'role':'professor'}
            self.assertEqual(self.client.get('/api/admin/finance').status_code,403)
            load.assert_not_called()

    def test_admin_and_no_cache_and_upstream_error_sanitized(self):
        self.app.dependency_overrides[current_user]=lambda:{'role':'admin'}
        with patch('backend.app.api.finance.request_dashboard',return_value={'ok':True}):
            response=self.client.get('/api/admin/finance?month=2026-10')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertEqual(self.client.get('/api/admin/finance?month=2026-13').status_code,422)
        with patch('backend.app.api.finance.request_dashboard',side_effect=RuntimeError('secret')):
            response=self.client.get('/api/admin/finance')
            self.assertEqual(response.status_code,503)
            self.assertNotIn('secret',response.text)

    def test_loading_is_202_without_partial_totals(self):
        self.app.dependency_overrides[current_user]=lambda:{'role':'admin'}
        with patch('backend.app.api.finance.request_dashboard',return_value=None):
            response=self.client.get('/api/admin/finance?month=2026-10')
            self.assertEqual(response.status_code,202)
            self.assertEqual(response.json(),{'loading':True})
            self.assertEqual(response.headers['retry-after'],'3')
