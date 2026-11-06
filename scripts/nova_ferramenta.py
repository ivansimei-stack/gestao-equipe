"""Gera o esqueleto de uma nova ferramenta em app/ferramentas/<slug>.

Uso: python scripts/nova_ferramenta.py ferias
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z][a-z0-9_]*", sys.argv[1]):
        sys.exit("Uso: nova_ferramenta.py <slug_em_minusculas>")
    slug = sys.argv[1]
    nome = slug.replace("_", " ").title()
    pasta = RAIZ / "app" / "ferramentas" / slug
    if pasta.exists():
        sys.exit(f"Já existe: {pasta}")
    pasta.mkdir(parents=True)
    tpl = RAIZ / "app" / "templates" / slug
    tpl.mkdir(parents=True)

    (pasta / "__init__.py").write_text(f'''from app.ferramentas.{slug} import models  # noqa: F401
from app.ferramentas.{slug}.router import router

FERRAMENTA = {{
    "slug": "{slug}",
    "nome": "{nome}",
    "descricao": "Descreva aqui o objetivo da ferramenta.",
    "router": router,
}}
''', encoding="utf-8")
    (pasta / "models.py").write_text(f'''from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class {nome.replace(" ", "")}Item(Base):
    __tablename__ = "{slug}_itens"

    id: Mapped[int] = mapped_column(primary_key=True)
    membro_id: Mapped[int | None] = mapped_column(ForeignKey("membros.id"))
    descricao: Mapped[str] = mapped_column(String(200))
''', encoding="utf-8")
    (pasta / "router.py").write_text(f'''from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web import templates

router = APIRouter()


@router.get("/{slug}", response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request):
    return templates.TemplateResponse(request, "{slug}/index.html")
''', encoding="utf-8")
    (tpl / "index.html").write_text(f'''{{% extends "base.html" %}}
{{% block conteudo %}}
<h1>{nome}</h1>
<p>Comece a construir esta ferramenta.</p>
{{% endblock %}}
''', encoding="utf-8")

    reg = RAIZ / "app" / "ferramentas" / "__init__.py"
    txt = reg.read_text(encoding="utf-8")
    txt = txt.replace("from app.ferramentas import equipe",
                      f"from app.ferramentas import equipe\nfrom app.ferramentas import {slug}", 1)
    txt = txt.replace("    equipe.FERRAMENTA,\n", f"    equipe.FERRAMENTA,\n    {slug}.FERRAMENTA,\n", 1)
    reg.write_text(txt, encoding="utf-8")
    print(f"Ferramenta '{slug}' criada em {pasta.relative_to(RAIZ)} e registrada.")


if __name__ == "__main__":
    main()
