import json
import os
from datetime import time
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from nextfit_client import NextFitClient
from ..core.security import require_admin, require_csrf
from ..services.presence_service import _store

router = APIRouter(prefix='/api/admin/schedule', tags=['admin'])
KEY = 'teacher_schedule_v1'

class Shift(BaseModel):
    day: int = Field(ge=0, le=6)
    start: time
    end: time
    @model_validator(mode='after')
    def valid_interval(self):
        if self.end <= self.start:
            raise ValueError('O término deve ser posterior ao início no mesmo dia.')
        return self

class Teacher(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    source: str
    rate: float = Field(ge=0, le=100000, allow_inf_nan=False)
    shifts: list[Shift] = Field(max_length=200)
    @model_validator(mode='after')
    def no_overlaps(self):
        for day in range(7):
            shifts = sorted((s for s in self.shifts if s.day == day), key=lambda s: s.start)
            if any(a.end > b.start for a, b in zip(shifts, shifts[1:])):
                raise ValueError('Há horários sobrepostos para o mesmo professor.')
        return self

    @field_validator('source')
    @classmethod
    def source_valid(cls, value):
        if value not in ('nextfit', 'test'): raise ValueError('Origem inválida')
        return value

class Schedule(BaseModel):
    teachers: list[Teacher] = Field(max_length=200)
    @model_validator(mode='after')
    def unique_ids(self):
        if len({t.id for t in self.teachers}) != len(self.teachers): raise ValueError('Professor duplicado')
        return self

@router.get('')
def get_schedule(response: Response, user=Depends(require_admin)):
    response.headers['Cache-Control'] = 'no-store'
    value = _store().state(KEY)
    return json.loads(value) if value else {'teachers': []}

@router.put('')
def save_schedule(data: Schedule, response: Response, user=Depends(require_admin), csrf=Depends(require_csrf)):
    response.headers['Cache-Control'] = 'no-store'
    value = data.model_dump(mode='json')
    _store().set_state(KEY, json.dumps(value, ensure_ascii=False))
    return value

@router.get('/users')
def nextfit_users(response: Response, user=Depends(require_admin)):
    response.headers['Cache-Control'] = 'no-store'
    key, base = os.environ.get('NEXTFIT_API_KEY', '').strip(), os.environ.get('NEXTFIT_BASE_URL', '').strip()
    if not key or not base: raise HTTPException(503, 'Conexão com o NextFit não configurada.')
    try:
        users = NextFitClient(key, base, os.environ.get('NEXTFIT_API_VERSION', '1')).usuarios()
        return {'users': sorted([{'id': str(u['id']), 'name': str(u['nome']).strip()} for u in users if u.get('id') is not None and u.get('nome') and not u.get('inativo')], key=lambda u: u['name'].casefold())}
    except Exception:
        raise HTTPException(503, 'Não foi possível consultar os usuários do NextFit. Tente novamente.') from None
