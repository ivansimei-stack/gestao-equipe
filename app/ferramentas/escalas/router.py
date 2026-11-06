from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.ferramentas.equipe import servico as equipe
from app.ferramentas.escalas import servico
from app.ferramentas.escalas.models import Escala, Participante, Turno
from app.ferramentas.escalas.schemas import (EscalaAtualizar, EscalaCriar, EscalaOut, Gerar, GerarOut, Permuta,
                                             Troca, TurnoCriar, TurnoOut)
from app.util import parse_data, parse_int, sobrepoe
from app.web import redirecionar, templates

router = APIRouter()
TAG = ["escalas"]


# ======================= API =======================

@router.get("/api/escalas", response_model=list[EscalaOut], tags=TAG)
def api_listar(db: Session = Depends(get_db)):
    return servico.escalas(db)


@router.post("/api/escalas", response_model=EscalaOut, status_code=201, tags=TAG)
def api_criar(dados: EscalaCriar, db: Session = Depends(get_db)):
    e = Escala(**dados.model_dump(exclude={"participantes"}))
    servico.validar(e)
    for i, mid in enumerate(dados.participantes):
        e.participantes.append(Participante(membro=equipe.obter_membro(db, mid), ordem=i))
    db.add(e)
    db.commit()
    return e


@router.get("/api/escalas/{escala_id}", response_model=EscalaOut, tags=TAG)
def api_obter(escala_id: int, db: Session = Depends(get_db)):
    return servico.obter(db, escala_id)


@router.patch("/api/escalas/{escala_id}", response_model=EscalaOut, tags=TAG)
def api_atualizar(escala_id: int, dados: EscalaAtualizar, db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    for k, v in dados.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    try:
        servico.validar(e)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return e


@router.delete("/api/escalas/{escala_id}", status_code=204, tags=TAG)
def api_remover(escala_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, escala_id))
    db.commit()


@router.post("/api/escalas/{escala_id}/participantes/{membro_id}", response_model=EscalaOut, tags=TAG)
def api_add_participante(escala_id: int, membro_id: int, db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    servico.adicionar_participante(db, e, equipe.obter_membro(db, membro_id))
    return e


@router.delete("/api/escalas/{escala_id}/participantes/{membro_id}", status_code=204, tags=TAG)
def api_rem_participante(escala_id: int, membro_id: int, db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    p = next((p for p in e.participantes if p.membro_id == membro_id), None)
    if not p:
        raise HTTPException(404, "Participante não encontrado")
    db.delete(p)
    db.commit()


@router.post("/api/escalas/{escala_id}/gerar", response_model=GerarOut, tags=TAG)
def api_gerar(escala_id: int, dados: Gerar, db: Session = Depends(get_db)):
    return servico.gerar(db, servico.obter(db, escala_id), dados.de, dados.ate, dados.sobrescrever_manuais)


@router.get("/api/escalas/{escala_id}/turnos", response_model=list[TurnoOut], tags=TAG)
def api_turnos(escala_id: int, de: date | None = None, ate: date | None = None, db: Session = Depends(get_db)):
    return servico.turnos(db, escala_id, de=de, ate=ate)


@router.get("/api/escalas/{escala_id}/agora", response_model=TurnoOut | None, tags=TAG,
            summary="Quem está de plantão hoje")
def api_agora(escala_id: int, db: Session = Depends(get_db)):
    return servico.de_plantao(db, servico.obter(db, escala_id))


@router.post("/api/escalas/{escala_id}/turnos", response_model=TurnoOut, status_code=201, tags=TAG)
def api_criar_turno(escala_id: int, dados: TurnoCriar, db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    equipe.obter_membro(db, dados.membro_id)
    if dados.fim < dados.inicio:
        raise HTTPException(422, "Fim antes do início.")
    if any(sobrepoe(dados.inicio, dados.fim, t.inicio, t.fim) for t in servico.turnos(db, e.id, de=dados.inicio, ate=dados.fim)):
        raise HTTPException(409, "Já existe turno nesse período.")
    t = Turno(escala=e, origem="manual", **dados.model_dump())
    db.add(t)
    db.commit()
    return t


@router.post("/api/escalas/turnos/{turno_id}/trocar", response_model=TurnoOut, tags=TAG)
def api_trocar(turno_id: int, dados: Troca, db: Session = Depends(get_db)):
    return servico.trocar_responsavel(db, servico.obter_turno(db, turno_id), dados.membro_id, dados.observacao)


@router.post("/api/escalas/turnos/{turno_id}/permutar", response_model=list[TurnoOut], tags=TAG)
def api_permutar(turno_id: int, dados: Permuta, db: Session = Depends(get_db)):
    t1, t2 = servico.obter_turno(db, turno_id), servico.obter_turno(db, dados.outro_turno_id)
    servico.permutar(db, t1, t2, dados.observacao)
    return [t1, t2]


@router.delete("/api/escalas/turnos/{turno_id}", status_code=204, tags=TAG)
def api_remover_turno(turno_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter_turno(db, turno_id))
    db.commit()


# ======================= Páginas =======================

@router.get("/escalas", response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request, db: Session = Depends(get_db)):
    hoje = date.today()
    cards = []
    for e in servico.escalas(db):
        futuros = servico.turnos(db, e.id, de=hoje)
        cards.append({"e": e, "agora": servico.de_plantao(db, e, hoje),
                      "proximos": [t for t in futuros if t.inicio > hoje][:3],
                      "conflitos": len(servico.conflitos(db, e)) if e.ativa else 0,
                      "ate": futuros[-1].fim if futuros else None})
    return templates.TemplateResponse(request, "escalas/index.html", {
        "cards": cards, "membros": equipe.membros(db, apenas_ativos=True)})


@router.post("/escalas", include_in_schema=False)
async def pagina_criar(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    e = Escala(nome=(form.get("nome") or "").strip(), descricao=(form.get("descricao") or "").strip() or None,
               duracao_dias=parse_int(form.get("duracao_dias")) or 7, apenas_dias_uteis=bool(form.get("apenas_dias_uteis")),
               pular_ausentes=bool(form.get("pular_ausentes")))
    try:
        servico.validar(e)
    except HTTPException as ex:
        return redirecionar("/escalas", erro=ex.detail)
    for i, mid in enumerate(form.getlist("participantes")):
        e.participantes.append(Participante(membro=equipe.obter_membro(db, int(mid)), ordem=i))
    db.add(e)
    db.commit()
    return redirecionar(f"/escalas/{e.id}", msg="Escala criada. Agora gere os turnos.")


@router.get("/escalas/{escala_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_escala(request: Request, escala_id: int, passados: str = "", db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    hoje = date.today()
    ini = servico.sugerir_inicio(db, e)
    futuros = servico.turnos(db, e.id, de=hoje)
    ids_part = {p.membro_id for p in e.participantes}
    return templates.TemplateResponse(request, "escalas/escala.html", {
        "e": e, "agora": servico.de_plantao(db, e, hoje), "futuros": futuros,
        "passados": [t for t in reversed(servico.turnos(db, e.id, de=hoje - timedelta(days=180), ate=hoje))
                     if t.fim < hoje][: (None if passados else 8)],
        "conflitos": {t.id: aus for t, aus in servico.conflitos(db, e)},
        "equilibrio": servico.equilibrio(db, e),
        "membros": equipe.membros(db, apenas_ativos=True), "fora": [m for m in equipe.membros(db, apenas_ativos=True)
                                                                   if m.id not in ids_part],
        "sugestao": {"de": ini, "ate": ini + timedelta(days=e.duracao_dias * 12 - 1 if e.duracao_dias > 1 else 89)},
    })


@router.post("/escalas/{escala_id}/config", include_in_schema=False)
async def pagina_config(request: Request, escala_id: int, db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    form = await request.form()
    e.nome = (form.get("nome") or "").strip()
    e.descricao = (form.get("descricao") or "").strip() or None
    e.duracao_dias = parse_int(form.get("duracao_dias")) or e.duracao_dias
    e.apenas_dias_uteis = bool(form.get("apenas_dias_uteis"))
    e.pular_ausentes = bool(form.get("pular_ausentes"))
    e.ativa = bool(form.get("ativa"))
    try:
        servico.validar(e)
    except HTTPException as ex:
        db.rollback()
        return redirecionar(f"/escalas/{escala_id}", erro=ex.detail)
    db.commit()
    return redirecionar(f"/escalas/{escala_id}", msg="Configuração salva.")


@router.post("/escalas/{escala_id}/participantes", include_in_schema=False)
def pagina_add_participante(escala_id: int, membro_id: int = Form(...), db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    try:
        servico.adicionar_participante(db, e, equipe.obter_membro(db, membro_id))
    except HTTPException as ex:
        return redirecionar(f"/escalas/{escala_id}", erro=ex.detail)
    return redirecionar(f"/escalas/{escala_id}", msg="Participante adicionado. Regere os turnos futuros para incluí-lo.")


@router.post("/escalas/{escala_id}/participantes/{participante_id}/{acao}", include_in_schema=False)
def pagina_participante(escala_id: int, participante_id: int, acao: str, db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    if acao in ("subir", "descer"):
        servico.mover_participante(db, e, participante_id, -1 if acao == "subir" else 1)
        return redirecionar(f"/escalas/{escala_id}")
    if acao == "remover":
        p = next((p for p in e.participantes if p.id == participante_id), None)
        if p:
            db.delete(p)
            db.commit()
        return redirecionar(f"/escalas/{escala_id}", msg="Participante removido. Turnos já gerados foram mantidos.")
    raise HTTPException(404)


@router.post("/escalas/{escala_id}/gerar", include_in_schema=False)
def pagina_gerar(escala_id: int, de: str = Form(...), ate: str = Form(...), sobrescrever: str = Form(""),
                 db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    try:
        r = servico.gerar(db, e, parse_data(de), parse_data(ate), bool(sobrescrever))
    except HTTPException as ex:
        return redirecionar(f"/escalas/{escala_id}", erro=ex.detail)
    msg = f"{r['criados']} turno(s) gerado(s); {r['mantidos']} troca(s)/manual(is) mantido(s)."
    if r["pulos"]:
        msg += f" Pulados por ausência: {', '.join(r['pulos'][:6])}."
    erro = f"Sem ninguém disponível em {len(r['vagos'])} período(s)." if r["vagos"] else None
    return redirecionar(f"/escalas/{escala_id}", msg=msg, erro=erro)


@router.post("/escalas/turnos/{turno_id}/trocar", include_in_schema=False)
def pagina_trocar(turno_id: int, membro_id: str = Form(""), outro_turno_id: str = Form(""),
                  observacao: str = Form(""), db: Session = Depends(get_db)):
    t = servico.obter_turno(db, turno_id)
    try:
        if outro_turno_id:
            servico.permutar(db, t, servico.obter_turno(db, int(outro_turno_id)), observacao.strip() or None)
            msg = "Turnos permutados."
        elif membro_id:
            servico.trocar_responsavel(db, t, int(membro_id), observacao.strip() or None)
            msg = f"Turno de {t.inicio:%d/%m} agora com {t.membro.nome}."
        else:
            raise HTTPException(422, "Escolha uma pessoa ou um turno para permutar.")
    except HTTPException as ex:
        return redirecionar(f"/escalas/{t.escala_id}", erro=ex.detail)
    return redirecionar(f"/escalas/{t.escala_id}", msg=msg)


@router.post("/escalas/turnos/{turno_id}/excluir", include_in_schema=False)
def pagina_excluir_turno(turno_id: int, db: Session = Depends(get_db)):
    t = servico.obter_turno(db, turno_id)
    eid = t.escala_id
    db.delete(t)
    db.commit()
    return redirecionar(f"/escalas/{eid}", msg="Turno removido.")


@router.post("/escalas/{escala_id}/turno-manual", include_in_schema=False)
def pagina_turno_manual(escala_id: int, membro_id: int = Form(...), inicio: str = Form(...), fim: str = Form(""),
                        observacao: str = Form(""), db: Session = Depends(get_db)):
    try:
        ini = parse_data(inicio)
        api_criar_turno(escala_id, TurnoCriar(membro_id=membro_id, inicio=ini, fim=parse_data(fim) or ini,
                                              observacao=observacao.strip() or None), db)
    except HTTPException as ex:
        return redirecionar(f"/escalas/{escala_id}", erro=ex.detail)
    return redirecionar(f"/escalas/{escala_id}", msg="Turno manual criado.")


@router.post("/escalas/{escala_id}/excluir", include_in_schema=False)
def pagina_excluir(escala_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, escala_id))
    db.commit()
    return redirecionar("/escalas", msg="Escala excluída.")


@router.get("/escalas/{escala_id}/escala.ics", include_in_schema=False)
def exportar_ics(escala_id: int, db: Session = Depends(get_db)):
    e = servico.obter(db, escala_id)
    lista = servico.turnos(db, e.id, de=date.today() - timedelta(days=60))
    return Response(servico.ics(e, lista), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=escala-{e.id}.ics"})
