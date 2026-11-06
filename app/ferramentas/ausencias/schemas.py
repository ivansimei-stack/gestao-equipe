from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AusenciaCriar(BaseModel):
    membro_id: int
    tipo: str = "ferias"
    inicio: date
    fim: date
    dias_vendidos: int = Field(default=0, ge=0, le=10)
    observacao: str | None = None
    status: str = Field(default="solicitada", pattern="^(solicitada|aprovada)$")


class AusenciaAtualizar(BaseModel):
    tipo: str | None = None
    inicio: date | None = None
    fim: date | None = None
    dias_vendidos: int | None = Field(default=None, ge=0, le=10)
    observacao: str | None = None


class Decisao(BaseModel):
    motivo: str | None = None


class AusenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    membro_id: int
    tipo: str
    inicio: date
    fim: date
    status: str
    dias_vendidos: int
    observacao: str | None
    motivo_decisao: str | None
    criado_em: datetime
    decidido_em: datetime | None
    dias_corridos: int
    dias_uteis: int


class AusenciaComAvisos(AusenciaOut):
    avisos: list[str] = []


class PeriodoOut(BaseModel):
    inicio: date
    fim: date
    concessivo_fim: date
    adquirido: bool
    direito: float
    usados: int
    saldo: float
    situacao: str


class SaldoOut(BaseModel):
    membro_id: int
    disponivel: float
    solicitados: int
    proximo_limite: date | None
    situacao: str
    periodos: list[PeriodoOut]
