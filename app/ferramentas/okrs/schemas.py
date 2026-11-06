from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class CicloCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    inicio: date
    fim: date


class CicloAtualizar(BaseModel):
    nome: str | None = Field(default=None, max_length=80)
    inicio: date | None = None
    fim: date | None = None
    arquivado: bool | None = None


class CheckinCriar(BaseModel):
    valor: float
    confianca: int | None = Field(default=None, ge=1, le=10)
    comentario: str | None = None
    data: date | None = None


class CheckinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    data: date
    valor: float
    confianca: int | None
    comentario: str | None


class KRCriar(BaseModel):
    descricao: str = Field(min_length=1, max_length=250)
    tipo: str = Field(default="numero", pattern="^(numero|percentual|moeda|binario)$")
    valor_inicial: float = 0
    valor_alvo: float = 100
    unidade: str | None = None
    responsavel_id: int | None = None


class KRAtualizar(BaseModel):
    descricao: str | None = Field(default=None, max_length=250)
    tipo: str | None = Field(default=None, pattern="^(numero|percentual|moeda|binario)$")
    valor_inicial: float | None = None
    valor_alvo: float | None = None
    unidade: str | None = None
    responsavel_id: int | None = None


class KROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    objetivo_id: int
    descricao: str
    tipo: str
    valor_inicial: float
    valor_alvo: float
    valor_atual: float
    unidade: str | None
    responsavel_id: int | None
    progresso: float = 0
    status: str = ""
    projecao: float | None = None
    checkins: list[CheckinOut] = []


class ObjetivoCriar(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    dono_id: int | None = None
    ordem: int = 0
    krs: list[KRCriar] = []


class ObjetivoAtualizar(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    descricao: str | None = None
    dono_id: int | None = None
    ordem: int | None = None


class ObjetivoOut(BaseModel):
    id: int
    ciclo_id: int
    titulo: str
    descricao: str | None
    dono_id: int | None
    progresso: float
    status: str
    krs: list[KROut]


class CicloOut(BaseModel):
    id: int
    nome: str
    inicio: date
    fim: date
    arquivado: bool
    progresso: float
    tempo_decorrido: float
    objetivos: list[ObjetivoOut] = []
