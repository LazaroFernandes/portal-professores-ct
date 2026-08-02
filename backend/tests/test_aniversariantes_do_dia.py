from __future__ import annotations

import unittest
from datetime import date

from aniversariantes_do_dia import buscar_aniversariantes


class AniversariantesDoDiaTests(unittest.TestCase):
    def test_active_birthday_client_is_listed(self) -> None:
        result = buscar_aniversariantes(
            clientes=[{
                "id": 1,
                "nome": "Ana",
                "dataNascimento": "1990-08-01T00:00:00",
                "inativo": False,
                "dddFone": "48",
                "fone": "999998888",
            }],
            contratos=[{"codigoCliente": 1, "status": "Ativo", "dataInicio": "2026-01-01T00:00:00"}],
            hoje=date(2026, 8, 1),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["nome"], "Ana")
        self.assertEqual(result[0]["situacao"], "ATIVO")
        self.assertEqual(result[0]["telefone"], "(48) 999998888")

    def test_recently_expired_contract_is_listed_inside_renewal_margin(self) -> None:
        result = buscar_aniversariantes(
            clientes=[{"id": 2, "nome": "Bruno", "dataNascimento": "1988-08-01T00:00:00", "inativo": True}],
            contratos=[{
                "codigoCliente": 2,
                "status": "Bloqueado",
                "dataInicio": "2026-01-01T00:00:00",
                "dataValidade": "2026-07-30T00:00:00",
            }],
            hoje=date(2026, 8, 1),
        )

        self.assertEqual(len(result), 1)
        self.assertIn("MARGEM DE RENOVACAO", result[0]["situacao"])

    def test_cancelled_contract_is_not_listed(self) -> None:
        result = buscar_aniversariantes(
            clientes=[{"id": 3, "nome": "Carla", "dataNascimento": "1988-08-01T00:00:00", "inativo": True}],
            contratos=[{
                "codigoCliente": 3,
                "status": "Cancelado",
                "dataInicio": "2026-01-01T00:00:00",
                "dataValidade": "2026-07-30T00:00:00",
            }],
            hoje=date(2026, 8, 1),
        )

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
