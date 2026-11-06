from app.ferramentas.equipe import models  # noqa: F401
from app.ferramentas.equipe.router import router

FERRAMENTA = {
    "slug": "equipe",
    "nome": "Equipe",
    "descricao": "Cadastro dos membros da equipe — base para as demais ferramentas.",
    "router": router,
}
