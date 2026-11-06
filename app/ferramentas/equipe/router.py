from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.ferramentas.equipe import servico
from app.ferramentas.equipe.models import Membro
from app.ferramentas.equipe.schemas import MembroAtualizar, MembroCriar, MembroOut
from app.util import parse_data
from app.web import redirecionar, templates

router = APIRouter()

# ---------- API JSON ----------


@router.get("/api/equipe", response_model=list[MembroOut], tags=["equipe"])
def listar(apenas_ativos: bool = False, area: str | None = None, db: Session = Depends(get_db)):
    return servico.membros(db, apenas_ativos, area)


@router.post("/api/equipe", response_model=MembroOut, status_code=201, tags=["equipe"])
def criar(dados: MembroCriar, db: Session = Depends(get_db)):
    return servico.salvar(db, Membro(**dados.model_dump()))


@router.get("/api/equipe/{membro_id}", response_model=MembroOut, tags=["equipe"])
def obter(membro_id: int, db: Session = Depends(get_db)):
    return servico.obter_membro(db, membro_id)


@router.patch("/api/equipe/{membro_id}", response_model=MembroOut, tags=["equipe"])
def atualizar(membro_id: int, dados: MembroAtualizar, db: Session = Depends(get_db)):
    membro = servico.obter_membro(db, membro_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(membro, campo, valor)
    return servico.salvar(db, membro)


@router.delete("/api/equipe/{membro_id}", status_code=204, tags=["equipe"])
def remover(membro_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter_membro(db, membro_id))
    db.commit()


# ---------- Páginas ----------

CAMPOS_TEXTO = ("email", "telefone", "cargo", "area", "observacoes")


def _preencher(m: Membro, form: dict) -> Membro:
    m.nome = form["nome"].strip()
    for c in CAMPOS_TEXTO:
        setattr(m, c, (form.get(c) or "").strip() or None)
    m.data_admissao = parse_data(form.get("data_admissao"))
    m.data_nascimento = parse_data(form.get("data_nascimento"))
    return m


@router.get("/equipe", response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request, area: str = "", status: str = "ativos", db: Session = Depends(get_db)):
    lista = servico.membros(db, area=area or None)
    if status == "ativos":
        lista = [m for m in lista if m.ativo]
    elif status == "inativos":
        lista = [m for m in lista if not m.ativo]
    return templates.TemplateResponse(request, "equipe/lista.html", {
        "membros": lista, "areas": servico.areas(db), "area": area, "status": status,
        "aniversariantes": servico.aniversariantes(db), "aniv_empresa": servico.aniversarios_de_empresa(db),
    })


@router.get("/equipe/novo", response_class=HTMLResponse, include_in_schema=False)
def pagina_novo(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "equipe/form.html", {"m": None, "areas": servico.areas(db)})


@router.post("/equipe/novo", include_in_schema=False)
async def pagina_criar(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    m = servico.salvar(db, _preencher(Membro(ativo=True), form))
    return redirecionar(f"/equipe/{m.id}", msg=f"{m.nome} adicionado(a) à equipe.")


@router.get("/equipe/{membro_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_perfil(request: Request, membro_id: int, db: Session = Depends(get_db)):
    from app.ferramentas import FERRAMENTAS

    m = servico.obter_membro(db, membro_id)
    secoes = []
    for f in FERRAMENTAS:
        if f.get("perfil"):
            dados = f["perfil"](db, m)
            if dados is not None:
                secoes.append({"ferramenta": f, "p": dados})
    return templates.TemplateResponse(request, "equipe/perfil.html", {"m": m, "secoes": secoes})


@router.get("/equipe/{membro_id}/editar", response_class=HTMLResponse, include_in_schema=False)
def pagina_editar(request: Request, membro_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "equipe/form.html", {
        "m": servico.obter_membro(db, membro_id), "areas": servico.areas(db)})


@router.post("/equipe/{membro_id}/editar", include_in_schema=False)
async def pagina_salvar(request: Request, membro_id: int, db: Session = Depends(get_db)):
    m = servico.obter_membro(db, membro_id)
    servico.salvar(db, _preencher(m, dict(await request.form())))
    return redirecionar(f"/equipe/{m.id}", msg="Dados atualizados.")


@router.post("/equipe/{membro_id}/alternar", include_in_schema=False)
def pagina_alternar(membro_id: int, db: Session = Depends(get_db)):
    m = servico.obter_membro(db, membro_id)
    m.ativo = not m.ativo
    db.commit()
    return redirecionar(f"/equipe/{m.id}", msg=f"{m.nome} marcado(a) como {'ativo' if m.ativo else 'inativo'}.")


@router.post("/equipe/{membro_id}/excluir", include_in_schema=False)
def pagina_excluir(membro_id: int, confirmacao: str = Form(""), db: Session = Depends(get_db)):
    m = servico.obter_membro(db, membro_id)
    if confirmacao.strip().lower() != m.primeiro_nome.lower():
        return redirecionar(f"/equipe/{m.id}", erro="Digite o primeiro nome para confirmar a exclusão.")
    db.delete(m)
    db.commit()
    return redirecionar("/equipe", msg=f"{m.nome} excluído(a) com todos os registros.")
