from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.ferramentas.equipe import servico as equipe
from app.ferramentas.um_a_um import servico
from app.ferramentas.um_a_um.models import CARGA, HUMOR, RESPONSAVEIS, STATUS, Acao, Reuniao, Topico
from app.ferramentas.um_a_um.perguntas import PERGUNTAS, sugestoes
from app.ferramentas.um_a_um.schemas import (AcaoAtualizar, AcaoCriar, AcaoOut, ConfigAtualizar, ConfigOut,
                                             ReuniaoAtualizar, ReuniaoCriar, ReuniaoOut, SituacaoOut, TopicoCriar,
                                             TopicoOut)
from app.util import parse_data, parse_int
from app.web import redirecionar, templates

router = APIRouter()
TAG = ["1:1s"]
BASE = "/um_a_um"


# ======================= API =======================

@router.get("/api/um_a_um/situacao", response_model=list[SituacaoOut], tags=TAG)
def api_situacao(db: Session = Depends(get_db)):
    return [SituacaoOut(membro_id=s.membro.id, nome=s.membro.nome, estado=s.estado, cadencia=s.cadencia,
                        ultima=s.ultima.data if s.ultima else None, proxima=s.proxima, dias_atraso=s.dias_atraso,
                        humores=s.humores, cargas=s.cargas, acoes_abertas=s.acoes_abertas,
                        acoes_atrasadas=s.acoes_atrasadas, topicos=s.topicos) for s in servico.situacoes(db)]


@router.get("/api/um_a_um/reunioes", response_model=list[ReuniaoOut], tags=TAG)
def api_reunioes(membro_id: int | None = None, status: str | None = None, de: date | None = None,
                 ate: date | None = None, db: Session = Depends(get_db)):
    return servico.reunioes(db, membro_id, status, de, ate)


@router.post("/api/um_a_um/reunioes", response_model=ReuniaoOut, status_code=201, tags=TAG)
def api_criar_reuniao(dados: ReuniaoCriar, db: Session = Depends(get_db)):
    equipe.obter_membro(db, dados.membro_id)
    campos = dados.model_dump(exclude={"novas_acoes", "concluir_acoes", "topicos_discutidos"})
    return servico.registrar(db, Reuniao(**campos), [a.model_dump() for a in dados.novas_acoes],
                             dados.concluir_acoes, dados.topicos_discutidos)


@router.get("/api/um_a_um/reunioes/{reuniao_id}", response_model=ReuniaoOut, tags=TAG)
def api_obter_reuniao(reuniao_id: int, db: Session = Depends(get_db)):
    return servico.obter_reuniao(db, reuniao_id)


@router.patch("/api/um_a_um/reunioes/{reuniao_id}", response_model=ReuniaoOut, tags=TAG)
def api_atualizar_reuniao(reuniao_id: int, dados: ReuniaoAtualizar, db: Session = Depends(get_db)):
    r = servico.obter_reuniao(db, reuniao_id)
    for k, v in dados.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    return r


@router.delete("/api/um_a_um/reunioes/{reuniao_id}", status_code=204, tags=TAG)
def api_remover_reuniao(reuniao_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter_reuniao(db, reuniao_id))
    db.commit()


@router.get("/api/um_a_um/acoes", response_model=list[AcaoOut], tags=TAG)
def api_acoes(membro_id: int | None = None, abertas: bool | None = None, responsavel: str | None = None,
              db: Session = Depends(get_db)):
    return servico.acoes(db, membro_id, abertas, responsavel)


@router.post("/api/um_a_um/acoes", response_model=AcaoOut, status_code=201, tags=TAG)
def api_criar_acao(dados: AcaoCriar, db: Session = Depends(get_db)):
    equipe.obter_membro(db, dados.membro_id)
    a = Acao(**dados.model_dump())
    db.add(a)
    db.commit()
    return a


@router.patch("/api/um_a_um/acoes/{acao_id}", response_model=AcaoOut, tags=TAG)
def api_atualizar_acao(acao_id: int, dados: AcaoAtualizar, db: Session = Depends(get_db)):
    a = servico.obter_acao(db, acao_id)
    d = dados.model_dump(exclude_unset=True)
    if "concluida" in d:
        servico.concluir_acao(a, d.pop("concluida"))
    for k, v in d.items():
        setattr(a, k, v)
    db.commit()
    return a


@router.delete("/api/um_a_um/acoes/{acao_id}", status_code=204, tags=TAG)
def api_remover_acao(acao_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter_acao(db, acao_id))
    db.commit()


@router.get("/api/um_a_um/topicos/{membro_id}", response_model=list[TopicoOut], tags=TAG,
            summary="Tópicos pendentes para a próxima 1:1")
def api_topicos(membro_id: int, db: Session = Depends(get_db)):
    return servico.topicos_pendentes(db, membro_id)


@router.post("/api/um_a_um/topicos", response_model=TopicoOut, status_code=201, tags=TAG)
def api_criar_topico(dados: TopicoCriar, db: Session = Depends(get_db)):
    equipe.obter_membro(db, dados.membro_id)
    t = Topico(**dados.model_dump())
    db.add(t)
    db.commit()
    return t


@router.delete("/api/um_a_um/topicos/{topico_id}", status_code=204, tags=TAG)
def api_remover_topico(topico_id: int, db: Session = Depends(get_db)):
    t = db.get(Topico, topico_id)
    if not t:
        raise HTTPException(404, "Tópico não encontrado")
    db.delete(t)
    db.commit()


@router.get("/api/um_a_um/config/{membro_id}", response_model=ConfigOut, tags=TAG)
def api_config(membro_id: int, db: Session = Depends(get_db)):
    equipe.obter_membro(db, membro_id)
    c = servico.config(db, membro_id)
    db.commit()
    return c


@router.patch("/api/um_a_um/config/{membro_id}", response_model=ConfigOut, tags=TAG)
def api_config_atualizar(membro_id: int, dados: ConfigAtualizar, db: Session = Depends(get_db)):
    equipe.obter_membro(db, membro_id)
    c = servico.config(db, membro_id)
    for k, v in dados.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    return c


# ======================= Páginas =======================

@router.get(BASE, response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request, db: Session = Depends(get_db)):
    sits = servico.situacoes(db)
    hoje = date.today()
    return templates.TemplateResponse(request, "um_a_um/index.html", {
        "situacoes": sits, "estados": servico.ESTADOS,
        "agenda": sorted(servico.reunioes(db, status="agendada", de=hoje), key=lambda r: r.data)[:10],
        "recentes": servico.reunioes(db, status="realizada", ate=hoje)[:8],
    })


@router.get(BASE + "/acoes", response_class=HTMLResponse, include_in_schema=False)
def pagina_acoes(request: Request, responsavel: str = "", ver: str = "abertas", db: Session = Depends(get_db)):
    abertas = None if ver == "todas" else (ver == "abertas")
    return templates.TemplateResponse(request, "um_a_um/acoes.html", {
        "acoes": servico.acoes(db, abertas=abertas, responsavel=responsavel or None),
        "responsavel": responsavel, "ver": ver, "responsaveis": RESPONSAVEIS,
        "membros": equipe.membros(db, apenas_ativos=True)})


@router.post(BASE + "/acoes", include_in_schema=False)
def pagina_criar_acao(membro_id: int = Form(...), descricao: str = Form(...), responsavel: str = Form("membro"),
                      prazo: str = Form(""), voltar: str = Form(""), db: Session = Depends(get_db)):
    equipe.obter_membro(db, membro_id)
    db.add(Acao(membro_id=membro_id, descricao=descricao.strip(), responsavel=responsavel, prazo=parse_data(prazo)))
    db.commit()
    return redirecionar(voltar if voltar.startswith("/") else BASE + "/acoes", msg="Ação criada.")


@router.post(BASE + "/acoes/{acao_id}/alternar", include_in_schema=False)
def pagina_alternar_acao(acao_id: int, voltar: str = Form(""), db: Session = Depends(get_db)):
    a = servico.obter_acao(db, acao_id)
    servico.concluir_acao(a, not a.concluida)
    db.commit()
    return redirecionar(voltar if voltar.startswith("/") else BASE + "/acoes")


@router.post(BASE + "/acoes/{acao_id}/excluir", include_in_schema=False)
def pagina_excluir_acao(acao_id: int, voltar: str = Form(""), db: Session = Depends(get_db)):
    db.delete(servico.obter_acao(db, acao_id))
    db.commit()
    return redirecionar(voltar if voltar.startswith("/") else BASE + "/acoes", msg="Ação excluída.")


@router.get(BASE + "/pessoa/{membro_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_pessoa(request: Request, membro_id: int, db: Session = Depends(get_db)):
    m = equipe.obter_membro(db, membro_id)
    sit = servico.situacao(db, m)
    db.commit()
    hist = servico.reunioes(db, membro_id=membro_id)
    return templates.TemplateResponse(request, "um_a_um/pessoa.html", {
        "m": m, "s": sit, "estados": servico.ESTADOS, "reunioes": hist,
        "topicos": servico.topicos_pendentes(db, membro_id), "acoes": servico.acoes(db, membro_id=membro_id),
        "serie": [r for r in reversed(hist) if r.status == "realizada"][-12:], "responsaveis": RESPONSAVEIS})


@router.post(BASE + "/pessoa/{membro_id}/config", include_in_schema=False)
def pagina_config(membro_id: int, cadencia_dias: int = Form(...), pausado: str = Form(""),
                  db: Session = Depends(get_db)):
    c = servico.config(db, equipe.obter_membro(db, membro_id).id)
    c.cadencia_dias = max(1, min(cadencia_dias, 120))
    c.pausado = bool(pausado)
    db.commit()
    return redirecionar(f"{BASE}/pessoa/{membro_id}", msg="Configuração salva.")


@router.post(BASE + "/pessoa/{membro_id}/topicos", include_in_schema=False)
def pagina_topico(membro_id: int, texto: str = Form(...), autor: str = Form("gestor"), voltar: str = Form(""),
                  db: Session = Depends(get_db)):
    equipe.obter_membro(db, membro_id)
    if texto.strip():
        db.add(Topico(membro_id=membro_id, texto=texto.strip()[:300], autor=autor))
        db.commit()
    return redirecionar(voltar if voltar.startswith("/") else f"{BASE}/pessoa/{membro_id}", msg="Tópico anotado.")


@router.post(BASE + "/topicos/{topico_id}/excluir", include_in_schema=False)
def pagina_excluir_topico(topico_id: int, db: Session = Depends(get_db)):
    t = db.get(Topico, topico_id)
    if not t:
        raise HTTPException(404)
    db.delete(t)
    db.commit()
    return redirecionar(f"{BASE}/pessoa/{t.membro_id}")


def _ctx_form(db, membro_id: int | None):
    ctx = {"membros": equipe.membros(db, apenas_ativos=True), "humores": HUMOR, "cargas": CARGA,
           "responsaveis": RESPONSAVEIS, "status_opcoes": STATUS, "perguntas": PERGUNTAS,
           "sugestoes": sugestoes(3), "topicos": [], "abertas": [], "pauta_inicial": ""}
    if membro_id:
        ctx.update(topicos=servico.topicos_pendentes(db, membro_id),
                   abertas=servico.acoes(db, membro_id=membro_id, abertas=True),
                   pauta_inicial=servico.montar_pauta(db, membro_id))
    return ctx


@router.get(BASE + "/nova", response_class=HTMLResponse, include_in_schema=False)
def pagina_nova(request: Request, membro_id: str = "", db: Session = Depends(get_db)):
    mid = parse_int(membro_id)
    return templates.TemplateResponse(request, "um_a_um/form.html", {
        **_ctx_form(db, mid), "r": None, "membro_id": mid})


def _ler_form(form) -> dict:
    return {
        "data": parse_data(form.get("data")) or date.today(),
        "status": form.get("status") or "realizada",
        "humor": parse_int(form.get("humor")),
        "carga": parse_int(form.get("carga")),
        "pauta": (form.get("pauta") or "").strip() or None,
        "anotacoes": (form.get("anotacoes") or "").strip() or None,
        "notas_privadas": (form.get("notas_privadas") or "").strip() or None,
    }


def _novas_acoes(form) -> list[dict]:
    descs, resps, prazos = form.getlist("acao_descricao"), form.getlist("acao_responsavel"), form.getlist("acao_prazo")
    return [{"descricao": d, "responsavel": r, "prazo": parse_data(p)} for d, r, p in zip(descs, resps, prazos)]


@router.post(BASE + "/nova", include_in_schema=False)
async def pagina_criar(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    m = equipe.obter_membro(db, int(form["membro_id"]))
    r = Reuniao(membro_id=m.id, **_ler_form(form))
    try:
        servico.registrar(db, r, _novas_acoes(form), [int(x) for x in form.getlist("concluir")],
                          [int(x) for x in form.getlist("topico")])
    except HTTPException as e:
        db.rollback()
        return redirecionar(f"{BASE}/nova?membro_id={m.id}", erro=e.detail)
    return redirecionar(f"{BASE}/{r.id}", msg=f"1:1 com {m.primeiro_nome} {'agendada' if r.status == 'agendada' else 'registrada'}.")


@router.get(BASE + "/{reuniao_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_reuniao(request: Request, reuniao_id: int, editar: str = "", db: Session = Depends(get_db)):
    r = servico.obter_reuniao(db, reuniao_id)
    if editar:
        return templates.TemplateResponse(request, "um_a_um/form.html", {
            **_ctx_form(db, r.membro_id), "r": r, "membro_id": r.membro_id})
    anterior = next((x for x in servico.reunioes(db, membro_id=r.membro_id, status="realizada")
                     if (x.data, x.id) < (r.data, r.id)), None)
    return templates.TemplateResponse(request, "um_a_um/reuniao.html", {
        "r": r, "anterior": anterior, "responsaveis": RESPONSAVEIS})


@router.post(BASE + "/{reuniao_id}", include_in_schema=False)
async def pagina_salvar(request: Request, reuniao_id: int, db: Session = Depends(get_db)):
    r = servico.obter_reuniao(db, reuniao_id)
    form = await request.form()
    for k, v in _ler_form(form).items():
        setattr(r, k, v)
    try:
        servico.registrar(db, r, _novas_acoes(form), [int(x) for x in form.getlist("concluir")],
                          [int(x) for x in form.getlist("topico")])
    except HTTPException as e:
        db.rollback()
        return redirecionar(f"{BASE}/{reuniao_id}?editar=1", erro=e.detail)
    return redirecionar(f"{BASE}/{r.id}", msg="1:1 atualizada.")


@router.post(BASE + "/{reuniao_id}/excluir", include_in_schema=False)
def pagina_excluir(reuniao_id: int, db: Session = Depends(get_db)):
    r = servico.obter_reuniao(db, reuniao_id)
    mid = r.membro_id
    db.delete(r)
    db.commit()
    return redirecionar(f"{BASE}/pessoa/{mid}", msg="Reunião excluída.")
