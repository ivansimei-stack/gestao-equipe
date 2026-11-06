from datetime import date, timedelta

from app.ferramentas.ausencias import models  # noqa: F401
from app.ferramentas.ausencias import servico
from app.ferramentas.ausencias.router import router
from app.ferramentas.equipe import servico as equipe


def painel(db):
    hoje = date.today()
    ausentes = servico.ausentes_em(db, hoje)
    pendentes = servico.listar(db, status="solicitada")
    saldos = [servico.saldo(db, m) for m in equipe.membros(db, apenas_ativos=True)]
    vencidas = [s for s in saldos if s.pior_situacao == "vencida"]
    vencendo = [s for s in saldos if s.pior_situacao == "vencendo"]
    semana = [a for a in servico.listar(db, status="aprovada", de=hoje, ate=hoje + timedelta(days=7)) if a.inicio > hoje]
    itens = [
        {"titulo": "Ausentes hoje", "valor": len(ausentes), "link": "/ausencias",
         "detalhe": ", ".join(a.membro.primeiro_nome for a in ausentes[:4]) or "equipe completa"},
        {"titulo": "Pedidos pendentes", "valor": len(pendentes), "link": "/ausencias",
         "nivel": "alerta" if pendentes else "ok"},
        {"titulo": "Saem nos próximos 7 dias", "valor": len(semana), "link": "/ausencias/calendario",
         "detalhe": ", ".join(a.membro.primeiro_nome for a in semana[:4])},
    ]
    if vencidas or vencendo:
        itens.append({"titulo": "Férias vencidas / vencendo", "valor": f"{len(vencidas)} / {len(vencendo)}",
                      "link": "/ausencias/saldos", "nivel": "risco" if vencidas else "alerta",
                      "detalhe": ", ".join(s.membro.primeiro_nome for s in (vencidas + vencendo)[:4])})
    return itens


def perfil(db, membro):
    hoje = date.today()
    return {
        "saldo": servico.saldo(db, membro),
        "proximas": servico.listar(db, membro_id=membro.id, status="aprovada,solicitada", de=hoje),
        "recentes": list(reversed(servico.listar(db, membro_id=membro.id, ate=hoje - timedelta(days=1))))[:5],
        "situacoes": servico.SITUACOES,
    }


FERRAMENTA = {
    "slug": "ausencias",
    "nome": "Férias e Ausências",
    "descricao": "Pedidos e aprovações, saldo de férias (CLT), calendário da equipe e conflitos de cobertura.",
    "router": router,
    "painel": painel,
    "perfil": perfil,
}
