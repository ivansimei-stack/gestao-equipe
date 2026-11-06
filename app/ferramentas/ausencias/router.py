import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.ferramentas.ausencias import servico
from app.ferramentas.ausencias.models import STATUS, TIPOS, Ausencia, RegraCobertura
from app.ferramentas.ausencias.schemas import (AusenciaAtualizar, AusenciaComAvisos, AusenciaCriar, AusenciaOut,
                                               Decisao, PeriodoOut, SaldoOut)
from app.ferramentas.equipe import servico as equipe
from app.util import feriado, fim_mes, inicio_mes, parse_data, parse_int, somar_meses
from app.web import redirecionar, templates

router = APIRouter()
TAG = ["ausencias"]


def _com_avisos(db, a: Ausencia) -> dict:
    return {**AusenciaOut.model_validate(a).model_dump(), "avisos": servico.avisos(db, a)}


def _saldo_out(s: servico.Saldo) -> SaldoOut:
    return SaldoOut(
        membro_id=s.membro.id, disponivel=s.disponivel, solicitados=s.solicitados, proximo_limite=s.proximo_limite,
        situacao=s.pior_situacao,
        periodos=[PeriodoOut(inicio=p.inicio, fim=p.fim, concessivo_fim=p.concessivo_fim, adquirido=p.adquirido,
                             direito=p.direito, usados=p.usados, saldo=p.saldo, situacao=p.situacao)
                  for p in s.periodos])


# ======================= API JSON =======================

@router.get("/api/ausencias", response_model=list[AusenciaOut], tags=TAG)
def api_listar(membro_id: int | None = None, status: str | None = None, tipo: str | None = None,
               de: date | None = None, ate: date | None = None, area: str | None = None,
               db: Session = Depends(get_db)):
    return servico.listar(db, membro_id, status, tipo, de, ate, area)


@router.post("/api/ausencias", response_model=AusenciaComAvisos, status_code=201, tags=TAG)
def api_criar(dados: AusenciaCriar, db: Session = Depends(get_db)):
    equipe.obter_membro(db, dados.membro_id)
    a = Ausencia(**dados.model_dump())
    servico.validar(db, a)
    db.add(a)
    db.commit()
    return _com_avisos(db, a)


@router.get("/api/ausencias/hoje", response_model=list[AusenciaOut], tags=TAG)
def api_hoje(db: Session = Depends(get_db)):
    return servico.ausentes_em(db, date.today())


@router.get("/api/ausencias/saldo/{membro_id}", response_model=SaldoOut, tags=TAG)
def api_saldo(membro_id: int, db: Session = Depends(get_db)):
    return _saldo_out(servico.saldo(db, equipe.obter_membro(db, membro_id)))


@router.post("/api/ausencias/simular", response_model=list[str], tags=TAG,
             summary="Retorna avisos (CLT, cobertura) de um pedido sem salvá-lo")
def api_simular(dados: AusenciaCriar, db: Session = Depends(get_db)):
    a = Ausencia(**dados.model_dump())
    a.membro = equipe.obter_membro(db, dados.membro_id)
    servico.validar(db, a)
    avisos = servico.avisos(db, a)
    if a in db:
        db.expunge(a)
    return avisos


@router.get("/api/ausencias/{ausencia_id}", response_model=AusenciaComAvisos, tags=TAG)
def api_obter(ausencia_id: int, db: Session = Depends(get_db)):
    return _com_avisos(db, servico.obter(db, ausencia_id))


@router.patch("/api/ausencias/{ausencia_id}", response_model=AusenciaComAvisos, tags=TAG)
def api_atualizar(ausencia_id: int, dados: AusenciaAtualizar, db: Session = Depends(get_db)):
    a = servico.obter(db, ausencia_id)
    for k, v in dados.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    try:
        servico.validar(db, a)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return _com_avisos(db, a)


@router.delete("/api/ausencias/{ausencia_id}", status_code=204, tags=TAG)
def api_remover(ausencia_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, ausencia_id))
    db.commit()


for _acao, _status in (("aprovar", "aprovada"), ("recusar", "recusada"), ("cancelar", "cancelada"),
                       ("reabrir", "solicitada")):
    def _fazer(ausencia_id: int, dados: Decisao | None = None, db: Session = Depends(get_db), _s=_status):
        return servico.decidir(db, servico.obter(db, ausencia_id), _s, dados.motivo if dados else None)
    router.add_api_route(f"/api/ausencias/{{ausencia_id}}/{_acao}", _fazer, methods=["POST"],
                         response_model=AusenciaOut, tags=TAG, name=f"api_{_acao}")


# ======================= Páginas =======================

def _ctx_form(db):
    return {"membros": equipe.membros(db, apenas_ativos=True), "tipos": TIPOS}


@router.get("/ausencias", response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request, db: Session = Depends(get_db)):
    hoje = date.today()
    pendentes = servico.listar(db, status="solicitada")
    return templates.TemplateResponse(request, "ausencias/index.html", {
        "hoje_ausentes": servico.ausentes_em(db, hoje),
        "pendentes": [(a, servico.avisos(db, a)) for a in pendentes],
        "proximas": [a for a in servico.listar(db, status="aprovada", de=hoje, ate=hoje + timedelta(days=45))
                     if a.inicio > hoje],
        "saldos_alerta": [s for s in (servico.saldo(db, m) for m in equipe.membros(db, apenas_ativos=True))
                          if s.pior_situacao in ("vencida", "vencendo")],
        "situacoes": servico.SITUACOES,
    })


@router.get("/ausencias/historico", response_class=HTMLResponse, include_in_schema=False)
def pagina_historico(request: Request, membro_id: str = "", status: str = "", tipo: str = "", ano: str = "",
                     db: Session = Depends(get_db)):
    a = parse_int(ano)
    lista = servico.listar(db, membro_id=parse_int(membro_id), status=status or None, tipo=tipo or None,
                           de=date(a, 1, 1) if a else None, ate=date(a, 12, 31) if a else None)
    return templates.TemplateResponse(request, "ausencias/historico.html", {
        "ausencias": list(reversed(lista)), "membros": equipe.membros(db), "tipos": TIPOS, "status_opcoes": STATUS,
        "f": {"membro_id": membro_id, "status": status, "tipo": tipo, "ano": ano},
        "anos": list(range(date.today().year + 1, date.today().year - 5, -1)),
    })


@router.get("/ausencias/nova", response_class=HTMLResponse, include_in_schema=False)
def pagina_nova(request: Request, membro_id: str = "", inicio: str = "", db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "ausencias/form.html", {
        **_ctx_form(db), "a": None, "pre": {"membro_id": parse_int(membro_id), "inicio": inicio}})


def _preencher(a: Ausencia, form) -> Ausencia:
    a.tipo = form.get("tipo", "ferias")
    a.inicio = parse_data(form.get("inicio"))
    a.fim = parse_data(form.get("fim")) or a.inicio
    a.dias_vendidos = parse_int(form.get("dias_vendidos")) or 0 if a.tipo == "ferias" else 0
    a.observacao = (form.get("observacao") or "").strip() or None
    if not a.inicio:
        raise HTTPException(422, "Informe a data de início.")
    return a


@router.post("/ausencias/nova", include_in_schema=False)
async def pagina_criar(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    membro = equipe.obter_membro(db, int(form["membro_id"]))
    a = _preencher(Ausencia(membro_id=membro.id), form)
    a.membro = membro
    a.status = "aprovada" if form.get("aprovar") else "solicitada"
    try:
        servico.validar(db, a)
    except HTTPException as e:
        if a in db:
            db.expunge(a)
        return redirecionar(f"/ausencias/nova?membro_id={membro.id}&inicio={a.inicio}", erro=e.detail)
    db.add(a)
    db.commit()
    return redirecionar(f"/ausencias/{a.id}", msg="Ausência registrada.")


@router.get("/ausencias/calendario", response_class=HTMLResponse, include_in_schema=False)
def pagina_calendario(request: Request, mes: str = "", area: str = "", solicitadas: str = "1",
                      db: Session = Depends(get_db)):
    ref = date.fromisoformat(mes + "-01") if mes else inicio_mes(date.today())
    cal = servico.calendario(db, ref, fim_mes(ref), area or None, incluir_solicitadas=solicitadas == "1")
    return templates.TemplateResponse(request, "ausencias/calendario.html", {
        **cal, "ref": ref, "anterior": somar_meses(ref, -1), "proximo": somar_meses(ref, 1),
        "area": area, "areas": equipe.areas(db), "solicitadas": solicitadas, "feriado": feriado, "tipos": TIPOS,
    })


@router.get("/ausencias/saldos", response_class=HTMLResponse, include_in_schema=False)
def pagina_saldos(request: Request, db: Session = Depends(get_db)):
    saldos = [servico.saldo(db, m) for m in equipe.membros(db, apenas_ativos=True)]
    ordem = {"vencida": 0, "vencendo": 1, "em_dia": 2, "em_aquisicao": 3, "quitado": 4}
    saldos.sort(key=lambda s: (ordem[s.pior_situacao], s.proximo_limite or date.max))
    return templates.TemplateResponse(request, "ausencias/saldos.html", {"saldos": saldos,
                                                                         "situacoes": servico.SITUACOES})


@router.get("/ausencias/regras", response_class=HTMLResponse, include_in_schema=False)
def pagina_regras(request: Request, db: Session = Depends(get_db)):
    contagem = {a: len(equipe.membros(db, apenas_ativos=True, area=a)) for a in equipe.areas(db)}
    return templates.TemplateResponse(request, "ausencias/regras.html", {"regras": servico.regras(db),
                                                                         "contagem": contagem})


@router.post("/ausencias/regras", include_in_schema=False)
async def pagina_salvar_regras(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    for area in equipe.areas(db):
        v = parse_int(form.get(f"min_{area}"))
        regra = db.get(RegraCobertura, area)
        if v:
            if regra:
                regra.minimo_presentes = v
            else:
                db.add(RegraCobertura(area=area, minimo_presentes=v))
        elif regra:
            db.delete(regra)
    db.commit()
    return redirecionar("/ausencias/regras", msg="Regras de cobertura salvas.")


@router.get("/ausencias/exportar.csv", include_in_schema=False)
def exportar_csv(ano: int | None = None, db: Session = Depends(get_db)):
    lista = servico.listar(db, de=date(ano, 1, 1) if ano else None, ate=date(ano, 12, 31) if ano else None)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Pessoa", "Área", "Tipo", "Início", "Fim", "Dias corridos", "Dias úteis", "Dias vendidos",
                "Status", "Observação"])
    for a in lista:
        w.writerow([a.membro.nome, a.membro.area or "", a.tipo_nome, f"{a.inicio:%d/%m/%Y}", f"{a.fim:%d/%m/%Y}",
                    a.dias_corridos, a.dias_uteis, a.dias_vendidos, a.status_nome, a.observacao or ""])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=ausencias.csv"})


@router.get("/ausencias/calendario.ics", include_in_schema=False)
def exportar_ics(db: Session = Depends(get_db)):
    lista = servico.listar(db, status="aprovada", de=date.today() - timedelta(days=180))
    return Response(servico.ics(lista, "Ausências da equipe"), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=ausencias.ics"})


@router.get("/ausencias/{ausencia_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_detalhe(request: Request, ausencia_id: int, db: Session = Depends(get_db)):
    a = servico.obter(db, ausencia_id)
    return templates.TemplateResponse(request, "ausencias/detalhe.html", {
        **_ctx_form(db), "a": a, "avisos": servico.avisos(db, a) if a.status in ("solicitada", "aprovada") else [],
        "saldo": servico.saldo(db, a.membro) if a.tipo == "ferias" else None, "situacoes": servico.SITUACOES})


@router.post("/ausencias/{ausencia_id}/editar", include_in_schema=False)
async def pagina_editar(request: Request, ausencia_id: int, db: Session = Depends(get_db)):
    a = servico.obter(db, ausencia_id)
    try:
        _preencher(a, await request.form())
        servico.validar(db, a)
    except HTTPException as e:
        db.rollback()
        return redirecionar(f"/ausencias/{ausencia_id}", erro=e.detail)
    db.commit()
    return redirecionar(f"/ausencias/{ausencia_id}", msg="Alterações salvas.")


@router.post("/ausencias/{ausencia_id}/status", include_in_schema=False)
def pagina_status(ausencia_id: int, status: str = Form(...), motivo: str = Form(""), voltar: str = Form(""),
                  db: Session = Depends(get_db)):
    a = servico.obter(db, ausencia_id)
    destino = voltar if voltar.startswith("/") else f"/ausencias/{ausencia_id}"
    try:
        servico.decidir(db, a, status, motivo.strip() or None)
    except HTTPException as e:
        return redirecionar(destino, erro=e.detail)
    return redirecionar(destino, msg=f"{a.membro.primeiro_nome}: {a.tipo_nome.lower()} {a.status_nome.lower()}.")


@router.post("/ausencias/{ausencia_id}/excluir", include_in_schema=False)
def pagina_excluir(ausencia_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, ausencia_id))
    db.commit()
    return redirecionar("/ausencias/historico", msg="Registro excluído.")
