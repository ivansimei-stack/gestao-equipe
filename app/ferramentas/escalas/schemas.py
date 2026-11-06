from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class EscalaCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    descricao: str | None = None
    duracao_dias: int = Field(default=7, ge=1, le=31)
    apenas_dias_uteis: bool = False
    pular_ausentes: bool = True
    participantes: list[int] = []


class EscalaAtualizar(BaseModel):
    nome: str | None = Field(default=None, max_length=80)
    descricao: str | None = None
    duracao_dias: int | None = Field(default=None, ge=1, le=31)
    apenas_dias_uteis: bool | None = None
    pular_ausentes: bool | None = None
    ativa: bool | None = None


class ParticipanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    membro_id: int
    ordem: int


class EscalaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    descricao: str | None
    duracao_dias: int
    apenas_dias_uteis: bool
    pular_ausentes: bool
    ativa: bool
    participantes: list[ParticipanteOut]


class TurnoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    escala_id: int
    membro_id: int
    inicio: date
    fim: date
    origem: str
    membro_original_id: int | None
    observacao: str | None


class TurnoCriar(BaseModel):
    membro_id: int
    inicio: date
    fim: date
    observacao: str | None = None


class Gerar(BaseModel):
    de: date
    ate: date
    sobrescrever_manuais: bool = False


class GerarOut(BaseModel):
    criados: int
    mantidos: int
    pulos: list[str]
    vagos: list[date]


class Troca(BaseModel):
    membro_id: int
    observacao: str | None = None


class Permuta(BaseModel):
    outro_turno_id: int
    observacao: str | None = None
