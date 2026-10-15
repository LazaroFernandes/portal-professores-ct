from datetime import date
import logging

from fastapi import APIRouter, Depends, HTTPException

from ..core.security import require_admin
from ..services.professor_analysis import weekly_analysis


router = APIRouter(prefix="/api/admin/professors", tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/analysis")
def analysis(start: date | None = None, _: dict = Depends(require_admin)) -> dict:
    try:
        return weekly_analysis(start)
    except Exception as exc:
        logger.exception("Não foi possível ler o acompanhamento dos professores")
        raise HTTPException(status_code=503, detail="A base de acompanhamento está indisponível. Tente novamente.") from exc
