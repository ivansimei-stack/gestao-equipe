"""Regras de negócio de férias e ausências."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ferramentas.ausencias.models import STATUS_ATIVOS, TIPOS, Ausencia, RegraCobertura
from app.ferramentas.equipe import servico as equipe
from app.ferramentas.equipe.models import Membro
from app.util import dias, eh_dia_util, feriado, somar_meses, sobrepoe

DIAS_FERIAS_POR_PERIODO = 30
MAX_DIAS_VENDIDOS = 10
ANTECEDENCIA_ALERTA_VENCIMENTO = 60  # dias


# ---------------- consultas ----------------

def listar(db: Session, membro_id: int | None = None, status: str | None = None, tipo: str | None = None,
           de: date | None = None, ate: date | None = None, area: str | None = None) -> list[Ausencia]:
    q = select(Ausencia).join(Ausencia.membro).order_by(Ausencia.inicio, Membro.nome)
    if membro_id:
        q = q.where(Ausencia.membro_id == membro_id)
    if status:
        q = q.where(Ausencia.status.in_(status.split(",")))
    if tipo:
        q = q.where(Ausencia.tipo == tipo)
    if de:
        q = q.where(Ausencia.fim >= de)
    if ate:
        q = q.where(Ausencia.inicio <= ate)
    if area:
        q = q.where(Membro.area == area)
    return list(db.scalars(q).unique())


def obter(db: Session, ausencia_id: int) -> Ausencia:
    a = db.get(Ausencia, ausencia_id)
    if not a:
        raise HTTPException(404, "Ausência não encontrada")
    return a


def ausentes_em(db: Session, dia: date, incluir_solicitadas: bool = False) -> list[Ausencia]:
    status = "aprovada,solicitada" if incluir_solicitadas else "aprovada"
    return [a for a in listar(db, status=status, de=dia, ate=dia) if a.membro.ativo]


def regras(db: Session) -> dict[str, int]:
    return {r.area: r.minimo_presentes for r in db.scalars(select(RegraCobertura))}


# ---------------- validação ----------------

def validar(db: Session, a: Ausencia) -> None:
    """Erros que impedem salvar (HTTP 422/409)."""
    if a.tipo not in TIPOS:
        raise HTTPException(422, f"Tipo inválido: {a.tipo}")
    if a.fim < a.inicio:
        raise HTTPException(422, "A data final não pode ser anterior à inicial.")
    if a.dias_vendidos and a.tipo != "ferias":
        raise HTTPException(422, "Só é possível vender dias (abono pecuniário) em férias.")
    if not 0 <= (a.dias_vendidos or 0) <= MAX_DIAS_VENDIDOS:
        raise HTTPException(422, f"É possível vender no máximo {MAX_DIAS_VENDIDOS} dias.")
    for outra in listar(db, membro_id=a.membro_id, status=",".join(STATUS_ATIVOS), de=a.inicio, ate=a.fim):
        if outra.id != a.id:
            raise HTTPException(409, f"Já existe {outra.tipo_nome.lower()} de {outra.inicio:%d/%m} a "
                                     f"{outra.fim:%d/%m} para esta pessoa.")


def avisos(db: Session, a: Ausencia) -> list[str]:
    """Alertas que não impedem salvar, mas o gestor deve avaliar."""
    msgs: list[str] = []
    if a.tipo == "ferias":
        msgs += _avisos_clt(db, a)
    msgs += [c["texto"] for c in conflitos(db, a)]
    return msgs


def _avisos_clt(db: Session, a: Ausencia) -> list[str]:
    msgs = []
    for delta in (1, 2):
        d = a.inicio + timedelta(days=delta)
        if d.weekday() == 6 or feriado(d):
            motivo = feriado(d) or "domingo"
            msgs.append(f"CLT art. 134 §3º: férias não podem começar nos 2 dias que antecedem feriado ou DSR "
                        f"({motivo} em {d:%d/%m}).")
            break
    if a.dias_corridos < 5:
        msgs.append("CLT art. 134 §1º: cada parcela de férias deve ter pelo menos 5 dias corridos.")
    membro = a.membro or db.get(Membro, a.membro_id)
    if not membro or not membro.data_admissao:
        msgs.append("Cadastre a data de admissão para calcular o saldo de férias.")
        return msgs
    s = saldo(db, membro, extra=a)
    periodo = next((p for p in s.periodos if any(x is a for x in p.parcelas)), None)
    if periodo is None:
        return msgs
    if not periodo.adquirido:
        msgs.append("Férias antecipadas: o período aquisitivo ainda não foi completado.")
    if periodo.saldo < 0:
        msgs.append(f"Saldo insuficiente no período {periodo.rotulo} ({-periodo.saldo} dia(s) além do direito).")
    if len(periodo.parcelas) > 3:
        msgs.append(f"CLT: férias podem ser divididas em no máximo 3 parcelas (período {periodo.rotulo}).")
    tem_14 = any(p.dias_corridos >= 14 for p in periodo.parcelas)
    if not tem_14 and periodo.saldo < 14:
        msgs.append(f"CLT: uma das parcelas precisa ter pelo menos 14 dias corridos (período {periodo.rotulo}).")
    if a.fim > periodo.concessivo_fim:
        msgs.append(f"Termina após o fim do período concessivo ({periodo.concessivo_fim:%d/%m/%Y}) — "
                    "férias pagas em dobro (CLT art. 137).")
    return msgs


def conflitos(db: Session, a: Ausencia) -> list[dict]:
    """Colegas da mesma área ausentes no mesmo período e dias abaixo da cobertura mínima."""
    membro = a.membro or db.get(Membro, a.membro_id)
    if not membro or not membro.area:
        return []
    area = membro.area
    outros = [o for o in listar(db, status=",".join(STATUS_ATIVOS), de=a.inicio, ate=a.fim, area=area)
              if o.membro_id != a.membro_id and o.id != a.id and o.membro.ativo]
    res = []
    if outros:
        nomes = sorted({o.membro.primeiro_nome for o in outros})
        res.append({"tipo": "sobreposicao", "texto": f"Também ausentes na área {area} no período: {', '.join(nomes)}."})
    minimo = regras(db).get(area)
    if minimo:
        total = len(equipe.membros(db, apenas_ativos=True, area=area))
        criticos = []
        for d in dias(a.inicio, a.fim):
            if not eh_dia_util(d):
                continue
            fora = 1 + sum(1 for o in outros if o.inicio <= d <= o.fim)
            if total - fora < minimo:
                criticos.append(d)
        if criticos:
            amostra = ", ".join(f"{d:%d/%m}" for d in criticos[:6]) + ("…" if len(criticos) > 6 else "")
            res.append({"tipo": "cobertura", "dias": criticos,
                        "texto": f"Cobertura abaixo do mínimo ({minimo} presente(s)) na área {area} em "
                                 f"{len(criticos)} dia(s) útil(eis): {amostra}."})
    return res


# ---------------- fluxo ----------------

def decidir(db: Session, a: Ausencia, novo_status: str, motivo: str | None = None) -> Ausencia:
    transicoes = {
        "aprovada": ("solicitada", "recusada"),
        "recusada": ("solicitada", "aprovada"),
        "cancelada": ("solicitada", "aprovada"),
        "solicitada": ("cancelada", "recusada"),
    }
    if a.status not in transicoes.get(novo_status, ()):
        raise HTTPException(409, f"Não é possível passar de '{a.status}' para '{novo_status}'.")
    anterior, a.status = a.status, novo_status
    if novo_status in STATUS_ATIVOS:
        try:
            validar(db, a)
        except HTTPException:
            a.status = anterior
            raise
    a.motivo_decisao = motivo or a.motivo_decisao
    a.decidido_em = datetime.now() if novo_status != "solicitada" else None
    db.commit()
    return a


# ---------------- saldo de férias (CLT) ----------------

@dataclass
class Periodo:
    inicio: date
    fim: date
    concessivo_fim: date
    adquirido: bool
    direito: float
    usados: int = 0
    parcelas: list = field(default_factory=list)
    situacao: str = ""

    @property
    def saldo(self) -> float:
        return self.direito - self.usados

    @property
    def rotulo(self) -> str:
        return f"{self.inicio:%d/%m/%Y}–{self.fim:%d/%m/%Y}"


SITUACOES = {
    "em_aquisicao": ("Em aquisição", "info"),
    "em_dia": ("Disponível", "ok"),
    "vencendo": ("Vence em breve", "alerta"),
    "vencida": ("Vencida", "risco"),
    "quitado": ("Quitado", ""),
}


@dataclass
class Saldo:
    membro: Membro
    periodos: list[Periodo]
    solicitados: int = 0

    @property
    def disponivel(self) -> float:
        return sum(p.saldo for p in self.periodos if p.adquirido and p.saldo > 0)

    @property
    def pior_situacao(self) -> str:
        ordem = ["vencida", "vencendo", "em_dia", "em_aquisicao", "quitado"]
        sits = {p.situacao for p in self.periodos}
        return next((s for s in ordem if s in sits), "quitado")

    @property
    def proximo_limite(self) -> date | None:
        pend = [p.concessivo_fim for p in self.periodos if p.adquirido and p.saldo > 0]
        return min(pend) if pend else None


def saldo(db: Session, membro: Membro, ref: date | None = None, extra: Ausencia | None = None) -> Saldo:
    ref = ref or date.today()
    periodos: list[Periodo] = []
    if membro.data_admissao:
        ini = membro.data_admissao
        while ini <= ref:
            fim = somar_meses(ini, 12) - timedelta(days=1)
            adquirido = fim < ref
            meses = 12 if adquirido else max(0, (ref.year - ini.year) * 12 + ref.month - ini.month
                                              - (1 if ref.day < ini.day else 0))
            periodos.append(Periodo(
                inicio=ini, fim=fim, concessivo_fim=somar_meses(fim + timedelta(days=1), 12) - timedelta(days=1),
                adquirido=adquirido,
                direito=DIAS_FERIAS_POR_PERIODO if adquirido else round(meses * DIAS_FERIAS_POR_PERIODO / 12, 1)))
            ini = fim + timedelta(days=1)

    ferias = [a for a in listar(db, membro_id=membro.id, tipo="ferias", status="aprovada") if extra is None or a.id != extra.id]
    if extra is not None:
        ferias.append(extra)
    ferias.sort(key=lambda a: a.inicio)
    solicitados = sum(a.dias_corridos + a.dias_vendidos
                      for a in listar(db, membro_id=membro.id, tipo="ferias", status="solicitada"))

    # aloca FIFO: período adquirido mais antigo com saldo; senão, o período em aquisição (antecipação)
    for a in ferias:
        consumo = a.dias_corridos + (a.dias_vendidos or 0)
        alvo = next((p for p in periodos if p.adquirido and p.saldo > 0 and p.inicio <= a.inicio), None) \
            or next((p for p in periodos if not p.adquirido), None) \
            or (periodos[-1] if periodos else None)
        if alvo:
            alvo.usados += consumo
            alvo.parcelas.append(a)

    for p in periodos:
        if not p.adquirido:
            p.situacao = "em_aquisicao"
        elif p.saldo <= 0:
            p.situacao = "quitado"
        elif p.concessivo_fim < ref:
            p.situacao = "vencida"
        elif (p.concessivo_fim - ref).days <= ANTECEDENCIA_ALERTA_VENCIMENTO:
            p.situacao = "vencendo"
        else:
            p.situacao = "em_dia"
    return Saldo(membro=membro, periodos=periodos, solicitados=solicitados)


# ---------------- calendário ----------------

def calendario(db: Session, inicio: date, fim: date, area: str | None = None, incluir_solicitadas: bool = True):
    membros = equipe.membros(db, apenas_ativos=True, area=area)
    status = "aprovada,solicitada" if incluir_solicitadas else "aprovada"
    ausencias = listar(db, status=status, de=inicio, ate=fim, area=area)
    por_membro: dict[int, dict[date, Ausencia]] = {m.id: {} for m in membros}
    for a in ausencias:
        if a.membro_id in por_membro:
            for d in dias(max(a.inicio, inicio), min(a.fim, fim)):
                por_membro[a.membro_id][d] = a
    lista_dias = list(dias(inicio, fim))
    regras_area = regras(db)
    presentes = {}
    for d in lista_dias:
        presentes[d] = sum(1 for m in membros
                           if not (d in por_membro[m.id] and por_membro[m.id][d].status == "aprovada"))
    # dias críticos: alguma área abaixo do mínimo
    criticos = set()
    for ar, minimo in regras_area.items():
        if area and ar != area:
            continue
        da_area = [m for m in membros if m.area == ar]
        for d in lista_dias:
            if eh_dia_util(d) and sum(1 for m in da_area if d not in por_membro[m.id]) < minimo:
                criticos.add(d)
    return {"membros": membros, "dias": lista_dias, "grade": por_membro, "presentes": presentes, "criticos": criticos}


# ---------------- exportação ----------------

def ics(ausencias: list[Ausencia], nome_cal: str) -> str:
    def esc(t: str) -> str:
        return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    agora = datetime.now().strftime("%Y%m%dT%H%M%S")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//gestao-equipe//ausencias//PT",
              "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{esc(nome_cal)}"]
    for a in ausencias:
        linhas += [
            "BEGIN:VEVENT",
            f"UID:ausencia-{a.id}@gestao-equipe",
            f"DTSTAMP:{agora}",
            f"DTSTART;VALUE=DATE:{a.inicio:%Y%m%d}",
            f"DTEND;VALUE=DATE:{a.fim + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{esc(a.membro.nome + ' — ' + a.tipo_nome)}",
            f"DESCRIPTION:{esc(a.observacao or '')}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas) + "\r\n"
