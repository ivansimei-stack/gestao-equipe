from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.ferramentas.competencias import servico
from app.ferramentas.competencias.models import NIVEIS, Competencia
from app.ferramentas.equipe import servico as equipe
from app.util import parse_int
from app.web import redirecionar, templates

router = APIRouter()
TAG = ["competencias"]
B = "/competencias"


class CompetenciaIn(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    categoria: str = "Geral"
    descricao: str | None = None
    nivel_esperado: int = Field(default=2, ge=0, le=4)
    critica: bool = False
    minimo_pessoas: int = Field(default=2, ge=1, le=20)


class CompetenciaAtualizar(BaseModel):
    nome: str | None = Field(default=None, max_length=100)
    categoria: str | None = None
    descricao: str | None = None
    nivel_esperado: int | None = Field(default=None, ge=0, le=4)
    critica: bool | None = None
    minimo_pessoas: int | None = Field(default=None, ge=1, le=20)
    ativa: bool | None = None


class CompetenciaOut(CompetenciaIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ativa: bool


class NivelIn(BaseModel):
    nivel: int | None = Field(default=None, ge=0, le=4)
    interesse: bool | None = None


class NivelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    membro_id: int
    competencia_id: int
    nivel: int
    interesse: bool


class AnaliseOut(BaseModel):
    competencia_id: int
    nome: str
    fator_onibus: int
    risco: str
    media: float
    detentores: list[int]
    interessados: list[int]
    dias_descobertos: list[date]


# ======================= API =======================

@router.get("/api/competencias", response_model=list[CompetenciaOut], tags=TAG)
def api_listar(incluir_inativas: bool = False, db: Session = Depends(get_db)):
    return servico.competencias(db, apenas_ativas=not incluir_inativas)


@router.post("/api/competencias", response_model=CompetenciaOut, status_code=201, tags=TAG)
def api_criar(dados: CompetenciaIn, db: Session = Depends(get_db)):
    c = Competencia(**dados.model_dump())
    servico.validar(c)
    db.add(c)
    db.commit()
    return c


@router.patch("/api/competencias/{competencia_id}", response_model=CompetenciaOut, tags=TAG)
def api_atualizar(competencia_id: int, dados: CompetenciaAtualizar, db: Session = Depends(get_db)):
    c = servico.obter(db, competencia_id)
    for k, v in dados.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    servico.validar(c)
    db.commit()
    return c


@router.delete("/api/competencias/{competencia_id}", status_code=204, tags=TAG)
def api_remover(competencia_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, competencia_id))
    db.commit()


@router.get("/api/competencias/matriz", response_model=list[NivelOut], tags=TAG)
def api_matriz(db: Session = Depends(get_db)):
    return list(servico.niveis(db).values())


@router.put("/api/competencias/{competencia_id}/membros/{membro_id}", response_model=NivelOut, tags=TAG)
def api_definir(competencia_id: int, membro_id: int, dados: NivelIn, db: Session = Depends(get_db)):
    servico.obter(db, competencia_id)
    equipe.obter_membro(db, membro_id)
    return servico.definir(db, membro_id, competencia_id, dados.nivel, dados.interesse)


@router.get("/api/competencias/analise", response_model=list[AnaliseOut], tags=TAG)
def api_analise(db: Session = Depends(get_db)):
    return [AnaliseOut(competencia_id=a.competencia.id, nome=a.competencia.nome, fator_onibus=a.fator_onibus,
                       risco=a.risco, media=a.media, detentores=[m.id for m in a.detentores],
                       interessados=[m.id for m in a.interessados], dias_descobertos=a.dias_descobertos)
            for a in servico.analisar(db)]


# ======================= Páginas =======================

def _ctx(db):
    return {"niveis_nomes": NIVEIS, "riscos": servico.RISCOS, "categorias": servico.categorias(db)}


@router.get(B, response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request, area: str = "", categoria: str = "", editar: str = "", db: Session = Depends(get_db)):
    comps = servico.competencias(db, categoria=categoria or None)
    membros = equipe.membros(db, apenas_ativos=True, area=area or None)
    analises = {a.competencia.id: a for a in servico.analisar(db, area=area or None)}
    return templates.TemplateResponse(request, "competencias/matriz.html", {
        **_ctx(db), "comps": comps, "membros": membros, "mapa": servico.niveis(db), "analises": analises,
        "areas": equipe.areas(db), "area": area, "categoria": categoria, "editar": bool(editar)})


@router.post(B + "/matriz", include_in_schema=False)
async def pagina_salvar_matriz(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    alterados = 0
    for chave, valor in form.items():
        if chave.startswith("n_"):
            _, mid, cid = chave.split("_")
            nivel = parse_int(valor)
            interesse = form.get(f"i_{mid}_{cid}") is not None
            atual = servico.niveis(db).get((int(mid), int(cid)))
            if atual is None and not nivel and not interesse:
                continue
            if atual is None or atual.nivel != nivel or atual.interesse != interesse:
                servico.definir(db, int(mid), int(cid), nivel or 0, interesse, commit=False)
                alterados += 1
    db.commit()
    voltar = form.get("voltar") or B
    return redirecionar(voltar if voltar.startswith("/") else B, msg=f"{alterados} nível(is) atualizado(s).")


@router.get(B + "/riscos", response_class=HTMLResponse, include_in_schema=False)
def pagina_riscos(request: Request, db: Session = Depends(get_db)):
    analises = servico.analisar(db)
    ordem = {"sem_cobertura": 0, "alto": 1, "medio": 2, "ok": 3}
    analises.sort(key=lambda a: (ordem[a.risco], not a.competencia.critica, a.fator_onibus))
    return templates.TemplateResponse(request, "competencias/riscos.html", {
        **_ctx(db), "analises": analises, "mentorias": servico.mentorias(analises, db),
        "descobertos": [a for a in analises if a.dias_descobertos]})


@router.post(B + "/mentoria-pdi", include_in_schema=False)
def pagina_mentoria_pdi(competencia_id: int = Form(...), mentor_id: int = Form(...), aprendiz_id: int = Form(...),
                        db: Session = Depends(get_db)):
    from app.ferramentas.avaliacoes.models import ItemPDI
    from app.ferramentas.avaliacoes.servico import ciclo_atual
    c = servico.obter(db, competencia_id)
    mentor, aprendiz = equipe.obter_membro(db, mentor_id), equipe.obter_membro(db, aprendiz_id)
    ciclo = ciclo_atual(db)
    db.add(ItemPDI(membro_id=aprendiz.id, ciclo_id=ciclo.id if ciclo else None, tipo="social",
                   descricao=f"Desenvolver {c.nome} com mentoria de {mentor.nome}"[:300],
                   prazo=date.today() + timedelta(days=90)))
    servico.definir(db, aprendiz.id, c.id, interesse=True, commit=False)
    db.commit()
    return redirecionar(B + "/riscos", msg=f"Item de PDI criado para {aprendiz.nome}.")


@router.get(B + "/catalogo", response_class=HTMLResponse, include_in_schema=False)
def pagina_catalogo(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "competencias/catalogo.html", {
        **_ctx(db), "comps": servico.competencias(db, apenas_ativas=False)})


def _ler(form, c: Competencia) -> Competencia:
    c.nome = (form.get("nome") or "").strip()
    c.categoria = (form.get("categoria") or "").strip() or "Geral"
    c.descricao = (form.get("descricao") or "").strip() or None
    c.nivel_esperado = parse_int(form.get("nivel_esperado")) or 0
    c.minimo_pessoas = parse_int(form.get("minimo_pessoas")) or 2
    c.critica = bool(form.get("critica"))
    return c


@router.post(B + "/catalogo", include_in_schema=False)
async def pagina_criar(request: Request, db: Session = Depends(get_db)):
    c = _ler(await request.form(), Competencia(ativa=True))
    try:
        servico.validar(c)
    except HTTPException as e:
        return redirecionar(B + "/catalogo", erro=e.detail)
    db.add(c)
    db.commit()
    return redirecionar(B + "/catalogo", msg=f"Competência “{c.nome}” criada.")


@router.post(B + "/catalogo/exemplos", include_in_schema=False)
def pagina_exemplos(db: Session = Depends(get_db)):
    n = servico.criar_exemplos(db)
    return redirecionar(B + "/catalogo", msg=f"{n} competência(s) de exemplo adicionada(s).")


@router.post(B + "/catalogo/{competencia_id}", include_in_schema=False)
async def pagina_salvar(request: Request, competencia_id: int, db: Session = Depends(get_db)):
    c = servico.obter(db, competencia_id)
    form = await request.form()
    _ler(form, c)
    c.ativa = bool(form.get("ativa"))
    try:
        servico.validar(c)
    except HTTPException as e:
        db.rollback()
        return redirecionar(B + "/catalogo", erro=e.detail)
    db.commit()
    return redirecionar(B + "/catalogo", msg="Competência atualizada.")


@router.post(B + "/catalogo/{competencia_id}/excluir", include_in_schema=False)
def pagina_excluir(competencia_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, competencia_id))
    db.commit()
    return redirecionar(B + "/catalogo", msg="Competência excluída.")


@router.get(B + "/pessoa/{membro_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_pessoa(request: Request, membro_id: int, db: Session = Depends(get_db)):
    m = equipe.obter_membro(db, membro_id)
    return templates.TemplateResponse(request, "competencias/pessoa.html", {
        **_ctx(db), "m": m, "linhas": servico.perfil_membro(db, m)})
