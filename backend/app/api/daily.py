from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from ..core.security import current_user, require_csrf, require_admin
from ..schemas.daily import DailyRecord, ActionCreate, ActionUpdate
from ..services import daily_workflow as service
from ..services import presence_service as presence

router = APIRouter(prefix='/api/daily', tags=['daily'])


def run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except service.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, 'Não foi possível consultar a carteira atual no NextFit. Tente novamente.') from exc


@router.get('/preview-info')
def preview_info(request: Request):
    return {'enabled': bool(getattr(request.app.state, 'local_demo', False))}


@router.get('')
def daily(request: Request, start: date | None = None, end: date | None = None, pending: bool = False, user=Depends(current_user)):
    today = service.now().date()
    start = start or today
    end = end or start
    if start <= today <= end: run(presence.refresh_if_due)
    result = run(service.overview, user, start, end, pending)
    result['preview'] = bool(getattr(request.app.state, 'local_demo', False))
    return result


@router.get('/analysis')
def analysis(request: Request, start: date | None = None, end: date | None = None, user=Depends(require_admin)):
    return daily(request, start, end, False, user)


@router.put('/records/{visit_id}')
def save_record(visit_id: int, data: DailyRecord, user=Depends(require_csrf)):
    return run(service.save_record, visit_id, data, user)


@router.get('/students/{client_id}/history')
def history(client_id: str, user=Depends(current_user)):
    rows, actions = run(service.records, user, service.now().date(), service.now().date(), client_id=client_id)
    return {'records': rows, 'actions': [a for a in actions if a['client_id'] == client_id]}


@router.get('/actions')
def actions(user=Depends(current_user)):
    return {'actions': run(service.actions, user), 'professors': service.professor_names()}


@router.post('/actions')
def create_action(data: ActionCreate, user=Depends(require_csrf)):
    return run(service.create_action, data, user)


@router.put('/actions/{action_id}')
def update_action(action_id: str, data: ActionUpdate, user=Depends(require_csrf)):
    return run(service.update_action, action_id, data, user)
