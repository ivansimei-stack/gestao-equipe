from datetime import date

from app.ferramentas.equipe import models  # noqa: F401
from app.ferramentas.equipe import servico
from app.ferramentas.equipe.router import router


def painel(db):
    ativos = servico.membros(db, apenas_ativos=True)
    itens = [{"titulo": "Pessoas ativas", "valor": len(ativos), "link": "/equipe"}]
    hoje = date.today()
    for m, d in servico.aniversariantes(db, dias=14):
        itens.append({"titulo": "Aniversário", "valor": m.primeiro_nome,
                      "detalhe": "hoje! 🎉" if d == hoje else d.strftime("%d/%m"), "link": f"/equipe/{m.id}"})
    for m, d, anos in servico.aniversarios_de_empresa(db, dias=14):
        itens.append({"titulo": f"{anos} ano{'s' if anos > 1 else ''} de casa", "valor": m.primeiro_nome,
                      "detalhe": d.strftime("%d/%m"), "link": f"/equipe/{m.id}"})
    return itens


FERRAMENTA = {
    "slug": "equipe",
    "nome": "Equipe",
    "descricao": "Cadastro dos membros da equipe, perfil individual e datas comemorativas.",
    "router": router,
    "painel": painel,
}
