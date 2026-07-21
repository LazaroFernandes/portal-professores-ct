from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from ..services.frequency_service import TIMEZONE, refresh_snapshot


logger = logging.getLogger("nextfit.scheduler")
_scheduler: BackgroundScheduler | None = None


def _scheduled_refresh() -> None:
    try:
        refresh_snapshot()
    except Exception:
        logger.exception("Atualização automática de frequência falhou")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone=TIMEZONE)
    _scheduler.add_job(
        _scheduled_refresh,
        trigger="cron",
        hour=5,
        minute=0,
        id="frequency-dashboard-daily",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("Agendamento de frequência ativo: diariamente às 05:00 (%s)", TIMEZONE.key)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
