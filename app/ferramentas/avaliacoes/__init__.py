from datetime import date, timedelta

from app.ferramentas.avaliacoes import models  # noqa: F401
from app.ferramentas.avaliacoes import servico
from app.ferramentas.avaliacoes.router import router


def painel(db):
    itens = []
    c = servico.ciclo_atual(db)
    if c and c.status != "encerrado":
        p = servico.progresso(servico.resultados(db, c))
        pend = 2 * p["total"] - p["auto"] - p["gestor"]
        atrasado = c.prazo and c.prazo < date.today() and pend
        itens.append({"titulo": f"{c.nome}", "valor": f"{p['pct'] * 100:.0f}%", "link": f"/avaliacoes?ciclo={c.id}",
                      "detalhe": f"{pend} avaliação(ões) pendente(s)" + (f" · prazo {c.prazo:%d/%m}" if c.prazo else ""),
                      "nivel": "risco" if atrasado else ("alerta" if pend else "ok")})
    recentes = servico.feedbacks(db, de=date.today() - timedelta(days=30))
    sem = servico.sem_feedback(db)
    itens.append({"titulo": "Feedbacks (30 dias)", "valor": len(recentes), "link": "/avaliacoes/feedbacks",
                  "detalhe": f"{sum(1 for f in recentes if f.tipo == 'reconhecimento')} reconhecimento(s)"})
    if sem:
        itens.append({"titulo": f"Sem feedback há {servico.DIAS_SEM_FEEDBACK_ALERTA}+ dias", "valor": len(sem),
                      "link": "/avaliacoes/feedbacks", "nivel": "alerta",
                      "detalhe": ", ".join(m.primeiro_nome for m, _ in sem[:4])})
    pdi_atrasado = [i for i in servico.pdi(db, abertos=True) if i.atrasado]
    if pdi_atrasado:
        itens.append({"titulo": "Itens de PDI atrasados", "valor": len(pdi_atrasado), "link": "/avaliacoes",
                      "nivel": "alerta"})
    return itens


def perfil(db, membro):
    ultimo = None
    for c in servico.ciclos(db):
        g = servico.buscar(db, c.id, membro.id, "gestor")
        if g and g.status == "enviada":
            ultimo = (c, servico.Resultado(membro, servico.buscar(db, c.id, membro.id, "auto"), g))
            break
    return {"ultimo": ultimo, "feedbacks": servico.feedbacks(db, membro_id=membro.id)[:5],
            "pdi": servico.pdi(db, membro_id=membro.id), "tipos_fb": models.TIPOS_FEEDBACK, "tipos_pdi": models.TIPOS_PDI,
            "ciclo": servico.ciclo_atual(db)}


FERRAMENTA = {
    "slug": "avaliacoes",
    "nome": "Avaliações",
    "descricao": "Avaliação de desempenho (auto e gestor), nine-box, feedback contínuo e PDI.",
    "router": router,
    "painel": painel,
    "perfil": perfil,
}
