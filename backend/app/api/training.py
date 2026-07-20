from fastapi import APIRouter, Depends

from ..core.security import require_admin
from ..services import training_service


router = APIRouter(prefix="/api/admin/training", tags=["training"])


@router.get("/students")
def students(_: dict = Depends(require_admin)) -> list[dict]:
    return training_service.students()


@router.get("/students/{client_id}")
def student(client_id: int, _: dict = Depends(require_admin)) -> dict:
    return training_service.student_detail(client_id)
