from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AcaoNova(BaseModel):
    descricao: str = Field(min_length=1, max_length=300)
    responsavel: str = Field(default="membro", pattern="^(gestor|membro)$")
    prazo: date | None = None


class AcaoCriar(AcaoNova):
    membro_id: int


class AcaoAtualizar(BaseModel):
    descricao: str | None = Field(default=None, max_length=300)
    responsavel: str | None = Field(default=None, pattern="^(gestor|membro)$")
    prazo: date | None = None
    concluida: bool | None = None


class AcaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    membro_id: int
    reuniao_id: int | None
    descricao: str
    responsavel: str
    prazo: date | None
    concluida: bool
    concluida_em: date | None
    atrasada: bool


class TopicoCriar(BaseModel):
    membro_id: int
    texto: str = Field(min_length=1, max_length=300)
    autor: str = Field(default="gestor", pattern="^(gestor|membro)$")


class TopicoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    membro_id: int
    reuniao_id: int | None
    texto: str
    autor: str
    criado_em: datetime


class ReuniaoCriar(BaseModel):
    membro_id: int
    data: date
    status: str = Field(default="realizada", pattern="^(agendada|realizada|cancelada)$")
    humor: int | None = Field(default=None, ge=1, le=5)
    carga: int | None = Field(default=None, ge=1, le=5)
    pauta: str | None = None
    anotacoes: str | None = None
    notas_privadas: str | None = None
    novas_acoes: list[AcaoNova] = []
    concluir_acoes: list[int] = []
    topicos_discutidos: list[int] = []


class ReuniaoAtualizar(BaseModel):
    data: date | None = None
    status: str | None = Field(default=None, pattern="^(agendada|realizada|cancelada)$")
    humor: int | None = Field(default=None, ge=1, le=5)
    carga: int | None = Field(default=None, ge=1, le=5)
    pauta: str | None = None
    anotacoes: str | None = None
    notas_privadas: str | None = None


class ReuniaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    membro_id: int
    data: date
    status: str
    humor: int | None
    carga: int | None
    pauta: str | None
    anotacoes: str | None
    notas_privadas: str | None
    acoes: list[AcaoOut] = []
    topicos: list[TopicoOut] = []


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    membro_id: int
    cadencia_dias: int
    pausado: bool


class ConfigAtualizar(BaseModel):
    cadencia_dias: int | None = Field(default=None, ge=1, le=120)
    pausado: bool | None = None


class SituacaoOut(BaseModel):
    membro_id: int
    nome: str
    estado: str
    cadencia: int
    ultima: date | None
    proxima: date | None
    dias_atraso: int
    humores: list[int]
    cargas: list[int]
    acoes_abertas: int
    acoes_atrasadas: int
    topicos: int
