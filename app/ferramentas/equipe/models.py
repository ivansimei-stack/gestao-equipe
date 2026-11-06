from datetime import date

from sqlalchemy import Boolean, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Membro(Base):
    __tablename__ = "membros"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(120), unique=True)
    telefone: Mapped[str | None] = mapped_column(String(30))
    cargo: Mapped[str | None] = mapped_column(String(80))
    area: Mapped[str | None] = mapped_column(String(80))
    data_admissao: Mapped[date | None] = mapped_column(Date)
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def primeiro_nome(self) -> str:
        return self.nome.split()[0]

    def tempo_de_casa(self, ref: date | None = None) -> str:
        if not self.data_admissao:
            return "—"
        ref = ref or date.today()
        meses = (ref.year - self.data_admissao.year) * 12 + ref.month - self.data_admissao.month
        if ref.day < self.data_admissao.day:
            meses -= 1
        anos, meses = divmod(max(meses, 0), 12)
        partes = []
        if anos:
            partes.append(f"{anos} ano{'s' if anos > 1 else ''}")
        if meses or not anos:
            partes.append(f"{meses} {'mês' if meses == 1 else 'meses'}")
        return " e ".join(partes)
