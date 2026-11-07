from dataclasses import dataclass
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ferramentas.avaliacoes.models import (CRITERIOS_PADRAO, Avaliacao, CicloAvaliacao, Criterio, Feedback,
                                               ItemPDI, Nota)
from app.ferramentas.equipe import servico as equipe
from app.ferramentas.equipe.models import Membro

DIAS_SEM_FEEDBACK_ALERTA = 45
DIVERGENCIA_ALERTA = 2  # pontos de diferença entre auto e gestor num critério

# (potencial, desempenho) -> (nome, descrição, cor)
NINE_BOX = {
    (3, 1): ("Enigma", "Alto potencial pouco aproveitado: investigar causas e reposicionar.", "alerta"),
    (3, 2): ("Forte potencial", "Desenvolver para assumir desafios maiores.", "ok"),
    (3, 3): ("Estrela", "Reter e preparar para posições-chave.", "ok"),
    (2, 1): ("Questionável", "Plano de ação com acompanhamento próximo.", "risco"),
    (2, 2): ("Mantenedor", "Base sólida do time; desenvolver pontos específicos.", "info"),
    (2, 3): ("Forte desempenho", "Reconhecer e ampliar escopo.", "ok"),
    (1, 1): ("Insuficiente", "Plano de melhoria com metas claras e prazo.", "risco"),
    (1, 2): ("Eficaz", "Manter na função, reconhecer a contribuição.", "info"),
    (1, 3): ("Profissional comprometido", "Especialista valioso; reconhecer e reter.", "ok"),
}


def faixa_desempenho(nota: float | None) -> int | None:
    if nota is None:
        return None
    return 1 if nota < 3 else (2 if nota < 4 else 3)


# ---------------- ciclos e critérios ----------------

def ciclos(db: Session) -> list[CicloAvaliacao]:
    return list(db.scalars(select(CicloAvaliacao).order_by(CicloAvaliacao.fim.desc())))


def ciclo_atual(db: Session) -> CicloAvaliacao | None:
    lista = ciclos(db)
    return next((c for c in lista if c.status != "encerrado"), None) or (lista[0] if lista else None)


def obter(db: Session, modelo, id_: int):
    obj = db.get(modelo, id_)
    if not obj:
        raise HTTPException(404, "Registro não encontrado")
    return obj


def criar_ciclo(db: Session, nome: str, inicio: date, fim: date, prazo: date | None,
                criterios: list[tuple[str, str | None, float]] | None = None,
                copiar_de: CicloAvaliacao | None = None) -> CicloAvaliacao:
    if not nome.strip():
        raise HTTPException(422, "Informe o nome do ciclo.")
    if fim < inicio:
        raise HTTPException(422, "O fim do período deve ser depois do início.")
    c = CicloAvaliacao(nome=nome.strip(), inicio=inicio, fim=fim, prazo=prazo)
    if copiar_de:
        criterios = [(k.nome, k.descricao, k.peso) for k in copiar_de.criterios]
    for i, (n, d, p) in enumerate(criterios if criterios is not None else CRITERIOS_PADRAO):
        c.criterios.append(Criterio(nome=n, descricao=d, peso=p, ordem=i))
    db.add(c)
    db.commit()
    return c


def exigir_editavel(c: CicloAvaliacao) -> None:
    if c.status == "encerrado":
        raise HTTPException(409, "Ciclo encerrado: reabra-o para alterar.")


# ---------------- avaliações ----------------

def obter_ou_criar(db: Session, ciclo: CicloAvaliacao, membro_id: int, tipo: str) -> Avaliacao:
    if tipo not in ("auto", "gestor"):
        raise HTTPException(422, "Tipo deve ser 'auto' ou 'gestor'.")
    a = db.scalar(select(Avaliacao).where(Avaliacao.ciclo_id == ciclo.id, Avaliacao.membro_id == membro_id,
                                          Avaliacao.tipo == tipo))
    if not a:
        a = Avaliacao(ciclo=ciclo, membro_id=membro_id, tipo=tipo)
        db.add(a)
        db.flush()
    return a


def buscar(db: Session, ciclo_id: int, membro_id: int, tipo: str) -> Avaliacao | None:
    return db.scalar(select(Avaliacao).where(Avaliacao.ciclo_id == ciclo_id, Avaliacao.membro_id == membro_id,
                                             Avaliacao.tipo == tipo))


def salvar(db: Session, a: Avaliacao, notas: dict[int, tuple[int | None, str | None]], textos: dict,
           potencial: int | None, enviar: bool) -> Avaliacao:
    exigir_editavel(a.ciclo)
    ids = {k.id for k in a.ciclo.criterios}
    for cid, (valor, coment) in notas.items():
        if cid not in ids:
            raise HTTPException(422, f"Critério {cid} não pertence ao ciclo.")
        if valor is not None and not 1 <= valor <= 5:
            raise HTTPException(422, "Notas devem ser de 1 a 5.")
        n = a.nota_de(cid)
        if not n:
            n = Nota(criterio_id=cid)
            a.notas.append(n)
        n.nota, n.comentario = valor, coment
    for campo in ("pontos_fortes", "a_desenvolver", "comentario"):
        if campo in textos:
            setattr(a, campo, textos[campo])
    if a.tipo == "gestor":
        if potencial is not None and potencial not in (1, 2, 3):
            raise HTTPException(422, "Potencial deve ser 1, 2 ou 3.")
        a.potencial = potencial
    if enviar:
        faltando = [k.nome for k in a.ciclo.criterios if not (a.nota_de(k.id) and a.nota_de(k.id).nota)]
        if faltando:
            db.rollback()
            raise HTTPException(422, f"Preencha todas as notas antes de enviar (faltam: {', '.join(faltando)}).")
        if a.tipo == "gestor" and not a.potencial:
            db.rollback()
            raise HTTPException(422, "Informe o potencial antes de enviar.")
        a.status, a.enviada_em = "enviada", datetime.now()
    db.commit()
    return a


def reabrir(db: Session, a: Avaliacao) -> Avaliacao:
    exigir_editavel(a.ciclo)
    a.status, a.enviada_em = "rascunho", None
    db.commit()
    return a


def nota_final(a: Avaliacao | None) -> float | None:
    if not a:
        return None
    pesos = {k.id: k.peso for k in a.ciclo.criterios}
    pares = [(n.nota, pesos.get(n.criterio_id, 0)) for n in a.notas if n.nota]
    total = sum(p for _, p in pares)
    return round(sum(v * p for v, p in pares) / total, 2) if total else None


@dataclass
class Resultado:
    membro: Membro
    auto: Avaliacao | None
    gestor: Avaliacao | None

    @property
    def nota_auto(self):
        return nota_final(self.auto) if self.auto and self.auto.status == "enviada" else None

    @property
    def nota_gestor(self):
        return nota_final(self.gestor) if self.gestor and self.gestor.status == "enviada" else None

    @property
    def caixa(self):
        d = faixa_desempenho(self.nota_gestor)
        p = self.gestor.potencial if self.gestor and self.gestor.status == "enviada" else None
        return (p, d) if p and d else None

    @property
    def caixa_info(self):
        return NINE_BOX.get(self.caixa) if self.caixa else None

    @property
    def gap(self):
        if self.nota_auto is None or self.nota_gestor is None:
            return None
        return round(self.nota_auto - self.nota_gestor, 2)

    def divergencias(self) -> list[tuple]:
        if not (self.auto and self.gestor):
            return []
        res = []
        for k in self.gestor.ciclo.criterios:
            na, ng = self.auto.nota_de(k.id), self.gestor.nota_de(k.id)
            if na and ng and na.nota and ng.nota and abs(na.nota - ng.nota) >= DIVERGENCIA_ALERTA:
                res.append((k, na.nota, ng.nota))
        return res


def resultados(db: Session, ciclo: CicloAvaliacao) -> list[Resultado]:
    por = {(a.membro_id, a.tipo): a for a in ciclo.avaliacoes}
    membros = {m.id: m for m in equipe.membros(db, apenas_ativos=True)}
    for a in ciclo.avaliacoes:  # inclui quem foi avaliado e depois inativado
        membros.setdefault(a.membro_id, a.membro)
    return [Resultado(m, por.get((m.id, "auto")), por.get((m.id, "gestor")))
            for m in sorted(membros.values(), key=lambda m: m.nome)]


def progresso(res: list[Resultado]) -> dict:
    n = len(res) or 1
    auto = sum(1 for r in res if r.auto and r.auto.status == "enviada")
    gest = sum(1 for r in res if r.gestor and r.gestor.status == "enviada")
    return {"total": len(res), "auto": auto, "gestor": gest, "pct": (auto + gest) / (2 * n)}


def mudar_status(db: Session, c: CicloAvaliacao, status: str) -> None:
    if status not in ("aberto", "calibracao", "encerrado"):
        raise HTTPException(422, "Status inválido.")
    c.status = status
    db.commit()


# ---------------- feedback e PDI ----------------

def feedbacks(db: Session, membro_id: int | None = None, de: date | None = None, ate: date | None = None,
              tipo: str | None = None) -> list[Feedback]:
    q = select(Feedback).order_by(Feedback.data.desc(), Feedback.id.desc())
    if membro_id:
        q = q.where(Feedback.membro_id == membro_id)
    if de:
        q = q.where(Feedback.data >= de)
    if ate:
        q = q.where(Feedback.data <= ate)
    if tipo:
        q = q.where(Feedback.tipo == tipo)
    return list(db.scalars(q).unique())


def sem_feedback(db: Session, dias: int = DIAS_SEM_FEEDBACK_ALERTA) -> list[tuple[Membro, date | None]]:
    limite = date.today() - timedelta(days=dias)
    res = []
    for m in equipe.membros(db, apenas_ativos=True):
        ult = next(iter(feedbacks(db, membro_id=m.id)), None)
        if not ult or ult.data < limite:
            res.append((m, ult.data if ult else None))
    return res


def pdi(db: Session, membro_id: int | None = None, abertos: bool | None = None) -> list[ItemPDI]:
    q = select(ItemPDI)
    if membro_id:
        q = q.where(ItemPDI.membro_id == membro_id)
    if abertos is not None:
        q = q.where(ItemPDI.concluido.is_(not abertos))
    lista = list(db.scalars(q).unique())
    lista.sort(key=lambda i: (i.concluido, i.prazo or date.max, i.id))
    return lista
