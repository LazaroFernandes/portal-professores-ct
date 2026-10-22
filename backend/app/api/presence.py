from fastapi import APIRouter, Depends, HTTPException

from ..core.security import current_user, require_csrf
from ..schemas.presence import DailyAttendanceUpdate
from ..services import presence_service


router = APIRouter(prefix="/api/presence", tags=["presence"])


@router.get("")
def current_presence(user: dict = Depends(current_user)) -> dict:
    try:
        return presence_service.current_payload(user=user)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Não foi possível consultar a carteira atual no NextFit.") from exc


@router.get("/pending")
def pending_presence(user: dict = Depends(current_user)) -> dict:
    try:
        return presence_service.pending_payload(user=user)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Não foi possível consultar a carteira atual no NextFit.") from exc


@router.get("/{visit_id}/training")
def training_detail(
    visit_id: int,
    user: dict = Depends(current_user),
) -> dict:
    try:
        return presence_service.training_detail_for_visit(visit_id, user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{visit_id}/attendance")
def save_attendance(
    visit_id: int,
    data: DailyAttendanceUpdate,
    user: dict = Depends(require_csrf),
) -> dict:
    if not presence_service.finalize_attendance(visit_id, data, user):
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    return {"saved": True, "status": "ATENDIMENTO FINALIZADO"}
