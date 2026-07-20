from pydantic import BaseModel, Field, field_validator


TURNOS = {"", "MANHÃ", "TARDE", "NOITE"}
DESEMPENHOS = {"", "Muito bom", "Bom", "Regular", "Não está vindo", "Férias"}


class WeeklyUpdate(BaseModel):
    frequencia: str = Field(default="", max_length=80)
    desempenho: str = Field(default="", max_length=40)
    relato: str = Field(default="", max_length=3000)
    turno: str = Field(default="", max_length=30)

    @field_validator("desempenho")
    @classmethod
    def validate_desempenho(cls, value: str) -> str:
        value = value.strip()
        if value not in DESEMPENHOS:
            raise ValueError("Desempenho inválido")
        return value

    @field_validator("turno")
    @classmethod
    def validate_turno(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in TURNOS:
            raise ValueError("Turno inválido")
        return value

    @field_validator("frequencia", "relato")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()
