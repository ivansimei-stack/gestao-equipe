"""Cálculos de progresso, status e projeção de OKRs."""
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ferramentas.okrs.models import TIPOS_KR, Checkin, Ciclo, Objetivo, ResultadoChave
from app.util import somar_meses

DIAS_SEM_CHECKIN_ALERTA = 14

STATUS = {
    "concluido": ("Concluído", "ok"),
    "no_prazo": ("No ritmo", "ok"),
    "atencao": ("Atenção", "alerta"),
    "em_risco": ("Em risco", "risco"),
    "nao_iniciado": ("Não iniciado", ""),
    "encerrado": ("Não atingido", "risco"),
}


# ---------------- consultas ----------------

def ciclos(db: Session, incluir_arquivados: bool = True) -> list[Ciclo]:
    q = select(Ciclo).order_by(Ciclo.inicio.desc())
    if not incluir_arquivados:
        q = q.where(Ciclo.arquivado.is_(False))
    return list(db.scalars(q))


def ciclo_atual(db: Session, ref: date | None = None) -> Ciclo | None:
    ref = ref or date.today()
    lista = ciclos(db, incluir_arquivados=False)
    return next((c for c in lista if c.inicio <= ref <= c.fim), None) or (lista[0] if lista else None)


def obter(db: Session, modelo, id_: int):
    obj = db.get(modelo, id_)
    if not obj:
        raise HTTPException(404, f"{modelo.__name__} não encontrado(a)")
    return obj


def krs_do_membro(db: Session, membro_id: int, ciclo: Ciclo) -> list[ResultadoChave]:
    q = (select(ResultadoChave).join(ResultadoChave.objetivo)
         .where(Objetivo.ciclo_id == ciclo.id,
                or_(ResultadoChave.responsavel_id == membro_id, Objetivo.dono_id == membro_id)))
    return list(db.scalars(q).unique())


# ---------------- cálculos ----------------

def fracao_tempo(ciclo: Ciclo, ref: date | None = None) -> float:
    ref = ref or date.today()
    total = (ciclo.fim - ciclo.inicio).days + 1
    return max(0.0, min(1.0, ((ref - ciclo.inicio).days + 1) / total))


def progresso_kr(kr: ResultadoChave) -> float:
    if kr.tipo == "binario":
        return 1.0 if kr.valor_atual >= 1 else 0.0
    faixa = kr.valor_alvo - kr.valor_inicial
    if faixa == 0:
        return 1.0 if kr.valor_atual == kr.valor_alvo else 0.0
    return max(0.0, min(1.0, (kr.valor_atual - kr.valor_inicial) / faixa))


def ultimo_checkin(kr: ResultadoChave) -> Checkin | None:
    return kr.checkins[-1] if kr.checkins else None


def status_kr(kr: ResultadoChave, ref: date | None = None) -> str:
    ref = ref or date.today()
    ciclo = kr.objetivo.ciclo
    p = progresso_kr(kr)
    if p >= 1:
        return "concluido"
    if ref < ciclo.inicio:
        return "nao_iniciado"
    if ref > ciclo.fim:
        return "encerrado"
    esperado = fracao_tempo(ciclo, ref)
    ult = ultimo_checkin(kr)
    confianca_baixa = ult is not None and ult.confianca is not None and ult.confianca <= 4
    if kr.tipo == "binario":  # sem progresso parcial: avalia só pela confiança e pelo fim do prazo
        return "em_risco" if confianca_baixa or esperado > 0.85 else ("atencao" if esperado > 0.6 else "no_prazo")
    if p >= esperado - 0.10 and not confianca_baixa:
        return "no_prazo"
    if p >= esperado - 0.25 and not confianca_baixa:
        return "atencao"
    return "em_risco"


def projecao_kr(kr: ResultadoChave, ref: date | None = None) -> float | None:
    """Projeção linear do valor no fim do ciclo, com base no ritmo atual."""
    ciclo = kr.objetivo.ciclo
    ref = min(ref or date.today(), ciclo.fim)
    if kr.tipo == "binario" or ref < ciclo.inicio:
        return None
    decorrido = (ref - ciclo.inicio).days + 1
    total = (ciclo.fim - ciclo.inicio).days + 1
    if decorrido < 7 or not kr.checkins:
        return None
    proj = kr.valor_inicial + (kr.valor_atual - kr.valor_inicial) * total / decorrido
    if kr.tipo == "percentual":
        proj = max(0.0, min(100.0, proj))
    return proj


def progresso_objetivo(o: Objetivo) -> float:
    return sum(progresso_kr(k) for k in o.krs) / len(o.krs) if o.krs else 0.0


def status_objetivo(o: Objetivo, ref: date | None = None) -> str:
    if not o.krs:
        return "nao_iniciado"
    ordem = ["em_risco", "encerrado", "atencao", "no_prazo", "nao_iniciado", "concluido"]
    sts = [status_kr(k, ref) for k in o.krs]
    if all(s == "concluido" for s in sts):
        return "concluido"
    return min((s for s in sts if s != "concluido"), key=ordem.index)


def progresso_ciclo(c: Ciclo) -> float:
    return sum(progresso_objetivo(o) for o in c.objetivos) / len(c.objetivos) if c.objetivos else 0.0


def resumo_ciclo(c: Ciclo, ref: date | None = None) -> dict:
    krs = [k for o in c.objetivos for k in o.krs]
    contagem = {s: 0 for s in STATUS}
    for k in krs:
        contagem[status_kr(k, ref)] += 1
    ref = ref or date.today()
    sem_checkin = [k for k in krs if progresso_kr(k) < 1 and c.inicio <= ref <= c.fim and
                   (not k.checkins or (ref - k.checkins[-1].data).days > DIAS_SEM_CHECKIN_ALERTA)]
    return {"progresso": progresso_ciclo(c), "tempo": fracao_tempo(c, ref), "total_krs": len(krs),
            "contagem": contagem, "sem_checkin": sem_checkin,
            "dias_restantes": max(0, (c.fim - ref).days)}


# ---------------- operações ----------------

def validar_ciclo(c: Ciclo) -> None:
    if not c.nome or not c.nome.strip():
        raise HTTPException(422, "Informe o nome do ciclo.")
    if c.fim < c.inicio:
        raise HTTPException(422, "O fim do ciclo deve ser depois do início.")


def validar_kr(kr: ResultadoChave) -> None:
    if kr.tipo not in TIPOS_KR:
        raise HTTPException(422, "Tipo de KR inválido.")
    if kr.tipo == "binario":
        kr.valor_inicial, kr.valor_alvo = 0, 1
        kr.valor_atual = 1 if (kr.valor_atual or 0) >= 1 else 0
    elif kr.valor_alvo == kr.valor_inicial:
        raise HTTPException(422, "O valor alvo deve ser diferente do valor inicial.")


def registrar_checkin(db: Session, kr: ResultadoChave, valor: float, confianca: int | None,
                      comentario: str | None, data: date | None = None) -> Checkin:
    if confianca is not None and not 1 <= confianca <= 10:
        raise HTTPException(422, "Confiança deve ser de 1 a 10.")
    ch = Checkin(kr=kr, data=data or date.today(), valor=valor, confianca=confianca, comentario=comentario)
    db.add(ch)
    db.flush()
    db.refresh(kr)
    kr.valor_atual = kr.checkins[-1].valor if kr.checkins else valor  # último por data
    if kr.tipo == "binario":
        kr.valor_atual = 1 if kr.valor_atual >= 1 else 0
    db.commit()
    return ch


def duplicar_ciclo(db: Session, origem: Ciclo, nome: str, inicio: date, fim: date,
                   partir_do_atual: bool = True) -> Ciclo:
    """Cria um novo ciclo com os mesmos objetivos e KRs (valores reiniciados)."""
    novo = Ciclo(nome=nome, inicio=inicio, fim=fim)
    validar_ciclo(novo)
    for o in origem.objetivos:
        no = Objetivo(titulo=o.titulo, descricao=o.descricao, dono_id=o.dono_id, ordem=o.ordem)
        for k in o.krs:
            base = k.valor_atual if partir_do_atual and k.tipo != "binario" else k.valor_inicial
            no.krs.append(ResultadoChave(descricao=k.descricao, tipo=k.tipo, valor_inicial=base,
                                         valor_alvo=k.valor_alvo if k.valor_alvo != base else k.valor_alvo + 1,
                                         valor_atual=base, unidade=k.unidade, responsavel_id=k.responsavel_id))
        novo.objetivos.append(no)
    db.add(novo)
    db.commit()
    return novo


def sugerir_proximo_ciclo(c: Ciclo | None) -> dict:
    if not c:
        hoje = date.today()
        tri = (hoje.month - 1) // 3
        ini = date(hoje.year, tri * 3 + 1, 1)
        return {"nome": f"{hoje.year} T{tri + 1}", "inicio": ini, "fim": somar_meses(ini, 3) - timedelta(days=1)}
    meses = max(1, round(((c.fim - c.inicio).days + 1) / 30.4))
    ini = c.fim + timedelta(days=1)
    nome = f"{ini.year} T{(ini.month - 1) // 3 + 1}" if meses == 3 else f"Ciclo {ini:%m/%Y}"
    return {"nome": nome, "inicio": ini, "fim": somar_meses(ini, meses) - timedelta(days=1)}


def grafico_kr(kr: ResultadoChave, w: int = 1000, h: int = 280) -> dict:
    """Coordenadas SVG: linha real (check-ins) vs. ritmo ideal."""
    c = kr.objetivo.ciclo
    esq, dir_, topo, base = 90, 16, 14, 30
    total = max(1, (c.fim - c.inicio).days)
    pontos = [(c.inicio, kr.valor_inicial)] + [(ch.data, ch.valor) for ch in kr.checkins]
    valores = [v for _, v in pontos] + [kr.valor_alvo, kr.valor_inicial]
    vmin, vmax = min(valores), max(valores)
    if vmin == vmax:
        vmax = vmin + 1
    margem = (vmax - vmin) * 0.08
    vmin, vmax = vmin - margem, vmax + margem

    def x(d: date) -> float:
        return esq + (min(max((d - c.inicio).days, 0), total) / total) * (w - esq - dir_)

    def y(v: float) -> float:
        return topo + (vmax - v) / (vmax - vmin) * (h - topo - base)

    ticks_y = [vmin + margem + i * (vmax - vmin - 2 * margem) / 4 for i in range(5)]
    meses = []
    d = c.inicio.replace(day=1)
    while d <= c.fim:
        if d >= c.inicio:
            meses.append({"x": x(d), "rotulo": d.strftime("%m/%y")})
        d = somar_meses(d, 1)
    hoje = date.today()
    return {
        "w": w, "h": h, "esq": esq, "dir": dir_, "topo": topo, "base": base,
        "real": " ".join(f"{x(dt):.1f},{y(v):.1f}" for dt, v in pontos),
        "pontos": [{"x": x(dt), "y": y(v), "rotulo": f"{dt:%d/%m}: {kr.formatar(v)}"} for dt, v in pontos[1:]],
        "ideal": f"{x(c.inicio):.1f},{y(kr.valor_inicial):.1f} {x(c.fim):.1f},{y(kr.valor_alvo):.1f}",
        "alvo_y": y(kr.valor_alvo),
        "ticks_y": [{"y": y(v), "rotulo": kr.formatar(round(v, 2))} for v in ticks_y],
        "meses": meses, "hoje_x": x(hoje) if c.inicio <= hoje <= c.fim else None,
    }
