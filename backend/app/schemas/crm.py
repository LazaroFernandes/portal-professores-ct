from pydantic import BaseModel, Field, field_validator


CONTACT_STATUSES = {
    "Pendente",
    "Falou - vai voltar",
    "Falou - cancelou",
    "Sem resposta",
    "Outro",
}


class ContactCreate(BaseModel):
    client_id: int
    client_name: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=80)
    status: str = Field(max_length=80)
    notes: str = Field(default="", max_length=2000)
    operator: str = Field(min_length=1, max_length=120)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in CONTACT_STATUSES:
            raise ValueError("Status de contato inválido")
        return value
