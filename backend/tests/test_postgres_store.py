from __future__ import annotations

import unittest

from postgres_store import safe_table_name


class PostgresStoreTests(unittest.TestCase):
    def test_safe_table_name_normalizes_google_sheet_titles(self) -> None:
        self.assertEqual(safe_table_name("sheet_nextfit", "Contas Receber"), "sheet_nextfit_contas_receber")
        self.assertEqual(safe_table_name("sheet_controle", "RegistroSemanal"), "sheet_controle_registrosemanal")
        self.assertEqual(safe_table_name("sheet_nextfit", "2026 Financeiro"), "sheet_nextfit__2026_financeiro")


if __name__ == "__main__":
    unittest.main()
