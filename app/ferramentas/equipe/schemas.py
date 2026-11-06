from datetime import date

from pydantic import BaseModel, ConfigDict


class MembroBase(BaseModel):
    nome: str
    email: str | None = None
    cargo: str | None = None
    area: str | None = None
    data_admissao: date | None = None
    ativo: bool = True


class MembroCriar(MembroBase):
    pass


class MembroAtualizar(BaseModel):
    nome: str | None = None
    email: str | None = None
    cargo: str | None = None
    area: str | None = None
    data_admissao: date | None = None
    ativo: bool | None = None


class MembroOut(MembroBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
