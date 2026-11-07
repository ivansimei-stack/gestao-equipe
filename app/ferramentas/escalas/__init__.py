from datetime import date

from app.ferramentas.escalas import models  # noqa: F401
from app.ferramentas.escalas import servico
from app.ferramentas.escalas.router import router
from app.util import eh_dia_util


def painel(db):
    itens = []
    for e in servico.escalas(db, apenas_ativas=True):
        t = servico.de_plantao(db, e)
        n_conf = len(servico.conflitos(db, e))
        folga = not t and e.apenas_dias_uteis and not eh_dia_util(date.today())
        itens.append({"titulo": e.nome, "valor": t.membro.primeiro_nome if t else "—", "link": f"/escalas/{e.id}",
                      "detalhe": (f"até {t.fim:%d/%m}" if t else ("não há turno hoje (dia não útil)" if folga
                                                                    else "sem turno hoje")) +
                                 (f" · {n_conf} conflito(s)" if n_conf else ""),
                      "nivel": "risco" if n_conf or (not t and not folga) else None})
    return itens


def perfil(db, membro):
    hoje = date.today()
    proximos = [t for t in servico.turnos(db, membro_id=membro.id, de=hoje)][:6]
    if not proximos and not any(p.membro_id == membro.id for e in servico.escalas(db) for p in e.participantes):
        return None
    return {"turnos": proximos}


FERRAMENTA = {
    "slug": "escalas",
    "nome": "Escalas",
    "descricao": "Rodízios de plantão e suporte que respeitam férias e ausências, com trocas e equilíbrio.",
    "router": router,
    "painel": painel,
    "perfil": perfil,
}
