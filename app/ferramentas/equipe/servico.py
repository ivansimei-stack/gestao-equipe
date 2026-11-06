from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ferramentas.equipe.models import Membro


def membros(db: Session, apenas_ativos: bool = False, area: str | None = None) -> list[Membro]:
    q = select(Membro).order_by(Membro.nome)
    if apenas_ativos:
        q = q.where(Membro.ativo.is_(True))
    if area:
        q = q.where(Membro.area == area)
    return list(db.scalars(q))


def obter_membro(db: Session, membro_id: int) -> Membro:
    m = db.get(Membro, membro_id)
    if not m:
        raise HTTPException(404, "Membro não encontrado")
    return m


def areas(db: Session) -> list[str]:
    return sorted(a for a in db.scalars(select(Membro.area).distinct()) if a)


def salvar(db: Session, membro: Membro) -> Membro:
    db.add(membro)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe um membro com este e-mail")
    return membro


def aniversariantes(db: Session, dias: int = 30, ref: date | None = None) -> list[tuple[Membro, date]]:
    ref = ref or date.today()
    res = []
    for m in membros(db, apenas_ativos=True):
        if not m.data_nascimento:
            continue
        for ano in (ref.year, ref.year + 1):
            try:
                d = m.data_nascimento.replace(year=ano)
            except ValueError:  # 29/02
                d = date(ano, 3, 1)
            if ref <= d <= ref + timedelta(days=dias):
                res.append((m, d))
                break
    return sorted(res, key=lambda x: x[1])


def aniversarios_de_empresa(db: Session, dias: int = 30, ref: date | None = None) -> list[tuple[Membro, date, int]]:
    ref = ref or date.today()
    res = []
    for m in membros(db, apenas_ativos=True):
        if not m.data_admissao:
            continue
        for ano in (ref.year, ref.year + 1):
            try:
                d = m.data_admissao.replace(year=ano)
            except ValueError:
                d = date(ano, 3, 1)
            anos = ano - m.data_admissao.year
            if anos > 0 and ref <= d <= ref + timedelta(days=dias):
                res.append((m, d, anos))
                break
    return sorted(res, key=lambda x: x[1])
