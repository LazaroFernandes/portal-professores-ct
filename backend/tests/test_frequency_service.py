from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend.app.services.frequency_service import classify_students, format_phone, refresh_snapshot


TZ = ZoneInfo("America/Sao_Paulo")


class FrequencyServiceTests(unittest.TestCase):
    def test_classifies_only_system_clients_with_active_contracts(self) -> None:
        now = datetime(2026, 7, 21, 5, 0, tzinfo=TZ)
        clients = [
            {"id": 1, "nome": "Ana", "inativo": False, "dddFone": "11", "fone": "999998888"},
            {"id": 2, "nome": "Bruno", "inativo": False},
            {"id": 3, "nome": "Cancelada", "inativo": True},
            {"id": 4, "nome": "Sem plano", "inativo": False},
        ]
        contracts = [
            {"codigoCliente": 1, "codigoContratoBase": 10, "status": "Ativo"},
            {"codigoCliente": 2, "codigoContratoBase": 10, "status": "Ativo"},
            {"codigoCliente": 3, "codigoContratoBase": 10, "status": "Ativo"},
            {"codigoCliente": 4, "codigoContratoBase": 10, "status": "Cancelado"},
        ]
        receivables = [
            {"codigoCliente": 1, "status": "Recebido", "dataVencimento": "2026-07-10"},
            {"codigoCliente": 2, "status": "Aberto", "dataVencimento": "2026-07-18"},
        ]

        result = classify_students(
            clients, contracts, [{"id": 10, "descricao": "Plano Black"}], receivables, now
        )

        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["inactive_count"], 1)
        self.assertEqual(result["inactive_students"][0]["name"], "Bruno")
        self.assertEqual(result["inactive_students"][0]["plan"], "Plano Black")
        self.assertEqual(result["inactive_students"][0]["due_date"], "2026-07-18")

    def test_keeps_open_payment_in_three_day_grace_period_active(self) -> None:
        now = datetime(2026, 7, 21, 5, 0, tzinfo=TZ)
        result = classify_students(
            [{"id": 1, "nome": "Ana", "inativo": False}],
            [{"codigoCliente": 1, "status": "Ativo"}],
            [],
            [{"codigoCliente": 1, "status": "Aberto", "dataVencimento": "2026-07-19"}],
            now,
        )
        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["inactive_count"], 0)

    def test_lists_overdue_client_after_contract_is_blocked(self) -> None:
        now = datetime(2026, 7, 21, 5, 0, tzinfo=TZ)
        result = classify_students(
            [{"id": 1, "nome": "Ana", "inativo": False}],
            [{"codigoCliente": 1, "codigoContratoBase": 10, "status": "Bloqueado"}],
            [{"id": 10, "descricao": "Plano Black"}],
            [{"codigoCliente": 1, "status": "Aberto", "dataVencimento": "2026-07-18"}],
            now,
        )
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["inactive_count"], 1)
        self.assertEqual(result["inactive_students"][0]["plan"], "Plano Black")

    def test_lists_latest_blocked_contract_three_days_after_expiration(self) -> None:
        now = datetime(2026, 7, 21, 5, 0, tzinfo=TZ)
        result = classify_students(
            [{"id": 1, "nome": "Ana", "inativo": False}],
            [{
                "id": 20,
                "codigoCliente": 1,
                "codigoContratoBase": 10,
                "status": "Bloqueado",
                "dataInicio": "2026-06-18",
                "dataValidade": "2026-07-18",
            }],
            [{"id": 10, "descricao": "Plano Black"}],
            [{"codigoCliente": 1, "status": "Recebido", "dataVencimento": "2026-07-18"}],
            now,
        )
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["inactive_count"], 1)
        self.assertEqual(result["inactive_students"][0]["due_date"], "2026-07-18")

    def test_keeps_recently_expired_blocked_contract_in_grace_period(self) -> None:
        now = datetime(2026, 7, 21, 5, 0, tzinfo=TZ)
        result = classify_students(
            [{"id": 1, "nome": "Ana", "inativo": False}],
            [{
                "id": 20,
                "codigoCliente": 1,
                "status": "Bloqueado",
                "dataInicio": "2026-06-19",
                "dataValidade": "2026-07-19",
            }],
            [],
            [],
            now,
        )
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["inactive_count"], 0)

    def test_ignores_non_open_receivables(self) -> None:
        now = datetime(2026, 7, 21, 5, 0, tzinfo=TZ)
        result = classify_students(
            [{"id": 1, "nome": "Ana", "inativo": False}],
            [{"codigoCliente": 1, "status": "Ativo"}],
            [],
            [
                {"codigoCliente": 1, "status": "Cancelado", "dataVencimento": "2026-07-01"},
                {"codigoCliente": 1, "status": "Renegociado", "dataVencimento": "2026-07-01"},
            ],
            now,
        )
        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["inactive_count"], 0)

    def test_excludes_contract_that_has_already_ended(self) -> None:
        now = datetime(2026, 7, 21, 5, 0, tzinfo=TZ)
        result = classify_students(
            [{"id": 1, "nome": "Ana", "inativo": False}],
            [{"codigoCliente": 1, "status": "Ativo", "dataEncerramento": "2026-07-20"}],
            [],
            [],
            now,
        )
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["inactive_count"], 0)

    def test_phone_formatting_and_missing_value(self) -> None:
        self.assertEqual(format_phone("48", "999998888"), "(48) 99999-8888")
        self.assertEqual(format_phone("48", "33334444"), "(48) 3333-4444")
        self.assertEqual(format_phone("", ""), "Não informado")
        self.assertEqual(format_phone("51", "1234567"), "Não informado")

    @patch(
        "backend.app.services.frequency_service._snapshot_from_postgres",
        return_value={"active_count": 10, "inactive_count": 2},
    )
    @patch(
        "backend.app.services.frequency_service.sync_nextfit_to_postgres",
        return_value={"errors": 0},
    )
    @patch("backend.app.services.frequency_service.postgres_data.enabled", return_value=True)
    def test_refresh_syncs_nextfit_before_reading_postgres(
        self, _enabled, sync_nextfit, _snapshot
    ) -> None:
        result = refresh_snapshot(now=datetime(2026, 7, 21, 5, 0, tzinfo=TZ))

        self.assertEqual(result["inactive_count"], 2)
        sync_nextfit.assert_called_once_with(selected={
            "clientes",
            "contratos_base",
            "contratos_cliente",
            "contas_receber",
        })


if __name__ == "__main__":
    unittest.main()
