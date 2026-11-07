# CLAUDE.md

Projeto de ferramentas de gestão de equipe (FastAPI + SQLAlchemy + SQLite + Jinja2). Idioma: português (código, UI e docs).

- Rodar: `make dev` · Testar: `make test` · Nova ferramenta: `make nova NOME=<slug>`
- Cada ferramenta vive em `app/ferramentas/<slug>/` e expõe `FERRAMENTA` (slug, nome, descricao, router); registre em `app/ferramentas/__init__.py`.
- API JSON em `/api/<slug>`, páginas em `/<slug>`, templates em `app/templates/<slug>/` estendendo `base.html`.
- Pessoas ficam em `membros` (ferramenta `equipe`); outras ferramentas referenciam `membros.id`.
- Tabelas são criadas no startup via `Base.metadata.create_all` (sem migrações por enquanto; adicionar Alembic quando houver dados reais).
- Testes usam SQLite em memória (`tests/conftest.py`); adicione testes para cada ferramenta nova.
- Contrato opcional de `FERRAMENTA`: `painel(db) -> list[dict]` (indicadores da página inicial: titulo, valor, detalhe, link, nivel ok|alerta|risco) e `perfil(db, membro) -> dict|None` (renderizado por `<slug>/_perfil.html` como `p`).
- Regras de negócio ficam em `servico.py` de cada ferramenta; `router.py` só faz HTTP (API + páginas). Utilidades de datas/feriados em `app/util.py`; filtros Jinja (`data`, `pct`, `num`, `nota`) e `redirecionar(url, msg=, erro=)` em `app/web.py`.
- Dados fictícios: `make exemplo LIMPAR=1` (script `scripts/dados_exemplo.py` — atualize ao criar ferramentas).
- Integrações existentes: escalas e competências consultam `ausencias.servico`; competências cria `ItemPDI` de avaliações.

