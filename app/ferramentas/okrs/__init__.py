from app.ferramentas.okrs import models  # noqa: F401
from app.ferramentas.okrs import servico
from app.ferramentas.okrs.router import router


def painel(db):
    c = servico.ciclo_atual(db)
    if not c or not c.objetivos:
        return [{"titulo": "OKRs", "valor": "—", "detalhe": "crie um ciclo", "link": "/okrs/ciclos"}]
    r = servico.resumo_ciclo(c)
    risco = r["contagem"]["em_risco"] + r["contagem"]["encerrado"]
    atrasado = r["progresso"] < r["tempo"] - 0.15
    return [
        {"titulo": f"Progresso {c.nome}", "valor": f"{r['progresso'] * 100:.0f}%", "link": f"/okrs?ciclo={c.id}",
         "detalhe": f"{r['tempo'] * 100:.0f}% do tempo · {r['dias_restantes']} dias restantes",
         "nivel": "alerta" if atrasado else "ok"},
        {"titulo": "KRs em risco", "valor": f"{risco} de {r['total_krs']}", "link": f"/okrs?ciclo={c.id}",
         "nivel": "risco" if risco else "ok"},
        {"titulo": "KRs sem check-in recente", "valor": len(r["sem_checkin"]), "link": f"/okrs?ciclo={c.id}",
         "detalhe": f"há mais de {servico.DIAS_SEM_CHECKIN_ALERTA} dias", "nivel": "alerta" if r["sem_checkin"] else "ok"},
    ]


def perfil(db, membro):
    c = servico.ciclo_atual(db)
    if not c:
        return None
    krs = servico.krs_do_membro(db, membro.id, c)
    objetivos = [o for o in c.objetivos if o.dono_id == membro.id]
    if not krs and not objetivos:
        return None
    return {"c": c, "krs": krs, "objetivos": objetivos, "sv": servico}


FERRAMENTA = {
    "slug": "okrs",
    "nome": "Metas e OKRs",
    "descricao": "Ciclos de objetivos e resultados-chave, check-ins com confiança, status e projeção.",
    "router": router,
    "painel": painel,
    "perfil": perfil,
}
