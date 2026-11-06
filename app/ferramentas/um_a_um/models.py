from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.ferramentas.equipe.models import Membro

HUMOR = {1: ("Muito mal", "😞"), 2: ("Desanimado(a)", "🙁"), 3: ("Neutro", "😐"), 4: ("Bem", "🙂"), 5: ("Muito bem", "😄")}
CARGA = {1: "Ociosa", 2: "Leve", 3: "Equilibrada", 4: "Pesada", 5: "Sobrecarregada"}
STATUS = {"agendada": ("Agendada", "info"), "realizada": ("Realizada", "ok"), "cancelada": ("Cancelada", "")}
RESPONSAVEIS = {"gestor": "Gestor(a)", "membro": "Liderado(a)"}


class ConfigUmAUm(Base):
    __tablename__ = "um_a_um_config"

    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), primary_key=True)
    cadencia_dias: Mapped[int] = mapped_column(Integer, default=14)
    pausado: Mapped[bool] = mapped_column(Boolean, default=False)


class Reuniao(Base):
    __tablename__ = "um_a_um_reunioes"

    id: Mapped[int] = mapped_column(primary_key=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="realizada")
    humor: Mapped[int | None] = mapped_column(Integer)
    carga: Mapped[int | None] = mapped_column(Integer)
    pauta: Mapped[str | None] = mapped_column(Text)
    anotacoes: Mapped[str | None] = mapped_column(Text)
    notas_privadas: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    membro: Mapped[Membro] = relationship(lazy="joined")
    acoes: Mapped[list["Acao"]] = relationship(back_populates="reuniao", order_by="Acao.id")
    topicos: Mapped[list["Topico"]] = relationship(back_populates="reuniao", order_by="Topico.id")

    @property
    def humor_emoji(self) -> str:
        return HUMOR.get(self.humor, ("", ""))[1]

    @property
    def humor_nome(self) -> str:
        return HUMOR.get(self.humor, ("—", ""))[0]

    @property
    def carga_nome(self) -> str:
        return CARGA.get(self.carga, "—")

    @property
    def status_nome(self) -> str:
        return STATUS[self.status][0]

    @property
    def status_cor(self) -> str:
        return STATUS[self.status][1]


class Acao(Base):
    __tablename__ = "um_a_um_acoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    reuniao_id: Mapped[int | None] = mapped_column(ForeignKey("um_a_um_reunioes.id", ondelete="SET NULL"))
    descricao: Mapped[str] = mapped_column(String(300))
    responsavel: Mapped[str] = mapped_column(String(10), default="membro")
    prazo: Mapped[date | None] = mapped_column(Date)
    concluida: Mapped[bool] = mapped_column(Boolean, default=False)
    concluida_em: Mapped[date | None] = mapped_column(Date)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    membro: Mapped[Membro] = relationship(lazy="joined")
    reuniao: Mapped[Reuniao | None] = relationship(back_populates="acoes")

    @property
    def responsavel_nome(self) -> str:
        return RESPONSAVEIS.get(self.responsavel, self.responsavel)

    @property
    def atrasada(self) -> bool:
        return not self.concluida and self.prazo is not None and self.prazo < date.today()


class Topico(Base):
    """Assunto anotado entre reuniões para levar à próxima 1:1."""
    __tablename__ = "um_a_um_topicos"

    id: Mapped[int] = mapped_column(primary_key=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    reuniao_id: Mapped[int | None] = mapped_column(ForeignKey("um_a_um_reunioes.id", ondelete="SET NULL"))
    texto: Mapped[str] = mapped_column(String(300))
    autor: Mapped[str] = mapped_column(String(10), default="gestor")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    reuniao: Mapped[Reuniao | None] = relationship(back_populates="topicos")

    @property
    def autor_nome(self) -> str:
        return RESPONSAVEIS.get(self.autor, self.autor)
