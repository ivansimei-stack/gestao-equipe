from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.ferramentas.avaliacoes import servico
from app.ferramentas.avaliacoes.models import (ESCALA, POTENCIAL, STATUS_CICLO, TIPOS_AVALIACAO, TIPOS_FEEDBACK,
                                               TIPOS_PDI, Avaliacao, CicloAvaliacao, Criterio, Feedback, ItemPDI)
from app.ferramentas.equipe import servico as equipe
from app.util import parse_data, parse_int
from app.web import redirecionar, templates

router = APIRouter()
TAG = ["avaliacoes"]
B = "/avaliacoes"


# ======================= schemas =======================

class CriterioIn(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    descricao: str | None = None
    peso: float = Field(default=1.0, gt=0, le=10)


class CicloIn(BaseModel):
    nome: str
    inicio: date
    fim: date
    prazo: date | None = None
    criterios: list[CriterioIn] | None = None


class CriterioOut(CriterioIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CicloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    inicio: date
    fim: date
    prazo: date | None
    status: str
    criterios: list[CriterioOut]


class NotaIn(BaseModel):
    criterio_id: int
    nota: int | None = Field(default=None, ge=1, le=5)
    comentario: str | None = None


class AvaliacaoIn(BaseModel):
    notas: list[NotaIn] = []
    pontos_fortes: str | None = None
    a_desenvolver: str | None = None
    comentario: str | None = None
    potencial: int | None = Field(default=None, ge=1, le=3)
    enviar: bool = False


class AvaliacaoOut(BaseModel):
    id: int
    ciclo_id: int
    membro_id: int
    tipo: str
    status: str
    nota_final: float | None
    potencial: int | None
    pontos_fortes: str | None
    a_desenvolver: str | None
    comentario: str | None
    notas: list[NotaIn]


class ResultadoOut(BaseModel):
    membro_id: int
    nome: str
    status_auto: str | None
    status_gestor: str | None
    nota_auto: float | None
    nota_gestor: float | None
    gap: float | None
    potencial: int | None
    nine_box: str | None


class FeedbackIn(BaseModel):
    membro_id: int
    tipo: str = Field(default="reconhecimento", pattern="^(reconhecimento|construtivo)$")
    texto: str = Field(min_length=1)
    data: date | None = None
    compartilhado: bool = True


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    membro_id: int
    data: date
    tipo: str
    texto: str
    compartilhado: bool


class PDIIn(BaseModel):
    membro_id: int
    descricao: str = Field(min_length=1, max_length=300)
    tipo: str = Field(default="pratica", pattern="^(pratica|social|formal)$")
    prazo: date | None = None
    ciclo_id: int | None = None


class PDIOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    membro_id: int
    ciclo_id: int | None
    descricao: str
    tipo: str
    prazo: date | None
    concluido: bool
    atrasado: bool


def _aval_out(a: Avaliacao) -> AvaliacaoOut:
    return AvaliacaoOut(id=a.id, ciclo_id=a.ciclo_id, membro_id=a.membro_id, tipo=a.tipo, status=a.status,
                        nota_final=servico.nota_final(a), potencial=a.potencial, pontos_fortes=a.pontos_fortes,
                        a_desenvolver=a.a_desenvolver, comentario=a.comentario,
                        notas=[NotaIn(criterio_id=n.criterio_id, nota=n.nota, comentario=n.comentario) for n in a.notas])


# ======================= API =======================

@router.get("/api/avaliacoes/ciclos", response_model=list[CicloOut], tags=TAG)
def api_ciclos(db: Session = Depends(get_db)):
    return servico.ciclos(db)


@router.post("/api/avaliacoes/ciclos", response_model=CicloOut, status_code=201, tags=TAG)
def api_criar_ciclo(dados: CicloIn, db: Session = Depends(get_db)):
    crit = [(c.nome, c.descricao, c.peso) for c in dados.criterios] if dados.criterios is not None else None
    return servico.criar_ciclo(db, dados.nome, dados.inicio, dados.fim, dados.prazo, crit)


@router.post("/api/avaliacoes/ciclos/{ciclo_id}/status/{status}", response_model=CicloOut, tags=TAG)
def api_status_ciclo(ciclo_id: int, status: str, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    servico.mudar_status(db, c, status)
    return c


@router.get("/api/avaliacoes/ciclos/{ciclo_id}/resultados", response_model=list[ResultadoOut], tags=TAG)
def api_resultados(ciclo_id: int, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    return [ResultadoOut(membro_id=r.membro.id, nome=r.membro.nome, status_auto=r.auto.status if r.auto else None,
                         status_gestor=r.gestor.status if r.gestor else None, nota_auto=r.nota_auto,
                         nota_gestor=r.nota_gestor, gap=r.gap,
                         potencial=r.gestor.potencial if r.gestor else None,
                         nine_box=r.caixa_info[0] if r.caixa_info else None) for r in servico.resultados(db, c)]


@router.get("/api/avaliacoes/ciclos/{ciclo_id}/membros/{membro_id}/{tipo}", response_model=AvaliacaoOut, tags=TAG)
def api_avaliacao(ciclo_id: int, membro_id: int, tipo: str, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    equipe.obter_membro(db, membro_id)
    a = servico.obter_ou_criar(db, c, membro_id, tipo)
    db.commit()
    return _aval_out(a)


@router.put("/api/avaliacoes/ciclos/{ciclo_id}/membros/{membro_id}/{tipo}", response_model=AvaliacaoOut, tags=TAG)
def api_salvar_avaliacao(ciclo_id: int, membro_id: int, tipo: str, dados: AvaliacaoIn, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    equipe.obter_membro(db, membro_id)
    a = servico.obter_ou_criar(db, c, membro_id, tipo)
    servico.salvar(db, a, {n.criterio_id: (n.nota, n.comentario) for n in dados.notas},
                   dados.model_dump(include={"pontos_fortes", "a_desenvolver", "comentario"}, exclude_unset=True),
                   dados.potencial, dados.enviar)
    return _aval_out(a)


@router.get("/api/avaliacoes/feedbacks", response_model=list[FeedbackOut], tags=TAG)
def api_feedbacks(membro_id: int | None = None, de: date | None = None, ate: date | None = None,
                  db: Session = Depends(get_db)):
    return servico.feedbacks(db, membro_id, de, ate)


@router.post("/api/avaliacoes/feedbacks", response_model=FeedbackOut, status_code=201, tags=TAG)
def api_criar_feedback(dados: FeedbackIn, db: Session = Depends(get_db)):
    equipe.obter_membro(db, dados.membro_id)
    f = Feedback(**{**dados.model_dump(), "data": dados.data or date.today()})
    db.add(f)
    db.commit()
    return f


@router.delete("/api/avaliacoes/feedbacks/{feedback_id}", status_code=204, tags=TAG)
def api_remover_feedback(feedback_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, Feedback, feedback_id))
    db.commit()


@router.get("/api/avaliacoes/pdi", response_model=list[PDIOut], tags=TAG)
def api_pdi(membro_id: int | None = None, abertos: bool | None = None, db: Session = Depends(get_db)):
    return servico.pdi(db, membro_id, abertos)


@router.post("/api/avaliacoes/pdi", response_model=PDIOut, status_code=201, tags=TAG)
def api_criar_pdi(dados: PDIIn, db: Session = Depends(get_db)):
    equipe.obter_membro(db, dados.membro_id)
    i = ItemPDI(**dados.model_dump())
    db.add(i)
    db.commit()
    return i


@router.post("/api/avaliacoes/pdi/{item_id}/concluir", response_model=PDIOut, tags=TAG)
def api_concluir_pdi(item_id: int, db: Session = Depends(get_db)):
    i = servico.obter(db, ItemPDI, item_id)
    i.concluido = not i.concluido
    i.concluido_em = date.today() if i.concluido else None
    db.commit()
    return i


# ======================= Páginas =======================

def _ctx(db):
    return {"escala": ESCALA, "potenciais": POTENCIAL, "tipos_av": TIPOS_AVALIACAO, "tipos_fb": TIPOS_FEEDBACK,
            "tipos_pdi": TIPOS_PDI, "status_ciclo": STATUS_CICLO, "nine_box": servico.NINE_BOX, "sv": servico,
            "membros": equipe.membros(db, apenas_ativos=True)}


@router.get(B, response_class=HTMLResponse, include_in_schema=False)
def pagina(request: Request, ciclo: str = "", db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, int(ciclo)) if ciclo else servico.ciclo_atual(db)
    res = servico.resultados(db, c) if c else []
    return templates.TemplateResponse(request, "avaliacoes/index.html", {
        **_ctx(db), "c": c, "ciclos": servico.ciclos(db), "res": res,
        "prog": servico.progresso(res) if c else None, "sem_feedback": servico.sem_feedback(db)})


@router.get(B + "/ciclos/novo", response_class=HTMLResponse, include_in_schema=False)
def pagina_novo_ciclo(request: Request, db: Session = Depends(get_db)):
    hoje = date.today()
    return templates.TemplateResponse(request, "avaliacoes/ciclo_form.html", {
        **_ctx(db), "ciclos": servico.ciclos(db),
        "sug": {"nome": f"Avaliação {hoje.year}", "inicio": date(hoje.year, 1, 1), "fim": date(hoje.year, 12, 31),
                "prazo": hoje + timedelta(days=21)}})


@router.post(B + "/ciclos", include_in_schema=False)
def pagina_criar_ciclo(nome: str = Form(...), inicio: str = Form(...), fim: str = Form(...), prazo: str = Form(""),
                       copiar_de: str = Form(""), db: Session = Depends(get_db)):
    try:
        origem = servico.obter(db, CicloAvaliacao, int(copiar_de)) if copiar_de else None
        c = servico.criar_ciclo(db, nome, parse_data(inicio), parse_data(fim), parse_data(prazo), copiar_de=origem)
    except HTTPException as e:
        return redirecionar(B + "/ciclos/novo", erro=e.detail)
    return redirecionar(f"{B}/ciclos/{c.id}/criterios", msg="Ciclo criado. Revise os critérios e pesos.")


@router.get(B + "/ciclos/{ciclo_id}/criterios", response_class=HTMLResponse, include_in_schema=False)
def pagina_criterios(request: Request, ciclo_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "avaliacoes/criterios.html", {
        **_ctx(db), "c": servico.obter(db, CicloAvaliacao, ciclo_id)})


@router.post(B + "/ciclos/{ciclo_id}/criterios", include_in_schema=False)
async def pagina_salvar_criterios(request: Request, ciclo_id: int, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    form = await request.form()
    try:
        servico.exigir_editavel(c)
        for k in list(c.criterios):
            if form.get(f"remover_{k.id}"):
                db.delete(k)
                continue
            k.nome = (form.get(f"nome_{k.id}") or k.nome).strip()
            k.descricao = (form.get(f"descricao_{k.id}") or "").strip() or None
            k.peso = max(0.1, float((form.get(f"peso_{k.id}") or "1").replace(",", ".")))
        if (form.get("novo_nome") or "").strip():
            c.criterios.append(Criterio(nome=form["novo_nome"].strip(), descricao=(form.get("novo_descricao") or "").strip() or None,
                                        peso=float((form.get("novo_peso") or "1").replace(",", ".")),
                                        ordem=len(c.criterios)))
        c.nome = (form.get("ciclo_nome") or c.nome).strip()
        c.prazo = parse_data(form.get("ciclo_prazo")) or c.prazo
    except (HTTPException, ValueError) as e:
        db.rollback()
        return redirecionar(f"{B}/ciclos/{ciclo_id}/criterios", erro=getattr(e, "detail", "Peso inválido."))
    db.commit()
    return redirecionar(f"{B}/ciclos/{ciclo_id}/criterios", msg="Critérios salvos.")


@router.post(B + "/ciclos/{ciclo_id}/status", include_in_schema=False)
def pagina_status_ciclo(ciclo_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    servico.mudar_status(db, c, status)
    return redirecionar(f"{B}?ciclo={ciclo_id}", msg=f"Ciclo agora: {c.status_nome.lower()}.")


@router.post(B + "/ciclos/{ciclo_id}/excluir", include_in_schema=False)
def pagina_excluir_ciclo(ciclo_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, CicloAvaliacao, ciclo_id))
    db.commit()
    return redirecionar(B, msg="Ciclo excluído.")


@router.get(B + "/ciclos/{ciclo_id}/calibracao", response_class=HTMLResponse, include_in_schema=False)
def pagina_calibracao(request: Request, ciclo_id: int, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    res = servico.resultados(db, c)
    grade = {k: [] for k in servico.NINE_BOX}
    for r in res:
        if r.caixa:
            grade[r.caixa].append(r)
    notas = [r.nota_gestor for r in res if r.nota_gestor is not None]
    dist = {f: sum(1 for n in notas if servico.faixa_desempenho(n) == f) for f in (1, 2, 3)}
    return templates.TemplateResponse(request, "avaliacoes/calibracao.html", {
        **_ctx(db), "c": c, "res": sorted(res, key=lambda r: -(r.nota_gestor or 0)), "grade": grade,
        "media": round(sum(notas) / len(notas), 2) if notas else None, "dist": dist, "n": len(notas)})


@router.get(B + "/ciclos/{ciclo_id}/exportar.csv", include_in_schema=False)
def exportar(ciclo_id: int, db: Session = Depends(get_db)):
    import csv
    import io
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Pessoa", "Área", "Nota auto", "Nota gestor", "Diferença", "Potencial", "Nine-box"] +
               [f"{k.nome} (gestor)" for k in c.criterios])
    for r in servico.resultados(db, c):
        notas_g = [(r.gestor.nota_de(k.id).nota if r.gestor and r.gestor.nota_de(k.id) else "") for k in c.criterios]
        fmt = lambda v: "" if v is None else str(v).replace(".", ",")  # noqa: E731
        w.writerow([r.membro.nome, r.membro.area or "", fmt(r.nota_auto), fmt(r.nota_gestor), fmt(r.gap),
                    POTENCIAL.get(r.gestor.potencial, "") if r.gestor else "",
                    r.caixa_info[0] if r.caixa_info else ""] + notas_g)
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=avaliacao-{c.id}.csv"})


@router.get(B + "/ciclos/{ciclo_id}/membros/{membro_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_resultado(request: Request, ciclo_id: int, membro_id: int, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    m = equipe.obter_membro(db, membro_id)
    r = servico.Resultado(m, servico.buscar(db, c.id, m.id, "auto"), servico.buscar(db, c.id, m.id, "gestor"))
    return templates.TemplateResponse(request, "avaliacoes/resultado.html", {
        **_ctx(db), "c": c, "m": m, "r": r, "feedbacks": servico.feedbacks(db, m.id, c.inicio, c.fim),
        "pdi": servico.pdi(db, m.id)})


@router.get(B + "/ciclos/{ciclo_id}/membros/{membro_id}/{tipo}", response_class=HTMLResponse, include_in_schema=False)
def pagina_form(request: Request, ciclo_id: int, membro_id: int, tipo: str, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    m = equipe.obter_membro(db, membro_id)
    a = servico.obter_ou_criar(db, c, m.id, tipo)
    db.commit()
    outra = servico.buscar(db, c.id, m.id, "auto") if tipo == "gestor" else None
    return templates.TemplateResponse(request, "avaliacoes/form.html", {
        **_ctx(db), "c": c, "m": m, "a": a, "auto": outra if outra and outra.status == "enviada" else None,
        "feedbacks": servico.feedbacks(db, m.id, c.inicio, c.fim) if tipo == "gestor" else []})


@router.post(B + "/ciclos/{ciclo_id}/membros/{membro_id}/{tipo}", include_in_schema=False)
async def pagina_salvar(request: Request, ciclo_id: int, membro_id: int, tipo: str, db: Session = Depends(get_db)):
    c = servico.obter(db, CicloAvaliacao, ciclo_id)
    m = equipe.obter_membro(db, membro_id)
    form = await request.form()
    a = servico.obter_ou_criar(db, c, m.id, tipo)
    url = f"{B}/ciclos/{ciclo_id}/membros/{membro_id}/{tipo}"
    if form.get("acao") == "reabrir":
        try:
            servico.reabrir(db, a)
        except HTTPException as e:
            return redirecionar(url, erro=e.detail)
        return redirecionar(url, msg="Avaliação reaberta para edição.")
    notas = {k.id: (parse_int(form.get(f"nota_{k.id}")), (form.get(f"coment_{k.id}") or "").strip() or None)
             for k in c.criterios}
    textos = {f: (form.get(f) or "").strip() or None for f in ("pontos_fortes", "a_desenvolver", "comentario")}
    try:
        servico.salvar(db, a, notas, textos, parse_int(form.get("potencial")), form.get("acao") == "enviar")
    except HTTPException as e:
        # mantém o rascunho mesmo se o envio falhar por campos faltando
        if form.get("acao") == "enviar":
            servico.salvar(db, servico.obter_ou_criar(db, c, m.id, tipo), notas, textos,
                           parse_int(form.get("potencial")), False)
        return redirecionar(url, erro=e.detail)
    if a.status == "enviada":
        return redirecionar(f"{B}/ciclos/{ciclo_id}/membros/{membro_id}", msg=f"{TIPOS_AVALIACAO[tipo]} enviada.")
    return redirecionar(url, msg="Rascunho salvo.")


@router.get(B + "/feedbacks", response_class=HTMLResponse, include_in_schema=False)
def pagina_feedbacks(request: Request, membro_id: str = "", tipo: str = "", db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "avaliacoes/feedbacks.html", {
        **_ctx(db), "lista": servico.feedbacks(db, parse_int(membro_id), tipo=tipo or None)[:200],
        "f": {"membro_id": membro_id, "tipo": tipo}, "sem_feedback": servico.sem_feedback(db)})


@router.post(B + "/feedbacks", include_in_schema=False)
def pagina_criar_feedback(membro_id: int = Form(...), tipo: str = Form("reconhecimento"), texto: str = Form(...),
                          data: str = Form(""), compartilhado: str = Form(""), voltar: str = Form(""),
                          db: Session = Depends(get_db)):
    equipe.obter_membro(db, membro_id)
    if tipo not in TIPOS_FEEDBACK or not texto.strip():
        return redirecionar(B + "/feedbacks", erro="Informe o tipo e o texto do feedback.")
    db.add(Feedback(membro_id=membro_id, tipo=tipo, texto=texto.strip(), data=parse_data(data) or date.today(),
                    compartilhado=bool(compartilhado)))
    db.commit()
    return redirecionar(voltar if voltar.startswith("/") else B + "/feedbacks", msg="Feedback registrado.")


@router.post(B + "/feedbacks/{feedback_id}/excluir", include_in_schema=False)
def pagina_excluir_feedback(feedback_id: int, db: Session = Depends(get_db)):
    db.delete(servico.obter(db, Feedback, feedback_id))
    db.commit()
    return redirecionar(B + "/feedbacks", msg="Feedback excluído.")


@router.post(B + "/feedbacks/{feedback_id}/compartilhado", include_in_schema=False)
def pagina_feedback_compartilhado(feedback_id: int, db: Session = Depends(get_db)):
    f = servico.obter(db, Feedback, feedback_id)
    f.compartilhado = not f.compartilhado
    db.commit()
    return redirecionar(B + "/feedbacks")


@router.post(B + "/pdi", include_in_schema=False)
def pagina_criar_pdi(membro_id: int = Form(...), descricao: str = Form(...), tipo: str = Form("pratica"),
                     prazo: str = Form(""), ciclo_id: str = Form(""), voltar: str = Form(""),
                     db: Session = Depends(get_db)):
    equipe.obter_membro(db, membro_id)
    if descricao.strip():
        db.add(ItemPDI(membro_id=membro_id, descricao=descricao.strip()[:300],
                       tipo=tipo if tipo in TIPOS_PDI else "pratica", prazo=parse_data(prazo),
                       ciclo_id=parse_int(ciclo_id)))
        db.commit()
    return redirecionar(voltar if voltar.startswith("/") else f"/equipe/{membro_id}", msg="Item de PDI adicionado.")


@router.post(B + "/pdi/{item_id}/alternar", include_in_schema=False)
def pagina_alternar_pdi(item_id: int, voltar: str = Form(""), db: Session = Depends(get_db)):
    i = api_concluir_pdi(item_id, db)
    return redirecionar(voltar if voltar.startswith("/") else f"/equipe/{i.membro_id}")


@router.post(B + "/pdi/{item_id}/excluir", include_in_schema=False)
def pagina_excluir_pdi(item_id: int, voltar: str = Form(""), db: Session = Depends(get_db)):
    i = servico.obter(db, ItemPDI, item_id)
    mid = i.membro_id
    db.delete(i)
    db.commit()
    return redirecionar(voltar if voltar.startswith("/") else f"/equipe/{mid}", msg="Item removido.")
