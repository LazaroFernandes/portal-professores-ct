from datetime import date,datetime,timedelta
from fastapi import APIRouter,Depends,HTTPException,Response,Query
from ..core.security import require_admin
from ..services.flow_analysis import overview,TIMEZONE
router=APIRouter(prefix='/api/admin/flow',tags=['admin'])
@router.get('')
def flow(response:Response,start:date,end:date,stay:int=Query(90),user=Depends(require_admin)):
    response.headers['Cache-Control']='no-store'
    if stay not in (60,90): raise HTTPException(422,'Escolha permanência de 60 ou 90 minutos.')
    if start>end or (end-start).days>61 or end>=datetime.now(TIMEZONE).date(): raise HTTPException(422,'Selecione até 62 dias completos, com término até ontem.')
    try: return overview(start,end,stay)
    except Exception: raise HTTPException(503,'Não foi possível concluir a consulta ao NEXT ou à escala. Nenhum zero deve ser interpretado como dado confirmado. Tente atualizar.') from None
