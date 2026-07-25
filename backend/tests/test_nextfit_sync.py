from __future__ import annotations

import unittest

from nextfit_sync import _record_key


class NextfitSyncTests(unittest.TestCase):
    def test_record_key_uses_first_available_field(self) -> None:
        self.assertEqual(_record_key({"id": 123, "codigo": 456}, ("id", "codigo")), "123")
        self.assertEqual(_record_key({"codigo": 456}, ("id", "codigo")), "456")

    def test_record_key_falls_back_to_stable_hash(self) -> None:
        first = _record_key({"nome": "Ana", "ativo": True}, ("id",))
        second = _record_key({"ativo": True, "nome": "Ana"}, ("id",))
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
