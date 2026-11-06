"""Registro das ferramentas de gestão.

Cada ferramenta é um subpacote com:
  - models.py  -> tabelas (SQLAlchemy)
  - router.py  -> rotas (API JSON em /api/<slug> e páginas em /<slug>)
  - __init__.py com FERRAMENTA = {...} descrevendo nome, slug, descrição e router

Para criar uma nova: `make nova NOME=minha_ferramenta` e adicione-a em FERRAMENTAS abaixo.
"""
from app.ferramentas import ausencias, equipe, escalas, okrs, um_a_um

FERRAMENTAS = [
    equipe.FERRAMENTA,
    ausencias.FERRAMENTA,
    um_a_um.FERRAMENTA,
    okrs.FERRAMENTA,
    escalas.FERRAMENTA,
]
