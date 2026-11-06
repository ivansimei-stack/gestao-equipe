from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.ferramentas.equipe import servico as equipe
from app.ferramentas.okrs import servico
from app.ferramentas.okrs.models import TIPOS_KR, Checkin, Ciclo, Objetivo, ResultadoChave
from app.ferramentas.okrs.schemas import (CheckinCriar, CheckinOut, CicloAtualizar, CicloCriar, CicloOut, KRAtualizar,
                                          KRCriar, KROut, ObjetivoAtualizar, ObjetivoCriar, ObjetivoOut)
from app.util import parse_data, parse_int
from app.web import redirecionar, templates

router = APIRouter()
TAG = ["okrs"]


def _kr_out(k: ResultadoChave) -> KROut:
    return KROut.model_validate(k).model_copy(update={
        "progresso": servico.progresso_kr(k), "status": servico.status_kr(k), "projecao": servico.projecao_kr(k)})


def _obj_out(o: Objetivo) -> ObjetivoOut:
    return ObjetivoOut(id=o.id, ciclo_id=o.ciclo_id, titulo=o.titulo, descricao=o.descricao, dono_id=o.dono_id,
                       progresso=servico.progresso_objetivo(o), status=servico.status_objetivo(o),
                       krs=[_kr_out(k) for k in o.krs])


def _ciclo_out(c: Ciclo, detalhado: bool = True) -> CicloOut:
    return CicloOut(id=c.id, nome=c.nome, inicio=c.inicio, fim=c.fim, arquivado=c.arquivado,
                    progresso=servico.progresso_ciclo(c), tempo_decorrido=servico.fracao_tempo(c),
                    objetivos=[_obj_out(o) for o in c.objetivos] if detalhado else [])


def _membro_opcional(db, mid):
    if mid is not None:
        equipe.obter_membro(db, mid)
    return mid


# ======================= API =======================

@router.get("/api/okrs/ciclos", response_model=list[CicloOut], tags=TAG)
def api_ciclos(db: Session = Depends(get_db)):
    return [_ciclo_out(c, detalhado=False) for c in servico.ciclos(db)]


@router.post("/api/okrs/ciclos", response_model=CicloOut, status_code=201, tags=TAG)
def api_criar_ciclo(dados: CicloCriar, db: Session = Depends(get_db)):
    c = Ciclo(**dados.model_dump())
    servico.validar_ciclo(c)
    db.add(c)
    db.commit()
    return _ciclo_out(c)


@router.get("/api/okrs/ciclos/atual", response_model=CicloOut | None, tags=TAG)
def api_ciclo_atual(db: Session = Depends(get_db)):
    c = servico.ciclo_atual(db)
    return _ciclo_out(c) if c else None


@router.get("/api/okrs/ciclos/{ciclo_id}", response_model=CicloOut, tags=TAG)
def api_ciclo(ciclo_id: int, db: Session = Depends(get_db)):
    return _ciclo_out(servico.obter(db, Ciclo, ciclo_id))


@router.patch("/api/okrs/ciclos/{ciclo_id}", response_model=CicloOut, tags=TAG)
def api_atualizar_ciclo(ciclo_id: int, dados: CicloAtualizar, db: Session = Depends(get_db)):
    c = servico.obter(db, Ciclo, ciclo_id)
    for k, v in dados.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    servico.validar_ciclo(c)
    db.commit()
    return _ciclo_out(c)


@router.delete("/api/okrs/ciclos/{ciclo_id}", status_code=204, tags=TAG)
def api_remover_ciclo(ciclo_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, Ciclo, ciclo_id))
    db.commit()


@router.post("/api/okrs/ciclos/{ciclo_id}/objetivos", response_model=ObjetivoOut, status_code=201, tags=TAG)
def api_criar_objetivo(ciclo_id: int, dados: ObjetivoCriar, db: Session = Depends(get_db)):
    c = servico.obter(db, Ciclo, ciclo_id)
    o = Objetivo(ciclo=c, **dados.model_dump(exclude={"krs"}))
    _membro_opcional(db, o.dono_id)
    for kd in dados.krs:
        k = ResultadoChave(**kd.model_dump(), valor_atual=kd.valor_inicial)
        servico.validar_kr(k)
        o.krs.append(k)
    db.add(o)
    db.commit()
    return _obj_out(o)


@router.patch("/api/okrs/objetivos/{objetivo_id}", response_model=ObjetivoOut, tags=TAG)
def api_atualizar_objetivo(objetivo_id: int, dados: ObjetivoAtualizar, db: Session = Depends(get_db)):
    o = servico.obter(db, Objetivo, objetivo_id)
    d = dados.model_dump(exclude_unset=True)
    _membro_opcional(db, d.get("dono_id"))
    for k, v in d.items():
        setattr(o, k, v)
    db.commit()
    return _obj_out(o)


@router.delete("/api/okrs/objetivos/{objetivo_id}", status_code=204, tags=TAG)
def api_remover_objetivo(objetivo_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, Objetivo, objetivo_id))
    db.commit()


@router.post("/api/okrs/objetivos/{objetivo_id}/krs", response_model=KROut, status_code=201, tags=TAG)
def api_criar_kr(objetivo_id: int, dados: KRCriar, db: Session = Depends(get_db)):
    o = servico.obter(db, Objetivo, objetivo_id)
    _membro_opcional(db, dados.responsavel_id)
    k = ResultadoChave(objetivo=o, **dados.model_dump(), valor_atual=dados.valor_inicial)
    servico.validar_kr(k)
    db.add(k)
    db.commit()
    return _kr_out(k)


@router.get("/api/okrs/krs/{kr_id}", response_model=KROut, tags=TAG)
def api_kr(kr_id: int, db: Session = Depends(get_db)):
    return _kr_out(servico.obter(db, ResultadoChave, kr_id))


@router.patch("/api/okrs/krs/{kr_id}", response_model=KROut, tags=TAG)
def api_atualizar_kr(kr_id: int, dados: KRAtualizar, db: Session = Depends(get_db)):
    k = servico.obter(db, ResultadoChave, kr_id)
    d = dados.model_dump(exclude_unset=True)
    _membro_opcional(db, d.get("responsavel_id"))
    for c, v in d.items():
        setattr(k, c, v)
    try:
        servico.validar_kr(k)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return _kr_out(k)


@router.delete("/api/okrs/krs/{kr_id}", status_code=204, tags=TAG)
def api_remover_kr(kr_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, ResultadoChave, kr_id))
    db.commit()


@router.post("/api/okrs/krs/{kr_id}/checkins", response_model=CheckinOut, status_code=201, tags=TAG)
def api_checkin(kr_id: int, dados: CheckinCriar, db: Session = Depends(get_db)):
    k = servico.obter(db, ResultadoChave, kr_id)
    return servico.registrar_checkin(db, k, dados.valor, dados.confianca, dados.comentario, dados.data)


@router.delete("/api/okrs/checkins/{checkin_id}", status_code=204, tags=TAG)
def api_remover_checkin(checkin_id: int, db: Session = Depends(get_db)):
    ch = servico.obter(db, Checkin, checkin_id)
    k = ch.kr
    db.delete(ch)
    db.flush()
    db.refresh(k)
    k.valor_atual = k.checkins[-1].valor if k.checkins else k.valor_inicial
    db.commit()


# ======================= Páginas =======================

def _ctx_base(db):
    return {"membros": equipe.membros(db, apenas_ativos=True), "tipos": TIPOS_KR, "status_nomes": servico.STATUS,
            "sv": servico}


@router.get("/okrs", response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request, ciclo: str = "", dono: str = "", db: Session = Depends(get_db)):
    c = servico.obter(db, Ciclo, int(ciclo)) if ciclo else servico.ciclo_atual(db)
    objetivos = c.objetivos if c else []
    if dono == "equipe":
        objetivos = [o for o in objetivos if o.dono_id is None]
    elif dono:
        objetivos = [o for o in objetivos if o.dono_id == int(dono) or any(k.responsavel_id == int(dono) for k in o.krs)]
    return templates.TemplateResponse(request, "okrs/index.html", {
        **_ctx_base(db), "c": c, "objetivos": objetivos, "ciclos": servico.ciclos(db), "dono": dono,
        "resumo": servico.resumo_ciclo(c) if c else None})


@router.get("/okrs/ciclos", response_class=HTMLResponse, include_in_schema=False)
def pagina_ciclos(request: Request, db: Session = Depends(get_db)):
    lista = servico.ciclos(db)
    return templates.TemplateResponse(request, "okrs/ciclos.html", {
        **_ctx_base(db), "ciclos": lista, "sugestao": servico.sugerir_proximo_ciclo(lista[0] if lista else None)})


@router.post("/okrs/ciclos", include_in_schema=False)
def pagina_criar_ciclo(nome: str = Form(...), inicio: str = Form(...), fim: str = Form(...),
                       copiar_de: str = Form(""), partir_do_atual: str = Form(""), db: Session = Depends(get_db)):
    try:
        if copiar_de:
            c = servico.duplicar_ciclo(db, servico.obter(db, Ciclo, int(copiar_de)), nome.strip(),
                                       parse_data(inicio), parse_data(fim), bool(partir_do_atual))
        else:
            c = Ciclo(nome=nome.strip(), inicio=parse_data(inicio), fim=parse_data(fim))
            servico.validar_ciclo(c)
            db.add(c)
            db.commit()
    except HTTPException as e:
        db.rollback()
        return redirecionar("/okrs/ciclos", erro=e.detail)
    return redirecionar(f"/okrs?ciclo={c.id}", msg=f"Ciclo {c.nome} criado.")


@router.post("/okrs/ciclos/{ciclo_id}", include_in_schema=False)
def pagina_salvar_ciclo(ciclo_id: int, nome: str = Form(...), inicio: str = Form(...), fim: str = Form(...),
                        arquivado: str = Form(""), db: Session = Depends(get_db)):
    c = servico.obter(db, Ciclo, ciclo_id)
    c.nome, c.inicio, c.fim, c.arquivado = nome.strip(), parse_data(inicio), parse_data(fim), bool(arquivado)
    try:
        servico.validar_ciclo(c)
    except HTTPException as e:
        db.rollback()
        return redirecionar("/okrs/ciclos", erro=e.detail)
    db.commit()
    return redirecionar("/okrs/ciclos", msg="Ciclo atualizado.")


@router.post("/okrs/ciclos/{ciclo_id}/excluir", include_in_schema=False)
def pagina_excluir_ciclo(ciclo_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, Ciclo, ciclo_id))
    db.commit()
    return redirecionar("/okrs/ciclos", msg="Ciclo excluído.")


def _ler_kr(form, k: ResultadoChave, prefixo: str = "") -> ResultadoChave:
    g = lambda c: form.get(prefixo + c)  # noqa: E731
    k.descricao = (g("descricao") or "").strip()
    k.tipo = g("tipo") or "numero"
    k.valor_inicial = float(g("valor_inicial") or 0)
    k.valor_alvo = float(g("valor_alvo") or (1 if k.tipo == "binario" else 0))
    k.unidade = (g("unidade") or "").strip() or None
    k.responsavel_id = parse_int(g("responsavel_id"))
    return k


@router.get("/okrs/ciclos/{ciclo_id}/objetivo", response_class=HTMLResponse, include_in_schema=False)
def pagina_novo_objetivo(request: Request, ciclo_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "okrs/objetivo_form.html", {
        **_ctx_base(db), "c": servico.obter(db, Ciclo, ciclo_id), "o": None})


@router.post("/okrs/ciclos/{ciclo_id}/objetivo", include_in_schema=False)
async def pagina_criar_objetivo(request: Request, ciclo_id: int, db: Session = Depends(get_db)):
    c = servico.obter(db, Ciclo, ciclo_id)
    form = await request.form()
    o = Objetivo(ciclo=c, titulo=form["titulo"].strip(), descricao=(form.get("descricao") or "").strip() or None,
                 dono_id=parse_int(form.get("dono_id")), ordem=len(c.objetivos))
    try:
        for i in range(int(form.get("n_krs") or 0)):
            if (form.get(f"kr{i}_descricao") or "").strip():
                k = _ler_kr(form, ResultadoChave(), f"kr{i}_")
                k.valor_atual = k.valor_inicial
                servico.validar_kr(k)
                o.krs.append(k)
    except (HTTPException, ValueError) as e:
        db.rollback()
        return redirecionar(f"/okrs/ciclos/{ciclo_id}/objetivo", erro=getattr(e, "detail", "Valor numérico inválido."))
    db.add(o)
    db.commit()
    return redirecionar(f"/okrs?ciclo={ciclo_id}", msg="Objetivo criado.")


@router.get("/okrs/objetivos/{objetivo_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_objetivo(request: Request, objetivo_id: int, db: Session = Depends(get_db)):
    o = servico.obter(db, Objetivo, objetivo_id)
    return templates.TemplateResponse(request, "okrs/objetivo_form.html", {**_ctx_base(db), "c": o.ciclo, "o": o})


@router.post("/okrs/objetivos/{objetivo_id}", include_in_schema=False)
async def pagina_salvar_objetivo(request: Request, objetivo_id: int, db: Session = Depends(get_db)):
    o = servico.obter(db, Objetivo, objetivo_id)
    form = await request.form()
    o.titulo = form["titulo"].strip()
    o.descricao = (form.get("descricao") or "").strip() or None
    o.dono_id = parse_int(form.get("dono_id"))
    o.ordem = parse_int(form.get("ordem")) or 0
    db.commit()
    return redirecionar(f"/okrs?ciclo={o.ciclo_id}", msg="Objetivo atualizado.")


@router.post("/okrs/objetivos/{objetivo_id}/excluir", include_in_schema=False)
def pagina_excluir_objetivo(objetivo_id: int, db: Session = Depends(get_db)):
    o = servico.obter(db, Objetivo, objetivo_id)
    cid = o.ciclo_id
    db.delete(o)
    db.commit()
    return redirecionar(f"/okrs?ciclo={cid}", msg="Objetivo excluído.")


@router.post("/okrs/objetivos/{objetivo_id}/kr", include_in_schema=False)
async def pagina_criar_kr(request: Request, objetivo_id: int, db: Session = Depends(get_db)):
    o = servico.obter(db, Objetivo, objetivo_id)
    try:
        k = _ler_kr(await request.form(), ResultadoChave(objetivo=o))
        k.valor_atual = k.valor_inicial
        servico.validar_kr(k)
    except (HTTPException, ValueError) as e:
        db.rollback()
        return redirecionar(f"/okrs/objetivos/{objetivo_id}", erro=getattr(e, "detail", "Valor numérico inválido."))
    db.commit()
    return redirecionar(f"/okrs?ciclo={o.ciclo_id}", msg="Resultado-chave adicionado.")


@router.get("/okrs/krs/{kr_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_kr(request: Request, kr_id: int, db: Session = Depends(get_db)):
    k = servico.obter(db, ResultadoChave, kr_id)
    return templates.TemplateResponse(request, "okrs/kr.html", {
        **_ctx_base(db), "k": k, "g": servico.grafico_kr(k)})


@router.post("/okrs/krs/{kr_id}", include_in_schema=False)
async def pagina_salvar_kr(request: Request, kr_id: int, db: Session = Depends(get_db)):
    k = servico.obter(db, ResultadoChave, kr_id)
    try:
        _ler_kr(await request.form(), k)
        servico.validar_kr(k)
    except (HTTPException, ValueError) as e:
        db.rollback()
        return redirecionar(f"/okrs/krs/{kr_id}", erro=getattr(e, "detail", "Valor numérico inválido."))
    db.commit()
    return redirecionar(f"/okrs/krs/{kr_id}", msg="Resultado-chave atualizado.")


@router.post("/okrs/krs/{kr_id}/checkin", include_in_schema=False)
def pagina_checkin(kr_id: int, valor: str = Form(...), confianca: str = Form(""), comentario: str = Form(""),
                   data: str = Form(""), voltar: str = Form(""), db: Session = Depends(get_db)):
    k = servico.obter(db, ResultadoChave, kr_id)
    destino = voltar if voltar.startswith("/") else f"/okrs/krs/{kr_id}"
    try:
        v = 1.0 if valor.lower() in ("sim", "true", "on") else 0.0 if valor.lower() in ("não", "nao", "false") \
            else float(valor.replace(",", "."))
        servico.registrar_checkin(db, k, v, parse_int(confianca), comentario.strip() or None, parse_data(data))
    except (HTTPException, ValueError) as e:
        db.rollback()
        return redirecionar(destino, erro=getattr(e, "detail", "Valor inválido."))
    return redirecionar(destino, msg=f"Check-in registrado: {k.formatar(k.valor_atual)}.")


@router.post("/okrs/checkins/{checkin_id}/excluir", include_in_schema=False)
def pagina_excluir_checkin(checkin_id: int, db: Session = Depends(get_db)):
    ch = servico.obter(db, Checkin, checkin_id)
    kid = ch.kr_id
    api_remover_checkin(checkin_id, db)
    return redirecionar(f"/okrs/krs/{kid}", msg="Check-in removido.")


@router.post("/okrs/krs/{kr_id}/excluir", include_in_schema=False)
def pagina_excluir_kr(kr_id: int, db: Session = Depends(get_db)):
    k = servico.obter(db, ResultadoChave, kr_id)
    cid = k.objetivo.ciclo_id
    db.delete(k)
    db.commit()
    return redirecionar(f"/okrs?ciclo={cid}", msg="Resultado-chave excluído.")
