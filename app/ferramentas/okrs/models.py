from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.ferramentas.equipe.models import Membro

TIPOS_KR = {"numero": "Número", "percentual": "Percentual (%)", "moeda": "Valor (R$)", "binario": "Sim / Não"}


class Ciclo(Base):
    __tablename__ = "okrs_ciclos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    arquivado: Mapped[bool] = mapped_column(Boolean, default=False)

    objetivos: Mapped[list["Objetivo"]] = relationship(back_populates="ciclo", order_by="Objetivo.ordem, Objetivo.id",
                                                       cascade="all, delete-orphan")


class Objetivo(Base):
    __tablename__ = "okrs_objetivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("okrs_ciclos.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    dono_id: Mapped[int | None] = mapped_column(ForeignKey("membros.id", ondelete="SET NULL"))
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    ciclo: Mapped[Ciclo] = relationship(back_populates="objetivos")
    dono: Mapped[Membro | None] = relationship(lazy="joined")
    krs: Mapped[list["ResultadoChave"]] = relationship(back_populates="objetivo", order_by="ResultadoChave.id",
                                                       cascade="all, delete-orphan")


class ResultadoChave(Base):
    __tablename__ = "okrs_krs"

    id: Mapped[int] = mapped_column(primary_key=True)
    objetivo_id: Mapped[int] = mapped_column(ForeignKey("okrs_objetivos.id", ondelete="CASCADE"), index=True)
    descricao: Mapped[str] = mapped_column(String(250))
    tipo: Mapped[str] = mapped_column(String(15), default="numero")
    valor_inicial: Mapped[float] = mapped_column(Float, default=0)
    valor_alvo: Mapped[float] = mapped_column(Float, default=100)
    valor_atual: Mapped[float] = mapped_column(Float, default=0)
    unidade: Mapped[str | None] = mapped_column(String(20))
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("membros.id", ondelete="SET NULL"))

    objetivo: Mapped[Objetivo] = relationship(back_populates="krs")
    responsavel: Mapped[Membro | None] = relationship(lazy="joined")
    checkins: Mapped[list["Checkin"]] = relationship(back_populates="kr", order_by="Checkin.data, Checkin.id",
                                                     cascade="all, delete-orphan")

    def formatar(self, v: float | None) -> str:
        if v is None:
            return "—"
        if self.tipo == "binario":
            return "Sim" if v >= 1 else "Não"
        txt = f"{v:,.2f}".rstrip("0").rstrip(".") if not float(v).is_integer() else f"{int(v):,}"
        txt = txt.replace(",", "X").replace(".", ",").replace("X", ".")
        if self.tipo == "moeda":
            return f"R$ {txt}"
        if self.tipo == "percentual":
            return f"{txt}%"
        return f"{txt} {self.unidade}" if self.unidade else txt


class Checkin(Base):
    __tablename__ = "okrs_checkins"

    id: Mapped[int] = mapped_column(primary_key=True)
    kr_id: Mapped[int] = mapped_column(ForeignKey("okrs_krs.id", ondelete="CASCADE"), index=True)
    data: Mapped[date] = mapped_column(Date)
    valor: Mapped[float] = mapped_column(Float)
    confianca: Mapped[int | None] = mapped_column(Integer)  # 1–10
    comentario: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    kr: Mapped[ResultadoChave] = relationship(back_populates="checkins")
