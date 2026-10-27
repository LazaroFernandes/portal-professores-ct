from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from nextfit_v2_client import NextFitV2Client, TokenExpiredError

from ..core.cache import cache
from ..core.config import PROJECT_ROOT


TIMEZONE = ZoneInfo("America/Sao_Paulo")
POLL_SECONDS = 15
TRAINING_POLL_SECONDS = 30
_refresh_lock = threading.Lock()
_training_refresh_lock = threading.Lock()
_last_refresh_monotonic = 0.0
_last_training_refresh_monotonic = 0.0
_last_sync_error: str | None = None
_last_training_sync_error: str | None = None


def _parse_datetime(value) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=TIMEZONE)
    return parsed.astimezone(TIMEZONE)


def _event_key(row: dict) -> str:
    raw = "|".join(str(row.get(field) or "") for field in (
        "CodigoCliente", "Data", "DescricaoTipo", "Descricao", "NomeCliente",
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PresenceStore:
    def __init__(self, path: Path | None = None):
        self.postgres = path is None
        self.path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self.postgres:
            from controle_professores.postgres_data import _connect
            return _connect()
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _execute(self, connection, sql, params=()):
        if self.postgres:
            sql = sql.replace("?", "%s")
        return connection.execute(sql, params)

    def _initialize(self) -> None:
        if self.postgres:
            migration = Path(__file__).resolve().parents[2] / "migrations" / "001_daily_operation.sql"
            with self._connect() as connection:
                connection.execute(migration.read_text())
            return
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS portal_gym_visits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_key TEXT NOT NULL UNIQUE,
                        client_id TEXT NOT NULL,
                        student_name TEXT NOT NULL,
                        entered_at TEXT NOT NULL,
                        finished_at TEXT,
                        finished_by TEXT
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS portal_gym_presence_state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(portal_gym_visits)").fetchall()
                }
                for name, definition in (
                    ("professor", "TEXT"),
                    ("student_shift", "TEXT"),
                    ("training_id", "INTEGER"),
                    ("training_name", "TEXT"),
                    ("training_session", "INTEGER"),
                    ("training_total_sessions", "INTEGER"),
                    ("training_weekly_frequency", "INTEGER"),
                    ("training_usage_baseline", "INTEGER"),
                    ("training_usage_current", "INTEGER"),
                    ("workout_finished_at", "TEXT"),
                    ("student_lookup_error", "TEXT"),
                    ("training_error", "TEXT"),
                ):
                    if name not in columns:
                        connection.execute(
                            f"ALTER TABLE portal_gym_visits ADD COLUMN {name} {definition}"
                        )
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS portal_daily_attendance_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        visit_id INTEGER NOT NULL UNIQUE,
                        client_id TEXT NOT NULL,
                        professor TEXT NOT NULL,
                        attendance_date TEXT NOT NULL,
                        performance TEXT NOT NULL,
                        had_pain INTEGER NOT NULL DEFAULT 0,
                        pain_description TEXT NOT NULL DEFAULT '',
                        observation TEXT NOT NULL DEFAULT '',
                        evolution TEXT NOT NULL DEFAULT '',
                        finalized_by TEXT NOT NULL,
                        finalized_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (visit_id) REFERENCES portal_gym_visits(id)
                    )
                """)

    def ingest(self, rows: list[dict]) -> int:
        inserted = 0
        with closing(self._connect()) as connection:
            with connection:
                if self.postgres:
                    connection.execute("SELECT pg_advisory_xact_lock(72102101)")
                for row in sorted(rows, key=lambda item: str(item.get("Data") or "")):
                    if row.get("Inativo") is True or str(row.get("DescricaoTipo") or "").strip().casefold() != "acesso":
                        continue
                    entered_at = _parse_datetime(row.get("Data"))
                    client_id = str(row.get("CodigoCliente") or "").strip()
                    name = str(row.get("NomeCliente") or "").strip()
                    if not entered_at or not client_id or not name:
                        continue
                    day_start = entered_at.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)
                    active = self._execute(connection, 
                        """
                        SELECT 1 FROM portal_gym_visits
                        WHERE client_id = ?
                          AND entered_at >= ? AND entered_at < ?
                        """,
                        (client_id, day_start.isoformat(), day_end.isoformat()),
                    ).fetchone()
                    if active:
                        continue
                    cursor = self._execute(connection, 
                        """
                        INSERT INTO portal_gym_visits
                            (event_key, client_id, student_name, entered_at)
                        VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING
                        """,
                        (_event_key(row), client_id, name, entered_at.isoformat()),
                    )
                    inserted += cursor.rowcount
        return inserted

    def active(self, now: datetime, include_finished: bool = False) -> list[dict]:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        with closing(self._connect()) as connection:
            query = """
                SELECT v.id, v.client_id, v.student_name, v.entered_at,
                       v.finished_at, v.professor, v.student_shift,
                       v.training_id, v.training_name, v.training_session,
                       v.training_total_sessions, v.training_weekly_frequency,
                       v.training_usage_baseline, v.training_usage_current,
                       v.workout_finished_at, v.student_lookup_error,
                       v.training_error, r.performance, r.had_pain,
                       r.pain_description, r.observation, r.evolution,
                       r.finalized_by, r.finalized_at
                FROM portal_gym_visits
                AS v LEFT JOIN portal_daily_attendance_records AS r ON r.visit_id = v.id
                WHERE v.entered_at >= ? AND v.entered_at < ?
            """
            if not include_finished:
                query += " AND v.finished_at IS NULL"
            query += " ORDER BY v.entered_at ASC"
            rows = self._execute(connection, query, (start.isoformat(), end.isoformat())).fetchall()
        return self._serialize_visits(rows, now)

    def pending_before(self, now: datetime) -> list[dict]:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        with closing(self._connect()) as connection:
            rows = self._execute(connection, 
                """
                SELECT v.id, v.client_id, v.student_name, v.entered_at,
                       v.finished_at, v.professor, v.student_shift,
                       v.training_id, v.training_name, v.training_session,
                       v.training_total_sessions, v.training_weekly_frequency,
                       v.training_usage_baseline, v.training_usage_current,
                       v.workout_finished_at, v.student_lookup_error,
                       v.training_error, r.performance, r.had_pain,
                       r.pain_description, r.observation, r.evolution,
                       r.finalized_by, r.finalized_at
                FROM portal_gym_visits AS v
                LEFT JOIN portal_daily_attendance_records AS r ON r.visit_id = v.id
                WHERE v.entered_at < ? AND v.finished_at IS NULL
                ORDER BY v.entered_at DESC
                """,
                (start.isoformat(),),
            ).fetchall()
        return self._serialize_visits(rows, now)

    def client_for_visit(self, visit_id):
        with closing(self._connect()) as connection:
            row = self._execute(connection, "SELECT client_id FROM portal_gym_visits WHERE id = ?", (visit_id,)).fetchone()
        return str(row["client_id"]) if row else None

    def professor_for_visit(self, visit_id: int) -> str | None:
        with closing(self._connect()) as connection:
            row = self._execute(connection, 
                "SELECT professor FROM portal_gym_visits WHERE id = ?",
                (visit_id,),
            ).fetchone()
        return None if row is None else str(row["professor"] or "")

    @staticmethod
    def _serialize_visits(rows, now: datetime) -> list[dict]:
        return [{
            "id": row["id"],
            "client_id": row["client_id"],
            "name": row["student_name"],
            "entered_at": row["entered_at"],
            "professor": row["professor"] or "",
            "shift": row["student_shift"] or "",
            "training_id": row["training_id"],
            "training_name": row["training_name"] or "",
            "training_session": row["training_session"],
            "training_total_sessions": row["training_total_sessions"],
            "training_weekly_frequency": row["training_weekly_frequency"],
            "training_usage_baseline": row["training_usage_baseline"],
            "training_usage_current": row["training_usage_current"],
            "training_monitored": row["training_usage_baseline"] is not None,
            "workout_finished_at": row["workout_finished_at"],
            "attendance_finalized_at": row["finalized_at"],
            "finished_by": row["finalized_by"] or "",
            "performance": row["performance"] or "",
            "had_pain": bool(row["had_pain"]) if row["had_pain"] is not None else False,
            "pain_description": row["pain_description"] or "",
            "observation": row["observation"] or "",
            "evolution": row["evolution"] or "",
            "student_lookup_error": row["student_lookup_error"] or "",
            "training_error": row["training_error"] or "",
            "status": (
                "ATENDIMENTO FINALIZADO" if row["finalized_at"]
                else "TREINO CONCLUÍDO" if row["workout_finished_at"]
                else "ACESSO REGISTRADO"
            ),
            "duration_seconds": max(
                0, int((now - _parse_datetime(row["entered_at"])).total_seconds())
            ),
        } for row in rows]

    def set_student_context(
        self,
        visit_id: int,
        professor: str,
        shift: str,
        error: str = "",
    ) -> None:
        with closing(self._connect()) as connection:
            with connection:
                self._execute(connection, 
                    """
                    UPDATE portal_gym_visits
                    SET professor = ?, student_shift = ?, student_lookup_error = ?
                    WHERE id = ?
                    """,
                    (professor, shift, error, visit_id),
                )

    def training_targets(self, now: datetime) -> list[dict]:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        with closing(self._connect()) as connection:
            rows = self._execute(connection, 
                """
                SELECT id, client_id, training_id, training_usage_baseline,
                       workout_finished_at
                FROM portal_gym_visits
                WHERE finished_at IS NULL AND entered_at >= ? AND entered_at < ?
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [dict(row) for row in rows]

    def training_id_for_active_visit(self, visit_id: int) -> int | None:
        with closing(self._connect()) as connection:
            row = self._execute(connection, 
                """
                SELECT training_id FROM portal_gym_visits
                WHERE id = ? AND finished_at IS NULL
                """,
                (visit_id,),
            ).fetchone()
        if not row or row["training_id"] is None:
            return None
        return int(row["training_id"])

    def training_id_for_visit(self, visit_id: int) -> int | None:
        with closing(self._connect()) as connection:
            row = self._execute(connection, 
                "SELECT training_id FROM portal_gym_visits WHERE id = ?",
                (visit_id,),
            ).fetchone()
        if not row or row["training_id"] is None:
            return None
        return int(row["training_id"])

    def set_training_baseline(
        self,
        visit_id: int,
        training_id: int,
        usage: int,
        detail: dict | None = None,
    ) -> None:
        detail = detail or {}
        sessions = detail.get("Sessoes") or []
        with closing(self._connect()) as connection:
            with connection:
                self._execute(connection, 
                    """
                    UPDATE portal_gym_visits
                    SET training_id = ?, training_name = ?, training_session = ?,
                        training_total_sessions = ?, training_weekly_frequency = ?,
                        training_usage_baseline = ?, training_usage_current = ?,
                        training_error = ''
                    WHERE id = ? AND training_usage_baseline IS NULL
                    """,
                    (
                        training_id,
                        str(detail.get("Nome") or "").strip(),
                        detail.get("SessaoAtual"),
                        len(sessions),
                        detail.get("FrequenciaSemanal"),
                        usage,
                        usage,
                        visit_id,
                    ),
                )

    def set_training_current(self, visit_id: int, usage: int) -> None:
        with closing(self._connect()) as connection:
            with connection:
                self._execute(connection, 
                    "UPDATE portal_gym_visits SET training_usage_current = ? WHERE id = ?",
                    (usage, visit_id),
                )

    def set_training_error(self, visit_id: int, error: str) -> None:
        with closing(self._connect()) as connection:
            with connection:
                self._execute(connection, 
                    "UPDATE portal_gym_visits SET training_error = ? WHERE id = ?",
                    (error, visit_id),
                )

    def mark_workout_finished(self, visit_id: int, finished_at: datetime) -> None:
        with closing(self._connect()) as connection:
            with connection:
                self._execute(connection, 
                    """
                    UPDATE portal_gym_visits
                    SET workout_finished_at = ?
                    WHERE id = ? AND workout_finished_at IS NULL
                    """,
                    (finished_at.isoformat(), visit_id),
                )

    def finish(self, visit_id: int, user_name: str, now: datetime) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                cursor = self._execute(connection, 
                    """
                    UPDATE portal_gym_visits
                    SET finished_at = ?, finished_by = ?
                    WHERE id = ? AND finished_at IS NULL
                    """,
                    (now.isoformat(), user_name, visit_id),
                )
        return cursor.rowcount == 1

    def finalize_attendance(
        self,
        visit_id: int,
        user_name: str,
        performance: str,
        had_pain: bool,
        pain_description: str,
        observation: str,
        evolution: str,
        now: datetime,
    ) -> bool:
        with closing(self._connect()) as connection:
            visit = self._execute(connection, 
                "SELECT client_id, professor, entered_at FROM portal_gym_visits WHERE id = ?",
                (visit_id,),
            ).fetchone()
            if not visit:
                return False
            with connection:
                self._execute(connection, 
                    """
                    INSERT INTO portal_daily_attendance_records (
                        visit_id, client_id, professor, attendance_date,
                        performance, had_pain, pain_description, observation,
                        evolution, finalized_by, finalized_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(visit_id) DO UPDATE SET
                        performance = excluded.performance,
                        had_pain = excluded.had_pain,
                        pain_description = excluded.pain_description,
                        observation = excluded.observation,
                        evolution = excluded.evolution,
                        finalized_by = excluded.finalized_by,
                        finalized_at = excluded.finalized_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        visit_id,
                        visit["client_id"],
                        visit["professor"] or "Professor não definido",
                        _parse_datetime(visit["entered_at"]).date().isoformat(),
                        performance,
                        int(had_pain),
                        pain_description,
                        observation,
                        evolution,
                        user_name,
                        now.isoformat(),
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                self._execute(connection, 
                    """
                    UPDATE portal_gym_visits SET finished_at = ?, finished_by = ?
                    WHERE id = ?
                    """,
                    (now.isoformat(), user_name, visit_id),
                )
        return True

    def state(self, key: str) -> str | None:
        with closing(self._connect()) as connection:
            row = self._execute(connection, 
                "SELECT value FROM portal_gym_presence_state WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else None

    def set_state(self, key: str, value: str) -> None:
        with closing(self._connect()) as connection:
            with connection:
                self._execute(connection, 
                    """
                    INSERT INTO portal_gym_presence_state (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )


def _database_path() -> Path:
    configured = os.environ.get("GYM_PRESENCE_DATABASE_PATH", "data/gym_presence.db")
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache(maxsize=1)
def _store() -> PresenceStore:
    if os.environ.get("DATABASE_URL", "").strip():
        return PresenceStore()
    if os.environ.get("APP_ENV", "").lower() == "production":
        raise RuntimeError("Operação diária exige PostgreSQL em produção.")
    return PresenceStore(_database_path())


def _nextfit_client() -> NextFitV2Client:
    from .nextfit_session import client
    return client(_store())


def refresh_if_due(now: datetime | None = None) -> None:
    global _last_refresh_monotonic, _last_sync_error
    if time.monotonic() - _last_refresh_monotonic < POLL_SECONDS:
        return
    if not _refresh_lock.acquire(blocking=False):
        return
    try:
        now = now or datetime.now(TIMEZONE)
        store = _store()
        last_poll = _parse_datetime(store.state("last_poll"))
        start = (
            last_poll - timedelta(minutes=2)
            if last_poll and last_poll.date() == now.date()
            else now.replace(hour=0, minute=0, second=0, microsecond=0)
        )
        store.ingest(_nextfit_client().presencas(start, now))
        store.set_state("last_poll", now.isoformat())
        try:
            refresh_student_context(store, now)
            _last_sync_error = None
        except Exception:
            _last_sync_error = "Acessos atualizados; não foi possível atualizar a carteira de professores."
    except TokenExpiredError:
        _last_sync_error = "A sessão do NEXT expirou ou foi revogada. A gerência precisa reconectar a integração."
    except Exception as exc:
        _last_sync_error = "Não foi possível atualizar os acessos. Verifique a integração NextFit."
    finally:
        _last_refresh_monotonic = time.monotonic()
        _refresh_lock.release()


def refresh_student_context(store: PresenceStore, now: datetime) -> None:
    """Relaciona visitas à carteira atual consultada diretamente no NextFit."""
    students = {
        str(row.get("ClienteId") or "").strip(): row
        for row in _roster_students()
        if str(row.get("ClienteId") or "").strip()
    }
    for visit in store.training_targets(now):
        student = students.get(str(visit["client_id"]))
        if student:
            store.set_student_context(
                visit["id"],
                str(student.get("Professor") or "").strip(),
                str(student.get("Turno") or "").strip(),
            )
        else:
            store.set_student_context(
                visit["id"],
                "",
                "",
                "Aluno não localizado na consulta atual do NextFit.",
            )


def _active_training_by_client(trainings: list[dict]) -> dict[str, dict]:
    selected: dict[str, dict] = {}
    for training in trainings:
        if str(training.get("Status") or "") != "1":
            continue
        client_id = str(training.get("CodigoCliente") or "").strip()
        if not client_id:
            continue
        current = selected.get(client_id)
        key = (str(training.get("DataCriacao") or ""), int(training.get("Id") or 0))
        current_key = (
            str(current.get("DataCriacao") or ""),
            int(current.get("Id") or 0),
        ) if current else None
        if current_key is None or key > current_key:
            selected[client_id] = training
    return selected


def process_training_snapshot(
    store: PresenceStore,
    trainings: list[dict],
    detail_loader,
    now: datetime,
) -> int:
    by_client = _active_training_by_client(trainings)
    by_id = {int(row["Id"]): row for row in trainings if row.get("Id") is not None}
    detected = 0
    for visit in store.training_targets(now):
        if visit["workout_finished_at"]:
            continue
        if visit["training_usage_baseline"] is None:
            training = by_client.get(str(visit["client_id"]))
            if training:
                try:
                    detail = detail_loader(int(training["Id"]))
                    store.set_training_baseline(
                        visit["id"],
                        int(training["Id"]),
                        int(training.get("QtdeUtilizado") or 0),
                        detail,
                    )
                except Exception as exc:
                    store.set_training_error(
                        visit["id"],
                        f"Erro ao consultar detalhes do treino: {str(exc).splitlines()[0]}",
                    )
            continue
        training = by_id.get(int(visit["training_id"]))
        if not training:
            store.set_training_error(visit["id"], "A ficha ativa não apareceu na consulta atual.")
            continue
        usage = int(training.get("QtdeUtilizado") or 0)
        store.set_training_current(visit["id"], usage)
        if usage <= int(visit["training_usage_baseline"]):
            continue
        try:
            detail = detail_loader(int(visit["training_id"]))
            finished_at = _parse_datetime(detail.get("DataAlteracao")) or now
            store.mark_workout_finished(visit["id"], finished_at)
            store.set_training_error(visit["id"], "")
            detected += 1
        except Exception as exc:
            store.set_training_error(
                visit["id"],
                f"Erro ao confirmar conclusão do treino: {str(exc).splitlines()[0]}",
            )
    return detected


def build_training_detail(detail: dict) -> dict:
    sessions = detail.get("Sessoes") or []
    try:
        current_session = max(1, int(detail.get("SessaoAtual") or 1))
    except (TypeError, ValueError):
        current_session = 1
    session_index = min(current_session - 1, max(0, len(sessions) - 1))
    session = sessions[session_index] if sessions else {}
    exercises = sorted(
        session.get("Exercicios") or [],
        key=lambda exercise: exercise.get("Ordem") or 0,
    )
    return {
        "name": str(detail.get("Nome") or "Treino do dia").strip(),
        "session": current_session,
        "total_sessions": len(sessions),
        "weekly_frequency": detail.get("FrequenciaSemanal"),
        "coach": str((detail.get("Usuario") or {}).get("Nome") or "").strip(),
        "notes": str(detail.get("Observacao") or "").strip(),
        "exercises": [
            {
                "name": str((exercise.get("Exercicio") or {}).get("Nome") or "Exercício").strip(),
                "sets": exercise.get("QtdeSeries"),
                "repetitions": exercise.get("Repeticoes"),
                "load": exercise.get("Carga"),
                "rest": exercise.get("Intervalo"),
                "notes": str(exercise.get("Observacoes") or "").strip(),
            }
            for exercise in exercises
        ],
    }


def _visit_allowed(visit_id: int, user: dict, now: datetime | None = None) -> bool:
    if user.get("role") == "admin":
        return True
    professor = str(user.get("name") or "").strip().casefold()
    cid = _store().client_for_visit(visit_id)
    owner = next((str(row.get("Professor") or "") for row in _roster_students()
                  if str(row["ClienteId"]) == cid), None)
    return owner is not None and owner.strip().casefold() == professor


def training_detail_for_visit(visit_id: int, user: dict | None = None) -> dict:
    if user is not None and not _visit_allowed(visit_id, user):
        raise PermissionError("Este aluno não pertence à carteira do professor.")
    training_id = _store().training_id_for_visit(visit_id)
    if training_id is None:
        raise LookupError("Nenhuma ficha ativa foi detectada para este aluno.")
    detail = cache.get_or_set(
        f"presence:training-detail:{training_id}",
        60,
        lambda: _nextfit_client().detalhe_treino(training_id),
    )
    if not detail:
        raise LookupError("Os detalhes desta ficha não estão disponíveis.")
    return build_training_detail(detail)


def refresh_training_if_due(now: datetime | None = None) -> None:
    global _last_training_refresh_monotonic, _last_training_sync_error
    if time.monotonic() - _last_training_refresh_monotonic < TRAINING_POLL_SECONDS:
        return
    if not _training_refresh_lock.acquire(blocking=False):
        return
    try:
        now = now or datetime.now(TIMEZONE)
        client = _nextfit_client()
        process_training_snapshot(
            _store(),
            client.listar_treinos(),
            client.detalhe_treino,
            now,
        )
        _last_training_sync_error = None
    except Exception as exc:
        _last_training_sync_error = "Não foi possível atualizar os treinos. Os acessos continuam disponíveis."
    finally:
        _last_training_refresh_monotonic = time.monotonic()
        _training_refresh_lock.release()


def _roster_students():
    from .nextfit_roster import current_roster
    return current_roster()["students"]


def _with_current_professors(visits):
    roster = {str(row["ClienteId"]): row for row in _roster_students()}
    return [{**visit, "professor": roster.get(visit["client_id"], {}).get("Professor", ""),
             "shift": roster.get(visit["client_id"], {}).get("Turno", "")} for visit in visits]


def current_payload(now: datetime | None = None, user: dict | None = None) -> dict:
    now = now or datetime.now(TIMEZONE)
    refresh_if_due(now)
    refresh_training_if_due(now)
    visits = _with_current_professors(_store().active(now, include_finished=True))
    if user and user.get("role") == "professor":
        professor = str(user.get("name") or "").strip().casefold()
        visits = [
            visit for visit in visits
            if visit["professor"].strip().casefold() == professor
        ]
    from .nextfit_roster import professor_names
    professors = professor_names() if not user or user.get("role") == "admin" else [user["name"]]
    return {
        "last_access_sync": _store().state("last_poll"),
        "updated_at": now.isoformat(),
        "poll_seconds": POLL_SECONDS,
        "training_poll_seconds": TRAINING_POLL_SECONDS,
        "sync_error": _last_sync_error or _last_training_sync_error,
        "total": len(visits),
        "professors": professors,
        "students": visits,
    }


def pending_payload(now: datetime | None = None, user: dict | None = None) -> dict:
    now = now or datetime.now(TIMEZONE)
    visits = _with_current_professors(_store().pending_before(now))
    if user and user.get("role") == "professor":
        professor = str(user.get("name") or "").strip().casefold()
        visits = [
            visit for visit in visits
            if visit["professor"].strip().casefold() == professor
        ]
    from .nextfit_roster import professor_names
    professors = professor_names() if not user or user.get("role") == "admin" else [user["name"]]
    return {
        "last_access_sync": _store().state("last_poll"),
        "updated_at": now.isoformat(),
        "total": len(visits),
        "professors": professors,
        "students": visits,
    }


def finish_visit(visit_id: int, user: dict, now: datetime | None = None) -> bool:
    if not _visit_allowed(visit_id, user, now):
        return False
    return _store().finish(
        visit_id,
        str(user.get("name") or "Usuário"),
        now or datetime.now(TIMEZONE),
    )


def finalize_attendance(visit_id: int, data, user: dict, now: datetime | None = None) -> bool:
    if not _visit_allowed(visit_id, user, now):
        return False
    return _store().finalize_attendance(
        visit_id=visit_id,
        user_name=str(user.get("name") or "Usuário"),
        performance=data.desempenho,
        had_pain=data.teve_dor,
        pain_description=data.descricao_dor,
        observation=data.observacao,
        evolution=data.evolucao,
        now=now or datetime.now(TIMEZONE),
    )
