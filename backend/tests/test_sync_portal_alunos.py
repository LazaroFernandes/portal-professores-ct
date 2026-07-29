from __future__ import annotations

import unittest

from sync_portal_alunos import build_portal_rows


class SyncPortalAlunosTests(unittest.TestCase):
    def test_preserves_manual_turn_and_professor(self) -> None:
        rows = build_portal_rows(
            clients=[{"id": 1, "nome": "Ana", "cliente": {"codigoUsuarioProfessor": 10}}],
            users=[{"id": 10, "nome": "Professor NextFit"}],
            contracts=[{"codigoCliente": 1, "codigoContratoBase": 100, "status": "Ativo"}],
            contract_bases=[{"id": 100, "descricao": "ACESSORIA FIXO 2026"}],
            existing_rows=[{"ClienteId": 1, "Turno": "NOITE", "Professor": "Professor Manual"}],
            now_iso="2026-07-28 10:00:00",
        )

        self.assertEqual(rows[0]["Turno"], "NOITE")
        self.assertEqual(rows[0]["Professor"], "Professor Manual")
        self.assertEqual(rows[0]["Status"], "ATIVO")
        self.assertEqual(rows[0]["Plano"], "ACESSORIA FIXO 2026")

    def test_uses_nextfit_professor_when_portal_is_empty(self) -> None:
        rows = build_portal_rows(
            clients=[{"id": 2, "nome": "Bruno", "cliente": {"codigoUsuarioProfessor": 20}}],
            users=[{"id": 20, "nome": "Professor NextFit"}],
            contracts=[{"codigoCliente": 2, "codigoContratoBase": 200, "status": "Ativo"}],
            contract_bases=[{"id": 200, "descricao": "1X BLACK"}],
            existing_rows=[],
            now_iso="2026-07-28 10:00:00",
        )

        self.assertEqual(rows[0]["Professor"], "Professor NextFit")
        self.assertEqual(rows[0]["Modalidade"], "HYROX")


if __name__ == "__main__":
    unittest.main()
