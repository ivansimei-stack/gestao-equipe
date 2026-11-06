from dataclasses import dataclass, field
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.ferramentas.equipe import servico as equipe
from app.ferramentas.equipe.models import Membro
from app.ferramentas.um_a_um.models import Acao, ConfigUmAUm, Reuniao, Topico

CADENCIA_PADRAO = 14


def config(db: Session, membro_id: int) -> ConfigUmAUm:
    c = db.get(ConfigUmAUm, membro_id)
    if not c:
        c = ConfigUmAUm(membro_id=membro_id, cadencia_dias=CADENCIA_PADRAO, pausado=False)
        db.add(c)
        db.flush()
    return c


def reunioes(db: Session, membro_id: int | None = None, status: str | None = None,
             de: date | None = None, ate: date | None = None) -> list[Reuniao]:
    q = select(Reuniao).order_by(Reuniao.data.desc(), Reuniao.id.desc())
    if membro_id:
        q = q.where(Reuniao.membro_id == membro_id)
    if status:
        q = q.where(Reuniao.status.in_(status.split(",")))
    if de:
        q = q.where(Reuniao.data >= de)
    if ate:
        q = q.where(Reuniao.data <= ate)
    return list(db.scalars(q).unique())


def obter_reuniao(db: Session, reuniao_id: int) -> Reuniao:
    r = db.get(Reuniao, reuniao_id)
    if not r:
        raise HTTPException(404, "Reunião não encontrada")
    return r


def acoes(db: Session, membro_id: int | None = None, abertas: bool | None = None,
          responsavel: str | None = None) -> list[Acao]:
    q = select(Acao).join(Acao.membro).where(Membro.ativo.is_(True) if membro_id is None else true())
    if membro_id:
        q = q.where(Acao.membro_id == membro_id)
    if abertas is not None:
        q = q.where(Acao.concluida.is_(not abertas))
    if responsavel:
        q = q.where(Acao.responsavel == responsavel)
    lista = list(db.scalars(q).unique())
    lista.sort(key=lambda a: (a.concluida, a.prazo or date.max, a.id))
    return lista


def obter_acao(db: Session, acao_id: int) -> Acao:
    a = db.get(Acao, acao_id)
    if not a:
        raise HTTPException(404, "Ação não encontrada")
    return a


def concluir_acao(a: Acao, concluida: bool = True) -> Acao:
    a.concluida = concluida
    a.concluida_em = date.today() if concluida else None
    return a


def topicos_pendentes(db: Session, membro_id: int) -> list[Topico]:
    return list(db.scalars(select(Topico).where(Topico.membro_id == membro_id, Topico.reuniao_id.is_(None))
                           .order_by(Topico.id)))


@dataclass
class Situacao:
    membro: Membro
    cadencia: int
    pausado: bool
    ultima: Reuniao | None
    agendada: Reuniao | None
    proxima: date | None
    estado: str  # nunca | em_dia | atrasada | agendada | pausado
    dias_atraso: int = 0
    humores: list[int] = field(default_factory=list)
    cargas: list[int] = field(default_factory=list)
    acoes_abertas: int = 0
    acoes_atrasadas: int = 0
    topicos: int = 0

    @property
    def alerta_humor(self) -> bool:
        return bool(self.humores) and (self.humores[-1] <= 2 or
                                       (len(self.humores) >= 3 and self.humores[-1] < self.humores[-3] - 1))

    @property
    def alerta_carga(self) -> bool:
        return bool(self.cargas) and self.cargas[-1] >= 5


ESTADOS = {
    "atrasada": ("Atrasada", "risco"),
    "nunca": ("Nunca realizada", "alerta"),
    "agendada": ("Agendada", "info"),
    "em_dia": ("Em dia", "ok"),
    "pausado": ("Pausada", ""),
}


def situacao(db: Session, membro: Membro, ref: date | None = None) -> Situacao:
    ref = ref or date.today()
    cfg = config(db, membro.id)
    todas = reunioes(db, membro_id=membro.id)
    realizadas = [r for r in todas if r.status == "realizada" and r.data <= ref]
    agendadas = sorted([r for r in todas if r.status == "agendada" and r.data >= ref], key=lambda r: r.data)
    ultima = realizadas[0] if realizadas else None
    agendada = agendadas[0] if agendadas else None
    devida = ultima.data + timedelta(days=cfg.cadencia_dias) if ultima else None
    if cfg.pausado:
        estado, proxima = "pausado", None
    elif agendada:
        estado, proxima = "agendada", agendada.data
    elif not ultima:
        estado, proxima = "nunca", None
    elif devida < ref:
        estado, proxima = "atrasada", devida
    else:
        estado, proxima = "em_dia", devida
    abertas = acoes(db, membro_id=membro.id, abertas=True)
    hist = list(reversed(realizadas[:8]))
    return Situacao(
        membro=membro, cadencia=cfg.cadencia_dias, pausado=cfg.pausado, ultima=ultima, agendada=agendada,
        proxima=proxima, estado=estado, dias_atraso=(ref - devida).days if estado == "atrasada" else 0,
        humores=[r.humor for r in hist if r.humor], cargas=[r.carga for r in hist if r.carga],
        acoes_abertas=len(abertas), acoes_atrasadas=sum(1 for a in abertas if a.atrasada),
        topicos=len(topicos_pendentes(db, membro.id)))


def situacoes(db: Session) -> list[Situacao]:
    ordem = list(ESTADOS)
    res = [situacao(db, m) for m in equipe.membros(db, apenas_ativos=True)]
    res.sort(key=lambda s: (ordem.index(s.estado), -s.dias_atraso, s.proxima or date.max, s.membro.nome))
    return res


def montar_pauta(db: Session, membro_id: int) -> str:
    """Texto inicial da pauta: tópicos pendentes + revisão de ações abertas."""
    linhas = []
    tops = topicos_pendentes(db, membro_id)
    if tops:
        linhas.append("Tópicos anotados:")
        linhas += [f"- {t.texto} ({t.autor_nome.lower()})" for t in tops]
    abertas = acoes(db, membro_id=membro_id, abertas=True)
    if abertas:
        linhas.append("Revisar ações:")
        linhas += [f"- {a.descricao} [{a.responsavel_nome}{', prazo ' + a.prazo.strftime('%d/%m') if a.prazo else ''}]"
                   for a in abertas]
    return "\n".join(linhas)


def registrar(db: Session, r: Reuniao, novas_acoes: list[dict], concluir_ids: list[int],
              topicos_ids: list[int]) -> Reuniao:
    if r.humor is not None and not 1 <= r.humor <= 5:
        raise HTTPException(422, "Humor deve ser de 1 a 5.")
    if r.carga is not None and not 1 <= r.carga <= 5:
        raise HTTPException(422, "Carga deve ser de 1 a 5.")
    if r.status not in ("agendada", "realizada", "cancelada"):
        raise HTTPException(422, "Status inválido.")
    db.add(r)
    db.flush()
    for d in novas_acoes:
        if d.get("descricao", "").strip():
            db.add(Acao(membro_id=r.membro_id, reuniao_id=r.id, descricao=d["descricao"].strip(),
                        responsavel=d.get("responsavel") or "membro", prazo=d.get("prazo")))
    for aid in concluir_ids:
        a = db.get(Acao, aid)
        if a and a.membro_id == r.membro_id:
            concluir_acao(a)
    for tid in topicos_ids:
        t = db.get(Topico, tid)
        if t and t.membro_id == r.membro_id:
            t.reuniao_id = r.id
    db.commit()
    db.refresh(r)
    return r
