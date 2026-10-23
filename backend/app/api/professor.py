from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.security import current_user, require_csrf
from ..schemas.professor import WeeklyUpdate
from ..services import professor_service


router = APIRouter(prefix="/api/professor", tags=["professor"])


def _bad_request(exc: Exception) -> HTTPException:
    code = 403 if isinstance(exc, PermissionError) else 400
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/week")
def get_week(
    start: str | None = None,
    professor: str | None = None,
    user: dict = Depends(current_user),
) -> dict:
    if user["role"] != "admin":
        raise HTTPException(410, "O registro semanal foi encerrado. Use o registro diário.")
    try:
        return professor_service.week_payload(user, professor, start)
    except (ValueError, PermissionError) as exc:
        raise _bad_request(exc) from exc


@router.post("/week/open")
def open_week(
    start: str = Query(...),
    professor: str | None = None,
    user: dict = Depends(require_csrf),
) -> dict:
    raise HTTPException(410, "O registro semanal foi encerrado. Use o registro diário.")


@router.put("/week/{start}/students/{client_id}")
def save_weekly_student(
    start: str,
    client_id: int,
    data: WeeklyUpdate,
    professor: str | None = None,
    user: dict = Depends(require_csrf),
) -> dict:
    raise HTTPException(410, "O registro semanal foi encerrado. Use o registro diário.")
