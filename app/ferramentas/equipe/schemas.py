from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MembroBase(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    email: str | None = None
    telefone: str | None = None
    cargo: str | None = None
    area: str | None = None
    data_admissao: date | None = None
    data_nascimento: date | None = None
    observacoes: str | None = None
    ativo: bool = True


class MembroCriar(MembroBase):
    pass


class MembroAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = None
    telefone: str | None = None
    cargo: str | None = None
    area: str | None = None
    data_admissao: date | None = None
    data_nascimento: date | None = None
    observacoes: str | None = None
    ativo: bool | None = None


class MembroOut(MembroBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
