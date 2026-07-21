from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.services.frequency_service import classify_students, format_phone


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
        accesses = [
            {"CodigoCliente": 1, "Data": "2026-07-19T08:00:00-03:00"},
            {"CodigoCliente": 2, "Data": "2026-07-17T04:59:59-03:00"},
        ]

        result = classify_students(
            clients, contracts, [{"id": 10, "descricao": "Plano Black"}], accesses, now
        )

        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["inactive_count"], 1)
        self.assertEqual(result["inactive_students"][0]["name"], "Bruno")
        self.assertEqual(result["inactive_students"][0]["plan"], "Plano Black")
        self.assertEqual(result["inactive_students"][0]["last_access"], "2026-07-17T04:59:59-03:00")

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


if __name__ == "__main__":
    unittest.main()
