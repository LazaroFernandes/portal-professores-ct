from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from ..core.security import require_admin
from ..services.finance_service import request_dashboard, TZ, month_shift

router = APIRouter(prefix='/api/admin/finance', tags=['admin'])


@router.get('')
def finance(response: Response, month: str | None = Query(None, pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),
            _: dict = Depends(require_admin)):
    response.headers['Cache-Control'] = 'no-store'
    selected = date.fromisoformat(month+'-01') if month else datetime.now(TZ).date().replace(day=1)
    today = datetime.now(TZ).date()
    if selected < month_shift(today,-36) or selected > month_shift(today,1):
        raise HTTPException(422, 'Escolha um mês entre os últimos 36 meses e o próximo mês')
    try:
        result = request_dashboard(selected)
        if result is None:
            response.status_code = 202
            response.headers['Retry-After'] = '3'
            return {'loading': True}
        return result
    except ValueError as exc:
        raise HTTPException(503, 'A consulta financeira não pôde ser conciliada. Atualize para tentar novamente; nenhum total parcial foi exibido.') from None
    except Exception:
        # Upstream exceptions may contain financial records or credentials.
        raise HTTPException(503, 'Não foi possível completar a consulta financeira do NextFit. Nenhum total parcial foi exibido. Tente novamente.') from None
