from fastapi import APIRouter, Depends, HTTPException

from ..core.security import require_admin, require_csrf
from ..schemas.crm import ContactCreate
from ..services import crm_service


router = APIRouter(prefix="/api/admin/crm", tags=["crm"])


@router.get("")
def dashboard(_: dict = Depends(require_admin)) -> dict:
    return crm_service.dashboard()


@router.post("/contacts", status_code=201)
def add_contact(data: ContactCreate, user: dict = Depends(require_csrf)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso administrativo necessário")
    return crm_service.add_contact(data)
