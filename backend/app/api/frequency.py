import logging

from fastapi import APIRouter, Depends, HTTPException

from ..core.security import require_admin, require_csrf
from ..services import frequency_service


logger = logging.getLogger("nextfit.frequency.api")
router = APIRouter(prefix="/api/admin/frequency", tags=["frequency"])


@router.get("")
def dashboard(_: dict = Depends(require_admin)) -> dict:
    try:
        snapshot = frequency_service.read_snapshot()
    except Exception as exc:
        logger.exception("Falha ao ler o cache de frequência")
        raise HTTPException(status_code=503, detail="Não foi possível consultar os dados de frequência.") from exc
    return {"available": snapshot is not None, "snapshot": snapshot}


@router.post("/refresh")
def refresh(user: dict = Depends(require_csrf)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso administrativo necessário")
    try:
        return {"available": True, "snapshot": frequency_service.refresh_snapshot()}
    except frequency_service.RefreshInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Atualização manual de frequência falhou")
        raise HTTPException(
            status_code=503,
            detail="Não foi possível atualizar os dados. Verifique a integração com Nextfit e Google Sheets.",
        ) from exc
