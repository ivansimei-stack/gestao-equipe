from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.ferramentas.equipe.models import Membro

ORIGENS = {"gerado": ("Automático", ""), "manual": ("Manual", "info"), "troca": ("Troca", "alerta")}


class Escala(Base):
    __tablename__ = "escalas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    descricao: Mapped[str | None] = mapped_column(Text)
    duracao_dias: Mapped[int] = mapped_column(Integer, default=7)  # 1 = diária, 7 = semanal...
    apenas_dias_uteis: Mapped[bool] = mapped_column(Boolean, default=False)  # só p/ escalas diárias
    pular_ausentes: Mapped[bool] = mapped_column(Boolean, default=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    participantes: Mapped[list["Participante"]] = relationship(
        back_populates="escala", order_by="Participante.ordem, Participante.id", cascade="all, delete-orphan")
    turnos: Mapped[list["Turno"]] = relationship(back_populates="escala", order_by="Turno.inicio",
                                                 cascade="all, delete-orphan")

    @property
    def periodicidade(self) -> str:
        return {1: "Diária", 7: "Semanal", 14: "Quinzenal"}.get(self.duracao_dias, f"A cada {self.duracao_dias} dias")


class Participante(Base):
    __tablename__ = "escalas_participantes"
    __table_args__ = (UniqueConstraint("escala_id", "membro_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    escala_id: Mapped[int] = mapped_column(ForeignKey("escalas.id", ondelete="CASCADE"), index=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"))
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    escala: Mapped[Escala] = relationship(back_populates="participantes")
    membro: Mapped[Membro] = relationship(lazy="joined")


class Turno(Base):
    __tablename__ = "escalas_turnos"

    id: Mapped[int] = mapped_column(primary_key=True)
    escala_id: Mapped[int] = mapped_column(ForeignKey("escalas.id", ondelete="CASCADE"), index=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    inicio: Mapped[date] = mapped_column(Date, index=True)
    fim: Mapped[date] = mapped_column(Date)
    origem: Mapped[str] = mapped_column(String(10), default="gerado")
    membro_original_id: Mapped[int | None] = mapped_column(ForeignKey("membros.id", ondelete="SET NULL"))
    observacao: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    escala: Mapped[Escala] = relationship(back_populates="turnos")
    membro: Mapped[Membro] = relationship(foreign_keys=[membro_id], lazy="joined")
    membro_original: Mapped[Membro | None] = relationship(foreign_keys=[membro_original_id], lazy="joined")

    @property
    def origem_nome(self) -> str:
        return ORIGENS.get(self.origem, (self.origem, ""))[0]

    @property
    def origem_cor(self) -> str:
        return ORIGENS.get(self.origem, ("", ""))[1]
