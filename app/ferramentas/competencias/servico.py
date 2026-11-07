"""Matriz de competências: fator ônibus, lacunas, riscos com ausências e mentorias."""
from dataclasses import dataclass, field
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ferramentas.ausencias import servico as ausencias
from app.ferramentas.competencias.models import NIVEL_DOMINIO, Competencia, NivelMembro
from app.ferramentas.equipe import servico as equipe
from app.ferramentas.equipe.models import Membro
from app.util import dias, eh_dia_util


def competencias(db: Session, apenas_ativas: bool = True, categoria: str | None = None) -> list[Competencia]:
    q = select(Competencia).order_by(Competencia.categoria, Competencia.nome)
    if apenas_ativas:
        q = q.where(Competencia.ativa.is_(True))
    if categoria:
        q = q.where(Competencia.categoria == categoria)
    return list(db.scalars(q))


def categorias(db: Session) -> list[str]:
    return sorted({c.categoria for c in competencias(db)})


def obter(db: Session, competencia_id: int) -> Competencia:
    c = db.get(Competencia, competencia_id)
    if not c:
        raise HTTPException(404, "Competência não encontrada")
    return c


def validar(c: Competencia) -> None:
    if not (c.nome or "").strip():
        raise HTTPException(422, "Informe o nome da competência.")
    if not 0 <= c.nivel_esperado <= 4:
        raise HTTPException(422, "Nível esperado deve ser de 0 a 4.")
    if not 1 <= c.minimo_pessoas <= 20:
        raise HTTPException(422, "Mínimo de pessoas deve ser de 1 a 20.")


def niveis(db: Session, membro_id: int | None = None) -> dict[tuple[int, int], NivelMembro]:
    q = select(NivelMembro)
    if membro_id:
        q = q.where(NivelMembro.membro_id == membro_id)
    return {(n.membro_id, n.competencia_id): n for n in db.scalars(q).unique()}


def definir(db: Session, membro_id: int, competencia_id: int, nivel: int | None = None,
            interesse: bool | None = None, commit: bool = True) -> NivelMembro:
    if nivel is not None and not 0 <= nivel <= 4:
        raise HTTPException(422, "Nível deve ser de 0 a 4.")
    n = db.scalar(select(NivelMembro).where(NivelMembro.membro_id == membro_id,
                                            NivelMembro.competencia_id == competencia_id))
    if not n:
        n = NivelMembro(membro_id=membro_id, competencia_id=competencia_id, nivel=0, interesse=False)
        db.add(n)
    if nivel is not None:
        n.nivel = nivel
    if interesse is not None:
        n.interesse = interesse
    if commit:
        db.commit()
    return n


@dataclass
class Analise:
    competencia: Competencia
    detentores: list[Membro]          # nível ≥ 3
    referencias: list[Membro]         # nível 4
    interessados: list[Membro]        # interesse e nível < 3
    media: float
    maximo: int
    dias_descobertos: list[date] = field(default_factory=list)

    @property
    def fator_onibus(self) -> int:
        return len(self.detentores)

    @property
    def risco(self) -> str:
        n, alvo = self.fator_onibus, self.competencia.minimo_pessoas
        if n == 0:
            return "sem_cobertura"
        if n < alvo and (self.competencia.critica or n == 1):
            return "alto"
        if n < alvo:
            return "medio"
        return "ok"


RISCOS = {"sem_cobertura": ("Sem ninguém", "risco"), "alto": ("Risco alto", "risco"),
          "medio": ("Atenção", "alerta"), "ok": ("Coberta", "ok")}


def analisar(db: Session, dias_frente: int = 30, area: str | None = None) -> list[Analise]:
    membros = equipe.membros(db, apenas_ativos=True, area=area)
    mapa = niveis(db)
    hoje = date.today()
    ausentes_por_dia: dict[date, set[int]] = {}
    for d in dias(hoje, hoje + timedelta(days=dias_frente)):
        if eh_dia_util(d):
            ausentes_por_dia[d] = {a.membro_id for a in ausencias.ausentes_em(db, d, incluir_solicitadas=True)}
    res = []
    for c in competencias(db):
        nv = {m.id: (mapa.get((m.id, c.id)).nivel if mapa.get((m.id, c.id)) else 0) for m in membros}
        det = [m for m in membros if nv[m.id] >= NIVEL_DOMINIO]
        a = Analise(
            competencia=c, detentores=det, referencias=[m for m in membros if nv[m.id] == 4],
            interessados=[m for m in membros if mapa.get((m.id, c.id)) and mapa[(m.id, c.id)].interesse
                          and nv[m.id] < NIVEL_DOMINIO],
            media=round(sum(nv.values()) / len(nv), 2) if nv else 0, maximo=max(nv.values(), default=0))
        if c.critica and det:
            ids = {m.id for m in det}
            a.dias_descobertos = [d for d, fora in ausentes_por_dia.items() if ids <= fora]
        res.append(a)
    return res


def perfil_membro(db: Session, membro: Membro) -> list[dict]:
    mapa = niveis(db, membro.id)
    linhas = []
    for c in competencias(db):
        n = mapa.get((membro.id, c.id))
        nivel = n.nivel if n else 0
        linhas.append({"c": c, "nivel": nivel, "interesse": bool(n and n.interesse),
                       "gap": max(0, c.nivel_esperado - nivel)})
    return linhas


def mentorias(analises: list[Analise], db: Session) -> list[dict]:
    """Sugere pares mentor → aprendiz para competências em risco (ou com interessados)."""
    mapa = niveis(db)
    sugestoes = []
    for a in analises:
        if not a.detentores:
            continue
        aprendizes = list(a.interessados)
        if a.risco in ("alto", "medio") and not aprendizes:
            # sem interessados: sugere quem já está mais perto (nível 2)
            aprendizes = [m for m in equipe.membros(db, apenas_ativos=True)
                          if (mapa.get((m.id, a.competencia.id)).nivel if mapa.get((m.id, a.competencia.id)) else 0) == 2]
        mentores = a.referencias or a.detentores
        for i, ap in enumerate(aprendizes[:3]):
            mentor = mentores[i % len(mentores)]
            sugestoes.append({"competencia": a.competencia, "mentor": mentor, "aprendiz": ap, "risco": a.risco,
                              "interesse": ap in a.interessados})
    ordem = {"sem_cobertura": 0, "alto": 1, "medio": 2, "ok": 3}
    sugestoes.sort(key=lambda s: (ordem[s["risco"]], not s["interesse"], s["competencia"].nome))
    return sugestoes


def criar_exemplos(db: Session) -> int:
    from app.ferramentas.competencias.models import EXEMPLOS
    existentes = {c.nome for c in competencias(db, apenas_ativas=False)}
    n = 0
    for cat, nome, desc, esperado, critica in EXEMPLOS:
        if nome not in existentes:
            db.add(Competencia(categoria=cat, nome=nome, descricao=desc, nivel_esperado=esperado, critica=critica,
                               minimo_pessoas=2))
            n += 1
    db.commit()
    return n
