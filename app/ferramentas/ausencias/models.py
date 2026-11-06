from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.ferramentas.equipe.models import Membro

TIPOS = {
    "ferias": ("Férias", "c1"),
    "folga": ("Folga / day off", "c2"),
    "abono": ("Abono / banco de horas", "c6"),
    "licenca_medica": ("Licença médica", "c5"),
    "licenca_parental": ("Licença maternidade/paternidade", "c4"),
    "treinamento": ("Treinamento / evento", "c3"),
    "outro": ("Outro", "c6"),
}
STATUS = {
    "solicitada": ("Solicitada", "alerta"),
    "aprovada": ("Aprovada", "ok"),
    "recusada": ("Recusada", "risco"),
    "cancelada": ("Cancelada", ""),
}
STATUS_ATIVOS = ("solicitada", "aprovada")


class Ausencia(Base):
    __tablename__ = "ausencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(30), default="ferias")
    inicio: Mapped[date] = mapped_column(Date, index=True)
    fim: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="solicitada")
    dias_vendidos: Mapped[int] = mapped_column(Integer, default=0)  # abono pecuniário (até 10)
    observacao: Mapped[str | None] = mapped_column(Text)
    motivo_decisao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime)

    membro: Mapped[Membro] = relationship(lazy="joined")

    @property
    def tipo_nome(self) -> str:
        return TIPOS.get(self.tipo, (self.tipo, ""))[0]

    @property
    def tipo_cor(self) -> str:
        return TIPOS.get(self.tipo, ("", "c6"))[1]

    @property
    def status_nome(self) -> str:
        return STATUS.get(self.status, (self.status, ""))[0]

    @property
    def status_cor(self) -> str:
        return STATUS.get(self.status, ("", ""))[1]

    @property
    def dias_corridos(self) -> int:
        return (self.fim - self.inicio).days + 1

    @property
    def dias_uteis(self) -> int:
        from app.util import dias_uteis
        return dias_uteis(self.inicio, self.fim)


class RegraCobertura(Base):
    """Mínimo de pessoas presentes por área (para detectar conflitos)."""
    __tablename__ = "ausencias_regras_cobertura"

    area: Mapped[str] = mapped_column(String(80), primary_key=True)
    minimo_presentes: Mapped[int] = mapped_column(Integer, default=1)
