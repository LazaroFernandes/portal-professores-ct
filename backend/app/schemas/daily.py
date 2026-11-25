from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator, ConfigDict


class DailyRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    contact: Literal['accompanied', 'not_observed']
    performance_score: int | None = Field(default=None, ge=0, le=10)
    outcome: Literal['completed', 'adapted', 'interrupted', 'unknown'] | None = None
    pain: Literal['no', 'yes', 'unknown'] | None = None
    note: str = Field(default='', max_length=3000)
    follow_up: bool
    version: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def validate_record(self):
        if self.contact == 'accompanied' and ((self.performance_score is None and not self.outcome) or not self.pain):
            raise ValueError('Informe o desempenho de 0 a 10 e se houve desconforto relatado.')
        if self.contact == 'not_observed':
            self.performance_score = None
            self.outcome = None
            self.pain = None
        return self


class ActionUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=1)
    status: Literal['review', 'in_progress', 'resolved']
    assigned_to: str = Field(min_length=1, max_length=200)
    due_date: date | None = None
    priority: Literal['normal', 'high']
    instruction: str = Field(default='', max_length=3000)
    result: str = Field(default='', max_length=3000)

    @model_validator(mode='after')
    def validate_resolution(self):
        if self.status == 'in_progress' and (not self.due_date or not self.instruction):
            raise ValueError('Defina prazo e orientação antes de iniciar a ação.')
        if self.status == 'resolved' and not self.result:
            raise ValueError('Descreva o resultado antes de resolver a ação.')
        return self


class ActionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    visit_id: int = Field(gt=0)
    title: str = Field(min_length=3, max_length=500)
