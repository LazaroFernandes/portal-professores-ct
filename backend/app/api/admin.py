from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.security import require_admin
from ..services import admin_service


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _run(callable_):
    try:
        return callable_()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/retention")
def retention(
    year_a: int,
    month_a: int = Query(ge=1, le=12),
    year_b: int = Query(...),
    month_b: int = Query(ge=1, le=12),
    target: int | None = Query(default=None, ge=1, le=31),
    _: dict = Depends(require_admin),
) -> dict:
    return _run(lambda: admin_service.retention(year_a, month_a, year_b, month_b, target))


@router.get("/retention/modalities")
def modalities(
    year_a: int,
    month_a: int = Query(ge=1, le=12),
    year_b: int = Query(...),
    month_b: int = Query(ge=1, le=12),
    group: str = "categoria",
    _: dict = Depends(require_admin),
) -> dict:
    return _run(lambda: admin_service.modalities(year_a, month_a, year_b, month_b, group))


@router.get("/attendance")
def attendance(
    days: int = Query(default=14, ge=1, le=60),
    mode: str = "missing",
    _: dict = Depends(require_admin),
) -> list[dict]:
    return _run(lambda: admin_service.attendance(days, mode))


@router.get("/attendance/decline")
def decline(
    weeks: int = Query(default=4, ge=2, le=8),
    _: dict = Depends(require_admin),
) -> list[dict]:
    return _run(lambda: admin_service.decline(weeks))


@router.get("/weekly-comparison")
def weekly_comparison(start: str, _: dict = Depends(require_admin)) -> list[dict]:
    return _run(lambda: admin_service.weekly_comparison(start))


@router.get("/students")
def students(_: dict = Depends(require_admin)) -> list[dict]:
    return admin_service.student_options()


@router.get("/students/{client_id}/history")
def history(client_id: int, _: dict = Depends(require_admin)) -> dict:
    return admin_service.student_history(client_id)
