"""Registro das ferramentas de gestão.

Cada ferramenta é um subpacote com:
  - models.py  -> tabelas (SQLAlchemy)
  - router.py  -> rotas (API JSON em /api/<slug> e páginas em /<slug>)
  - __init__.py com FERRAMENTA = {...} descrevendo nome, slug, descrição e router

Para criar uma nova: `make nova NOME=minha_ferramenta` e adicione-a em FERRAMENTAS abaixo.
"""
from app.ferramentas import equipe

FERRAMENTAS = [
    equipe.FERRAMENTA,
]
