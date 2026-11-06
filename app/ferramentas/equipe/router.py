from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.ferramentas.equipe.models import Membro
from app.ferramentas.equipe.schemas import MembroAtualizar, MembroCriar, MembroOut
from app.web import templates

router = APIRouter()

# ---------- API JSON ----------


@router.get("/api/equipe", response_model=list[MembroOut], tags=["equipe"])
def listar(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    q = select(Membro).order_by(Membro.nome)
    if apenas_ativos:
        q = q.where(Membro.ativo.is_(True))
    return db.scalars(q).all()


@router.post("/api/equipe", response_model=MembroOut, status_code=201, tags=["equipe"])
def criar(dados: MembroCriar, db: Session = Depends(get_db)):
    membro = Membro(**dados.model_dump())
    db.add(membro)
    db.commit()
    return membro


@router.get("/api/equipe/{membro_id}", response_model=MembroOut, tags=["equipe"])
def obter(membro_id: int, db: Session = Depends(get_db)):
    membro = db.get(Membro, membro_id)
    if not membro:
        raise HTTPException(404, "Membro não encontrado")
    return membro


@router.patch("/api/equipe/{membro_id}", response_model=MembroOut, tags=["equipe"])
def atualizar(membro_id: int, dados: MembroAtualizar, db: Session = Depends(get_db)):
    membro = obter(membro_id, db)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(membro, campo, valor)
    db.commit()
    return membro


@router.delete("/api/equipe/{membro_id}", status_code=204, tags=["equipe"])
def remover(membro_id: int, db: Session = Depends(get_db)):
    db.delete(obter(membro_id, db))
    db.commit()


# ---------- Páginas ----------


@router.get("/equipe", response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request, db: Session = Depends(get_db)):
    membros = db.scalars(select(Membro).order_by(Membro.nome)).all()
    return templates.TemplateResponse(request, "equipe/lista.html", {"membros": membros})


@router.post("/equipe", include_in_schema=False)
def pagina_criar(
    nome: str = Form(...),
    email: str = Form(""),
    cargo: str = Form(""),
    area: str = Form(""),
    data_admissao: str = Form(""),
    db: Session = Depends(get_db),
):
    db.add(
        Membro(
            nome=nome,
            email=email or None,
            cargo=cargo or None,
            area=area or None,
            data_admissao=date.fromisoformat(data_admissao) if data_admissao else None,
        )
    )
    db.commit()
    return RedirectResponse("/equipe", status_code=303)


@router.post("/equipe/{membro_id}/alternar", include_in_schema=False)
def pagina_alternar(membro_id: int, db: Session = Depends(get_db)):
    membro = obter(membro_id, db)
    membro.ativo = not membro.ativo
    db.commit()
    return RedirectResponse("/equipe", status_code=303)
