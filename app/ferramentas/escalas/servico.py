"""Geração de rodízio, trocas, conflitos com ausências e equilíbrio."""
from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ferramentas.ausencias import servico as ausencias
from app.ferramentas.escalas.models import Escala, Participante, Turno
from app.ferramentas.equipe.models import Membro
from app.util import eh_dia_util, sobrepoe


def escalas(db: Session, apenas_ativas: bool = False) -> list[Escala]:
    q = select(Escala).order_by(Escala.nome)
    if apenas_ativas:
        q = q.where(Escala.ativa.is_(True))
    return list(db.scalars(q))


def obter(db: Session, escala_id: int) -> Escala:
    e = db.get(Escala, escala_id)
    if not e:
        raise HTTPException(404, "Escala não encontrada")
    return e


def obter_turno(db: Session, turno_id: int) -> Turno:
    t = db.get(Turno, turno_id)
    if not t:
        raise HTTPException(404, "Turno não encontrado")
    return t


def validar(e: Escala) -> None:
    if not (e.nome or "").strip():
        raise HTTPException(422, "Informe o nome da escala.")
    if not 1 <= (e.duracao_dias or 0) <= 31:
        raise HTTPException(422, "A duração do turno deve ser de 1 a 31 dias.")
    if e.apenas_dias_uteis and e.duracao_dias != 1:
        raise HTTPException(422, "“Apenas dias úteis” vale só para escalas diárias.")


def turnos(db: Session, escala_id: int | None = None, membro_id: int | None = None,
           de: date | None = None, ate: date | None = None) -> list[Turno]:
    q = select(Turno).order_by(Turno.inicio, Turno.id)
    if escala_id:
        q = q.where(Turno.escala_id == escala_id)
    if membro_id:
        q = q.where(Turno.membro_id == membro_id)
    if de:
        q = q.where(Turno.fim >= de)
    if ate:
        q = q.where(Turno.inicio <= ate)
    return list(db.scalars(q).unique())


def de_plantao(db: Session, e: Escala, dia: date | None = None) -> Turno | None:
    dia = dia or date.today()
    return next(iter(turnos(db, e.id, de=dia, ate=dia)), None)


def adicionar_participante(db: Session, e: Escala, membro: Membro) -> Participante:
    if any(p.membro_id == membro.id for p in e.participantes):
        raise HTTPException(409, f"{membro.nome} já participa desta escala.")
    p = Participante(escala=e, membro=membro, ordem=max((p.ordem for p in e.participantes), default=-1) + 1)
    db.add(p)
    db.commit()
    return p


def mover_participante(db: Session, e: Escala, participante_id: int, delta: int) -> None:
    lista = list(e.participantes)
    idx = next((i for i, p in enumerate(lista) if p.id == participante_id), None)
    if idx is None:
        raise HTTPException(404, "Participante não encontrado")
    novo = max(0, min(len(lista) - 1, idx + delta))
    lista.insert(novo, lista.pop(idx))
    for i, p in enumerate(lista):
        p.ordem = i
    db.commit()


# ---------------- geração ----------------

def _slots(e: Escala, de: date, ate: date):
    d = de
    while d <= ate:
        if e.duracao_dias == 1 and e.apenas_dias_uteis and not eh_dia_util(d):
            d += timedelta(days=1)
            continue
        fim = d + timedelta(days=e.duracao_dias - 1)
        yield d, fim
        d = fim + timedelta(days=1)


def _ausente(db: Session, membro_id: int, ini: date, fim: date) -> bool:
    return any(a.status in ("aprovada", "solicitada")
               for a in ausencias.listar(db, membro_id=membro_id, de=ini, ate=fim))


def sugerir_inicio(db: Session, e: Escala) -> date:
    """Dia seguinte ao último turno; sem turnos, a próxima segunda (semanal) ou hoje."""
    lista = turnos(db, e.id)
    if lista:
        return max(date.today(), max(t.fim for t in lista) + timedelta(days=1))
    hoje = date.today()
    return hoje + timedelta(days=(7 - hoje.weekday()) % 7) if e.duracao_dias % 7 == 0 else hoje


def gerar(db: Session, e: Escala, de: date, ate: date, sobrescrever_manuais: bool = False) -> dict:
    """(Re)gera os turnos automáticos entre `de` e `ate`, mantendo trocas/manuais (salvo se pedido)."""
    if ate < de:
        raise HTTPException(422, "A data final deve ser posterior à inicial.")
    if (ate - de).days > 400:
        raise HTTPException(422, "Gere no máximo ~13 meses por vez.")
    ativos = [p.membro for p in e.participantes if p.membro.ativo]
    if not ativos:
        raise HTTPException(422, "Adicione participantes ativos à escala.")

    existentes = turnos(db, e.id, de=de, ate=ate)
    for t in existentes:
        if t.inicio >= de and (t.origem == "gerado" or sobrescrever_manuais):
            db.delete(t)
    db.flush()
    fixos = [t for t in turnos(db, e.id, de=de, ate=ate)]

    # continua o rodízio a partir de quem fez o último turno antes do período
    anterior = [t for t in turnos(db, e.id, ate=de - timedelta(days=1)) if t.inicio < de]
    ids = [m.id for m in ativos]
    def dono_da_vez(t: Turno) -> int:
        """Em trocas, a posição no rodízio é de quem estava escalado originalmente."""
        return t.membro_original_id or t.membro_id

    ponteiro = 0
    if anterior and dono_da_vez(anterior[-1]) in ids:
        ponteiro = (ids.index(dono_da_vez(anterior[-1])) + 1) % len(ids)

    # se um turno anterior ainda está em curso, começa logo após ele (evita buracos)
    em_curso = [t.fim for t in anterior if t.fim >= de]
    if em_curso:
        de = max(em_curso) + timedelta(days=1)

    devendo: list[int] = []  # pulados por ausência têm prioridade quando voltam
    criados, pulos, vagos = 0, [], []
    for ini, fim in _slots(e, de, ate):
        fixo = next((t for t in fixos if sobrepoe(ini, fim, t.inicio, t.fim)), None)
        if fixo:
            if dono_da_vez(fixo) in ids:
                ponteiro = (ids.index(dono_da_vez(fixo)) + 1) % len(ids)
            continue
        escolhido = None
        for mid in list(devendo):
            if not (e.pular_ausentes and _ausente(db, mid, ini, fim)):
                escolhido = mid
                devendo.remove(mid)
                break
        tentativas = 0
        while escolhido is None and tentativas < len(ids):
            mid = ids[ponteiro]
            ponteiro = (ponteiro + 1) % len(ids)
            tentativas += 1
            if e.pular_ausentes and _ausente(db, mid, ini, fim):
                pulos.append((ini, mid))
                if mid not in devendo:
                    devendo.append(mid)
                continue
            if mid in devendo:
                devendo.remove(mid)
            escolhido = mid
        if escolhido is None:
            vagos.append(ini)
            continue
        db.add(Turno(escala=e, membro_id=escolhido, inicio=ini, fim=fim, origem="gerado"))
        criados += 1
    db.commit()
    nomes = {m.id: m.primeiro_nome for m in ativos}
    return {"criados": criados, "mantidos": len(fixos),
            "pulos": [f"{d:%d/%m} {nomes[m]}" for d, m in pulos], "vagos": vagos}


# ---------------- trocas ----------------

def trocar_responsavel(db: Session, t: Turno, novo_membro_id: int, observacao: str | None = None) -> Turno:
    if novo_membro_id == t.membro_id:
        raise HTTPException(422, "Escolha outra pessoa para a troca.")
    novo = db.get(Membro, novo_membro_id)
    if not novo:
        raise HTTPException(404, "Membro não encontrado")
    if t.membro_original_id is None:
        t.membro_original_id = t.membro_id
    t.membro_id = novo_membro_id
    if t.membro_original_id == novo_membro_id:  # voltou para o original
        t.membro_original_id, t.origem = None, "gerado"
    else:
        t.origem = "troca"
    t.observacao = observacao or t.observacao
    db.commit()
    db.refresh(t)
    return t


def permutar(db: Session, t1: Turno, t2: Turno, observacao: str | None = None) -> None:
    if t1.escala_id != t2.escala_id:
        raise HTTPException(422, "Só é possível permutar turnos da mesma escala.")
    if t1.membro_id == t2.membro_id:
        raise HTTPException(422, "Os dois turnos são da mesma pessoa.")
    a, b = t1.membro_id, t2.membro_id
    for t, novo in ((t1, b), (t2, a)):
        if t.membro_original_id is None:
            t.membro_original_id = t.membro_id
        t.membro_id = novo
        t.origem = "troca"
        t.observacao = observacao or "Permuta"
    db.commit()


# ---------------- análises ----------------

def conflitos(db: Session, e: Escala, de: date | None = None) -> list[tuple[Turno, list]]:
    """Turnos futuros cuja pessoa tem ausência registrada no período."""
    de = de or date.today()
    res = []
    for t in turnos(db, e.id, de=de):
        aus = [a for a in ausencias.listar(db, membro_id=t.membro_id, de=t.inicio, ate=t.fim)
               if a.status in ("aprovada", "solicitada")]
        if aus:
            res.append((t, aus))
    return res


def equilibrio(db: Session, e: Escala, meses: int = 6) -> list[dict]:
    hoje = date.today()
    ini = hoje - timedelta(days=30 * meses)
    passados = Counter()
    futuros = Counter()
    dias = Counter()
    for t in turnos(db, e.id, de=ini):
        (passados if t.inicio <= hoje else futuros)[t.membro_id] += 1
        dias[t.membro_id] += (t.fim - t.inicio).days + 1
    linhas = []
    for p in e.participantes:
        mid = p.membro_id
        linhas.append({"membro": p.membro, "passados": passados[mid], "futuros": futuros[mid], "dias": dias[mid]})
    if linhas:
        media = sum(x["passados"] + x["futuros"] for x in linhas) / len(linhas)
        for x in linhas:
            x["desvio"] = round(x["passados"] + x["futuros"] - media, 1)
    return linhas


def ics(e: Escala, lista: list[Turno]) -> str:
    agora = datetime.now().strftime("%Y%m%dT%H%M%S")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//gestao-equipe//escalas//PT", "CALSCALE:GREGORIAN",
              f"X-WR-CALNAME:Escala {e.nome}"]
    for t in lista:
        linhas += ["BEGIN:VEVENT", f"UID:turno-{t.id}@gestao-equipe", f"DTSTAMP:{agora}",
                   f"DTSTART;VALUE=DATE:{t.inicio:%Y%m%d}", f"DTEND;VALUE=DATE:{t.fim + timedelta(days=1):%Y%m%d}",
                   f"SUMMARY:{e.nome}: {t.membro.nome}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas) + "\r\n"
