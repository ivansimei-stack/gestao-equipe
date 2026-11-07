from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.ferramentas.equipe.models import Membro

STATUS_CICLO = {"aberto": ("Aberto", "info"), "calibracao": ("Em calibração", "alerta"), "encerrado": ("Encerrado", "")}
TIPOS_AVALIACAO = {"auto": "Autoavaliação", "gestor": "Avaliação do gestor"}
ESCALA = {1: "Muito abaixo do esperado", 2: "Abaixo do esperado", 3: "Atende ao esperado",
          4: "Acima do esperado", 5: "Excepcional"}
POTENCIAL = {1: "Baixo", 2: "Médio", 3: "Alto"}
TIPOS_FEEDBACK = {"reconhecimento": ("Reconhecimento", "ok"), "construtivo": ("Ponto de melhoria", "alerta")}

CRITERIOS_PADRAO = [
    ("Entrega de resultados", "Cumpre metas e prazos com consistência.", 2.0),
    ("Qualidade técnica", "Domínio técnico e qualidade do trabalho entregue.", 1.5),
    ("Colaboração", "Trabalha bem em equipe e apoia os colegas.", 1.0),
    ("Comunicação", "Clareza, transparência e escuta ativa.", 1.0),
    ("Autonomia e proatividade", "Antecipa problemas e propõe soluções.", 1.0),
    ("Aprendizado contínuo", "Busca se desenvolver e compartilha conhecimento.", 1.0),
]


class CicloAvaliacao(Base):
    __tablename__ = "avaliacoes_ciclos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    inicio: Mapped[date] = mapped_column(Date)  # período avaliado
    fim: Mapped[date] = mapped_column(Date)
    prazo: Mapped[date | None] = mapped_column(Date)  # prazo para preencher
    status: Mapped[str] = mapped_column(String(15), default="aberto")

    criterios: Mapped[list["Criterio"]] = relationship(back_populates="ciclo", order_by="Criterio.ordem, Criterio.id",
                                                       cascade="all, delete-orphan")
    avaliacoes: Mapped[list["Avaliacao"]] = relationship(back_populates="ciclo", cascade="all, delete-orphan")

    @property
    def status_nome(self) -> str:
        return STATUS_CICLO[self.status][0]

    @property
    def status_cor(self) -> str:
        return STATUS_CICLO[self.status][1]


class Criterio(Base):
    __tablename__ = "avaliacoes_criterios"

    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes_ciclos.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(100))
    descricao: Mapped[str | None] = mapped_column(Text)
    peso: Mapped[float] = mapped_column(Float, default=1.0)
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    ciclo: Mapped[CicloAvaliacao] = relationship(back_populates="criterios")


class Avaliacao(Base):
    __tablename__ = "avaliacoes"
    __table_args__ = (UniqueConstraint("ciclo_id", "membro_id", "tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes_ciclos.id", ondelete="CASCADE"), index=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))  # auto | gestor
    status: Mapped[str] = mapped_column(String(10), default="rascunho")  # rascunho | enviada
    pontos_fortes: Mapped[str | None] = mapped_column(Text)
    a_desenvolver: Mapped[str | None] = mapped_column(Text)
    comentario: Mapped[str | None] = mapped_column(Text)
    potencial: Mapped[int | None] = mapped_column(Integer)  # só gestor: 1–3
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime)

    ciclo: Mapped[CicloAvaliacao] = relationship(back_populates="avaliacoes")
    membro: Mapped[Membro] = relationship(lazy="joined")
    notas: Mapped[list["Nota"]] = relationship(back_populates="avaliacao", cascade="all, delete-orphan")

    def nota_de(self, criterio_id: int):
        return next((n for n in self.notas if n.criterio_id == criterio_id), None)


class Nota(Base):
    __tablename__ = "avaliacoes_notas"
    __table_args__ = (UniqueConstraint("avaliacao_id", "criterio_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes.id", ondelete="CASCADE"), index=True)
    criterio_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes_criterios.id", ondelete="CASCADE"))
    nota: Mapped[int | None] = mapped_column(Integer)
    comentario: Mapped[str | None] = mapped_column(Text)

    avaliacao: Mapped[Avaliacao] = relationship(back_populates="notas")


class Feedback(Base):
    """Feedback contínuo: registros ao longo do ano que viram evidência na avaliação."""
    __tablename__ = "avaliacoes_feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    tipo: Mapped[str] = mapped_column(String(20), default="reconhecimento")
    texto: Mapped[str] = mapped_column(Text)
    compartilhado: Mapped[bool] = mapped_column(Boolean, default=True)  # já foi dado à pessoa?
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    membro: Mapped[Membro] = relationship(lazy="joined")

    @property
    def tipo_nome(self) -> str:
        return TIPOS_FEEDBACK[self.tipo][0]

    @property
    def tipo_cor(self) -> str:
        return TIPOS_FEEDBACK[self.tipo][1]


class ItemPDI(Base):
    """Plano de Desenvolvimento Individual."""
    __tablename__ = "avaliacoes_pdi"

    id: Mapped[int] = mapped_column(primary_key=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    ciclo_id: Mapped[int | None] = mapped_column(ForeignKey("avaliacoes_ciclos.id", ondelete="SET NULL"))
    descricao: Mapped[str] = mapped_column(String(300))
    tipo: Mapped[str] = mapped_column(String(20), default="pratica")  # 70-20-10
    prazo: Mapped[date | None] = mapped_column(Date)
    concluido: Mapped[bool] = mapped_column(Boolean, default=False)
    concluido_em: Mapped[date | None] = mapped_column(Date)

    membro: Mapped[Membro] = relationship(lazy="joined")

    @property
    def atrasado(self) -> bool:
        return not self.concluido and self.prazo is not None and self.prazo < date.today()


TIPOS_PDI = {"pratica": "Prática no trabalho (70%)", "social": "Mentoria / troca (20%)", "formal": "Curso / formal (10%)"}
