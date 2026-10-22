from pydantic import BaseModel, Field, field_validator, model_validator


DESEMPENHOS = {"Muito bom", "Bom", "Regular", "Ruim"}


class DailyAttendanceUpdate(BaseModel):
    desempenho: str = Field(max_length=40)
    teve_dor: bool = False
    descricao_dor: str = Field(default="", max_length=1000)
    observacao: str = Field(default="", max_length=3000)
    evolucao: str = Field(default="", max_length=3000)

    @field_validator("desempenho")
    @classmethod
    def validate_desempenho(cls, value: str) -> str:
        value = value.strip()
        if value not in DESEMPENHOS:
            raise ValueError("Desempenho inválido")
        return value

    @field_validator("descricao_dor", "observacao", "evolucao")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_pain(self):
        if self.teve_dor and not self.descricao_dor:
            raise ValueError("Informe a dor ou o desconforto relatado")
        if not self.teve_dor:
            self.descricao_dor = ""
        return self
