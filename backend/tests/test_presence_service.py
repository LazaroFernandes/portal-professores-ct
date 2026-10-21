from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend.app.services.presence_service import (
    PresenceStore,
    _visit_allowed,
    build_training_detail,
    process_training_snapshot,
)


TZ = ZoneInfo("America/Sao_Paulo")


class PresenceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = PresenceStore(Path(self.temp_dir.name) / "presence.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_ingests_access_once_and_ignores_agenda(self) -> None:
        rows = [
            {
                "CodigoCliente": 10,
                "NomeCliente": "Ana",
                "Data": "2026-07-29T10:00:00-03:00",
                "DescricaoTipo": "Acesso",
            },
            {
                "CodigoCliente": 20,
                "NomeCliente": "Bruno",
                "Data": "2026-07-29T10:05:00-03:00",
                "DescricaoTipo": "Agenda",
            },
        ]

        self.assertEqual(self.store.ingest(rows), 1)
        self.assertEqual(self.store.ingest(rows), 0)
        active = self.store.active(datetime(2026, 7, 29, 11, 0, tzinfo=TZ))
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["name"], "Ana")
        self.assertEqual(active[0]["duration_seconds"], 3600)

    def test_later_access_does_not_reopen_completed_daily_attendance(self):
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        row = {"CodigoCliente": 10, "NomeCliente": "Teste", "Data": now.isoformat(), "DescricaoTipo": "Acesso"}
        self.store.ingest([row])
        visit = self.store.active(now)[0]
        self.store.finalize_attendance(visit["id"], "Professor", "Bom", False, "", "", "", now)
        row["Data"] = "2026-07-29T12:00:00-03:00"
        self.assertEqual(self.store.ingest([row]), 0)
        self.assertEqual(len(self.store.active(now, include_finished=True)), 1)
        self.assertEqual(self.store.active(now), [])

    def test_finishing_removes_visit_from_active_list(self) -> None:
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        visit_id = self.store.active(now)[0]["id"]

        self.assertTrue(self.store.finish(visit_id, "Professor", now))
        self.assertFalse(self.store.finish(visit_id, "Professor", now))
        self.assertEqual(self.store.active(now), [])

    def test_unfinished_visit_from_previous_day_does_not_block_new_entry(self) -> None:
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-28T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        inserted = self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])

        self.assertEqual(inserted, 1)
        active = self.store.active(datetime(2026, 7, 29, 11, 0, tzinfo=TZ))
        self.assertEqual(len(active), 1)

    def test_previous_unfinished_visit_accumulates_as_pending(self) -> None:
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-28T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        today = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        previous = self.store.pending_before(today)

        self.assertEqual(len(previous), 1)
        self.assertEqual(previous[0]["name"], "Ana")

        self.store.finish(previous[0]["id"], "Professor", today)
        self.assertEqual(self.store.pending_before(today), [])

    def test_professor_can_finalize_own_pending_visit_from_previous_day(self) -> None:
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-28T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        previous = self.store.pending_before(
            datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        )[0]
        self.store.set_student_context(previous["id"], "Lucas", "MANHÃ")

        with patch("backend.app.services.presence_service._store", return_value=self.store):
            self.assertTrue(_visit_allowed(
                previous["id"], {"role": "professor", "name": "Lucas"}
            ))
            self.assertFalse(_visit_allowed(
                previous["id"], {"role": "professor", "name": "Katiucy"}
            ))

    def test_detects_workout_finish_when_usage_counter_increases(self) -> None:
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        training = {
            "Id": 100,
            "CodigoCliente": 10,
            "Status": 1,
            "DataCriacao": "2026-07-01T10:00:00",
            "QtdeUtilizado": 3,
        }

        detected = process_training_snapshot(
            self.store, [training], lambda _: {}, now
        )

        self.assertEqual(detected, 0)
        active = self.store.active(now)
        self.assertTrue(active[0]["training_monitored"])
        self.assertIsNone(active[0]["workout_finished_at"])

        training["QtdeUtilizado"] = 4
        detected = process_training_snapshot(
            self.store,
            [training],
            lambda _: {"DataAlteracao": "2026-07-29T11:30:00-03:00"},
            now,
        )

        self.assertEqual(detected, 1)
        self.assertEqual(
            self.store.active(now)[0]["workout_finished_at"],
            "2026-07-29T11:30:00-03:00",
        )

    def test_does_not_monitor_inactive_training(self) -> None:
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])

        process_training_snapshot(
            self.store,
            [{
                "Id": 100,
                "CodigoCliente": 10,
                "Status": 2,
                "QtdeUtilizado": 3,
            }],
            lambda _: {},
            now,
        )

        self.assertFalse(self.store.active(now)[0]["training_monitored"])

    def test_active_training_exposes_ficha_session_and_usage(self) -> None:
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        self.store.ingest([{
            "Id": 99,
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        process_training_snapshot(
            self.store,
            [{
                "Id": 100,
                "CodigoCliente": 10,
                "Status": 1,
                "DataCriacao": "2026-07-01T10:00:00",
                "QtdeUtilizado": 3,
            }],
            lambda _: {
                "Nome": "Hipertrofia 02",
                "SessaoAtual": 2,
                "FrequenciaSemanal": 4,
                "Sessoes": [{}, {}, {}],
            },
            now,
        )

        visit = self.store.active(now)[0]
        self.assertEqual(visit["training_name"], "Hipertrofia 02")
        self.assertEqual(visit["training_session"], 2)
        self.assertEqual(visit["training_usage_baseline"], 3)
        self.assertEqual(visit["status"], "ACESSO REGISTRADO")

    def test_student_without_professor_remains_visible(self) -> None:
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        visit_id = self.store.active(now)[0]["id"]
        self.store.set_student_context(
            visit_id, "", "", "Aluno não localizado na carteira do Portal dos Professores."
        )

        visit = self.store.active(now)[0]
        self.assertEqual(visit["professor"], "")
        self.assertIn("não localizado", visit["student_lookup_error"])

    def test_finalize_attendance_saves_daily_record_and_status(self) -> None:
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        visit_id = self.store.active(now)[0]["id"]
        self.store.set_student_context(visit_id, "Lucas", "MANHÃ")

        self.assertTrue(self.store.finalize_attendance(
            visit_id=visit_id,
            user_name="Lucas",
            performance="Bom",
            had_pain=True,
            pain_description="Joelho esquerdo",
            observation="Carga reduzida.",
            evolution="Boa execução.",
            now=now,
        ))

        visit = self.store.active(now, include_finished=True)[0]
        self.assertEqual(visit["status"], "ATENDIMENTO FINALIZADO")
        self.assertEqual(visit["performance"], "Bom")
        self.assertEqual(visit["pain_description"], "Joelho esquerdo")
        self.assertEqual(visit["finished_by"], "Lucas")

    def test_professor_can_only_access_own_portfolio(self) -> None:
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        visit_id = self.store.active(now)[0]["id"]
        self.store.set_student_context(visit_id, "Lucas", "MANHÃ")

        with patch("backend.app.services.presence_service._store", return_value=self.store):
            self.assertTrue(_visit_allowed(
                visit_id, {"role": "professor", "name": "Lucas"}, now
            ))
            self.assertFalse(_visit_allowed(
                visit_id, {"role": "professor", "name": "Katiucy"}, now
            ))
            self.assertTrue(_visit_allowed(
                visit_id, {"role": "admin", "name": "Administrador"}, now
            ))

    def test_returns_training_id_only_for_active_monitored_visit(self) -> None:
        now = datetime(2026, 7, 29, 11, 0, tzinfo=TZ)
        self.store.ingest([{
            "CodigoCliente": 10,
            "NomeCliente": "Ana",
            "Data": "2026-07-29T10:00:00-03:00",
            "DescricaoTipo": "Acesso",
        }])
        visit_id = self.store.active(now)[0]["id"]
        self.assertIsNone(self.store.training_id_for_active_visit(visit_id))

        self.store.set_training_baseline(visit_id, 100, 3)
        self.assertEqual(self.store.training_id_for_active_visit(visit_id), 100)

        self.store.finish(visit_id, "Professor", now)
        self.assertIsNone(self.store.training_id_for_active_visit(visit_id))

    def test_builds_current_session_training_detail(self) -> None:
        detail = build_training_detail({
            "Nome": "Treino A/B",
            "SessaoAtual": 2,
            "FrequenciaSemanal": 3,
            "Usuario": {"Nome": "Professor João"},
            "Observacao": "Atenção ao joelho",
            "Sessoes": [
                {"Exercicios": [{"Ordem": 1, "Exercicio": {"Nome": "Supino"}}]},
                {"Exercicios": [
                    {
                        "Ordem": 2,
                        "QtdeSeries": 3,
                        "Repeticoes": "12",
                        "Carga": "20 kg",
                        "Intervalo": "60 s",
                        "Observacoes": "Controlar a descida",
                        "Exercicio": {"Nome": "Agachamento"},
                    },
                    {"Ordem": 1, "Exercicio": {"Nome": "Leg press"}},
                ]},
            ],
        })

        self.assertEqual(detail["name"], "Treino A/B")
        self.assertEqual(detail["session"], 2)
        self.assertEqual(detail["total_sessions"], 2)
        self.assertEqual(detail["exercises"][0]["name"], "Leg press")
        self.assertEqual(detail["exercises"][1]["sets"], 3)


if __name__ == "__main__":
    unittest.main()
