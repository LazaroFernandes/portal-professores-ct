from fastapi import APIRouter, Depends, HTTPException

from ..core.security import require_admin, require_csrf
from ..schemas.monday import TaskCreate, TaskToggle
from ..services import monday_service


router = APIRouter(prefix="/api/admin/monday", tags=["monday"])


@router.get("")
def dashboard(_: dict = Depends(require_admin)) -> dict:
    return monday_service.load_snapshot()


@router.post("/refresh")
def refresh(_: dict = Depends(require_csrf)) -> dict:
    try:
        return monday_service.refresh_snapshot()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.put("/tasks/auto/{task_id}")
def toggle_auto(task_id: str, data: TaskToggle, user: dict = Depends(require_csrf)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso administrativo necessário")
    return monday_service.toggle_auto(task_id, data.done)


@router.post("/tasks/manual", status_code=201)
def add_manual(data: TaskCreate, user: dict = Depends(require_csrf)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso administrativo necessário")
    return monday_service.add_manual(data.text)


@router.put("/tasks/manual/{task_id}")
def toggle_manual(task_id: str, data: TaskToggle, user: dict = Depends(require_csrf)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso administrativo necessário")
    try:
        return monday_service.toggle_manual(task_id, data.done)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/tasks/manual/{task_id}")
def delete_manual(task_id: str, user: dict = Depends(require_csrf)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso administrativo necessário")
    try:
        return monday_service.delete_manual(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
