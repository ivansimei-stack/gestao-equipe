# CLAUDE.md

Projeto de ferramentas de gestão de equipe (FastAPI + SQLAlchemy + SQLite + Jinja2). Idioma: português (código, UI e docs).

- Rodar: `make dev` · Testar: `make test` · Nova ferramenta: `make nova NOME=<slug>`
- Cada ferramenta vive em `app/ferramentas/<slug>/` e expõe `FERRAMENTA` (slug, nome, descricao, router); registre em `app/ferramentas/__init__.py`.
- API JSON em `/api/<slug>`, páginas em `/<slug>`, templates em `app/templates/<slug>/` estendendo `base.html`.
- Pessoas ficam em `membros` (ferramenta `equipe`); outras ferramentas referenciam `membros.id`.
- Tabelas são criadas no startup via `Base.metadata.create_all` (sem migrações por enquanto; adicionar Alembic quando houver dados reais).
- Testes usam SQLite em memória (`tests/conftest.py`); adicione testes para cada ferramenta nova.
