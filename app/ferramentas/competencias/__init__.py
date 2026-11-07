from app.ferramentas.competencias import models  # noqa: F401
from app.ferramentas.competencias import servico
from app.ferramentas.competencias.router import router


def painel(db):
    analises = servico.analisar(db)
    if not analises:
        return [{"titulo": "Competências", "valor": "—", "detalhe": "monte o catálogo", "link": "/competencias/catalogo"}]
    risco = [a for a in analises if a.risco in ("sem_cobertura", "alto")]
    descobertos = [a for a in analises if a.dias_descobertos]
    itens = [{"titulo": "Competências em risco", "valor": f"{len(risco)} de {len(analises)}",
              "link": "/competencias/riscos", "nivel": "risco" if risco else "ok",
              "detalhe": ", ".join(a.competencia.nome for a in risco[:3]) or "fator ônibus ok"}]
    if descobertos:
        itens.append({"titulo": "Críticas sem cobertura (30 dias)", "valor": len(descobertos),
                      "link": "/competencias/riscos", "nivel": "risco",
                      "detalhe": ", ".join(f"{a.competencia.nome} {a.dias_descobertos[0]:%d/%m}" for a in descobertos[:2])})
    return itens


def perfil(db, membro):
    linhas = servico.perfil_membro(db, membro)
    if not linhas:
        return None
    return {"fortes": sorted([l for l in linhas if l["nivel"] >= 3], key=lambda l: -l["nivel"]),
            "gaps": [l for l in linhas if l["gap"]], "interesses": [l for l in linhas if l["interesse"]]}


FERRAMENTA = {
    "slug": "competencias",
    "nome": "Competências",
    "descricao": "Matriz de habilidades, fator ônibus, riscos de cobertura com ausências e sugestões de mentoria.",
    "router": router,
    "painel": painel,
    "perfil": perfil,
}
