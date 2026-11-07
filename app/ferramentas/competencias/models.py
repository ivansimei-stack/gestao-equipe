from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.ferramentas.equipe.models import Membro

NIVEIS = {
    0: ("Não conhece", "Nunca trabalhou com isso."),
    1: ("Básico", "Conhece a teoria, precisa de orientação."),
    2: ("Intermediário", "Executa com algum apoio."),
    3: ("Avançado", "Executa sozinho(a), resolve problemas."),
    4: ("Referência", "Domina e ensina outras pessoas."),
}
NIVEL_DOMINIO = 3  # a partir daqui a pessoa "cobre" a competência

EXEMPLOS = [
    ("Técnica", "SQL e consultas", "Extrair e cruzar dados nos bancos da empresa.", 2, True),
    ("Técnica", "Excel avançado", "Tabelas dinâmicas, PROCX, Power Query.", 3, False),
    ("Técnica", "Qlik Sense", "Criar e manter painéis.", 2, True),
    ("Técnica", "Python / automação", "Scripts para automatizar rotinas.", 1, False),
    ("Processos", "Fechamento mensal", "Rotina completa de fechamento.", 2, True),
    ("Processos", "Conciliação", "Conciliação de contas e grupos.", 2, True),
    ("Processos", "Atendimento ao cliente interno", "Fila de chamados e SLA.", 2, False),
    ("Comportamental", "Comunicação com diretoria", "Apresentar resultados com clareza.", 2, False),
    ("Comportamental", "Facilitação de reuniões", "Conduzir reuniões produtivas.", 1, False),
]


class Competencia(Base):
    __tablename__ = "competencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    categoria: Mapped[str] = mapped_column(String(60), default="Geral")
    descricao: Mapped[str | None] = mapped_column(Text)
    nivel_esperado: Mapped[int] = mapped_column(Integer, default=2)
    critica: Mapped[bool] = mapped_column(Boolean, default=False)
    minimo_pessoas: Mapped[int] = mapped_column(Integer, default=2)  # alvo de pessoas com nível ≥ 3
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class NivelMembro(Base):
    __tablename__ = "competencias_niveis"
    __table_args__ = (UniqueConstraint("membro_id", "competencia_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    membro_id: Mapped[int] = mapped_column(ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    competencia_id: Mapped[int] = mapped_column(ForeignKey("competencias.id", ondelete="CASCADE"), index=True)
    nivel: Mapped[int] = mapped_column(Integer, default=0)
    interesse: Mapped[bool] = mapped_column(Boolean, default=False)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    membro: Mapped[Membro] = relationship(lazy="joined")
    competencia: Mapped[Competencia] = relationship(lazy="joined")
