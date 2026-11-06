from datetime import date, timedelta

import pytest

from app.ferramentas.ausencias import servico
from app.ferramentas.ausencias.models import Ausencia
from app.ferramentas.equipe.models import Membro


def _membro(client, nome="Ana", area="TI", admissao="2023-01-10"):
    return client.post("/api/equipe", json={"nome": nome, "area": area, "data_admissao": admissao}).json()["id"]


def _ausencia(client, mid, inicio, fim, tipo="ferias", status="solicitada", **kw):
    return client.post("/api/ausencias", json={"membro_id": mid, "tipo": tipo, "inicio": str(inicio),
                                               "fim": str(fim), "status": status, **kw})


def test_fluxo_aprovacao(client):
    mid = _membro(client)
    r = _ausencia(client, mid, "2026-03-02", "2026-03-16")
    assert r.status_code == 201
    aid = r.json()["id"]
    assert r.json()["dias_corridos"] == 15
    assert client.post(f"/api/ausencias/{aid}/aprovar").json()["status"] == "aprovada"
    # aprovada -> aprovada não é transição válida
    assert client.post(f"/api/ausencias/{aid}/aprovar").status_code == 409
    assert client.post(f"/api/ausencias/{aid}/cancelar", json={"motivo": "mudou planos"}).json()["status"] == "cancelada"
    assert client.post(f"/api/ausencias/{aid}/reabrir").json()["status"] == "solicitada"


def test_validacoes(client):
    mid = _membro(client)
    assert _ausencia(client, mid, "2026-03-10", "2026-03-01").status_code == 422
    assert _ausencia(client, mid, "2026-03-02", "2026-03-06", tipo="folga", dias_vendidos=2).status_code == 422
    assert _ausencia(client, mid, "2026-03-02", "2026-03-06", tipo="xyz").status_code == 422
    assert _ausencia(client, mid, "2026-03-02", "2026-03-16").status_code == 201
    # sobreposição com a mesma pessoa
    assert _ausencia(client, mid, "2026-03-10", "2026-03-20", tipo="folga").status_code == 409


def test_avisos_clt(client):
    mid = _membro(client, admissao="2025-06-01")

    def simular(inicio, fim):
        return " ".join(client.post("/api/ausencias/simular",
                                    json={"membro_id": mid, "inicio": inicio, "fim": fim}).json())

    # sexta-feira (2 dias antes do domingo) e só 3 dias
    texto = simular("2027-03-05", "2027-03-07")
    assert "134 §3º" in texto and "pelo menos 5 dias" in texto
    # segunda-feira, 20 dias: nenhum aviso
    assert simular("2027-03-01", "2027-03-20") == ""
    # 10 + 10 + 5 dias: nenhuma parcela >= 14
    _ausencia(client, mid, "2027-02-01", "2027-02-10", status="aprovada")
    _ausencia(client, mid, "2027-03-01", "2027-03-10", status="aprovada")
    assert "14 dias" in simular("2027-04-05", "2027-04-09")
    # quarta parcela / saldo excedido
    _ausencia(client, mid, "2027-04-05", "2027-04-09", status="aprovada")
    texto = simular("2027-05-03", "2027-05-12")
    assert "no máximo 3 parcelas" in texto and "Saldo insuficiente" in texto


def test_ferias_antecipadas_e_sem_admissao(client):
    mid = _membro(client, admissao=str(date.today() - timedelta(days=60)))
    inicio = date.today() + timedelta(days=30)
    inicio += timedelta(days=-inicio.weekday())  # segunda
    avisos = client.post("/api/ausencias/simular", json={"membro_id": mid, "inicio": str(inicio),
                                                         "fim": str(inicio + timedelta(days=14))}).json()
    assert any("antecipadas" in a for a in avisos)
    sem = client.post("/api/equipe", json={"nome": "Sem Data"}).json()["id"]
    avisos = client.post("/api/ausencias/simular", json={"membro_id": sem, "inicio": str(inicio),
                                                         "fim": str(inicio + timedelta(days=14))}).json()
    assert any("data de admissão" in a for a in avisos)


def test_saldo_ferias(db_sessao):
    m = Membro(nome="Bia", data_admissao=date(2023, 1, 10))
    db_sessao.add(m)
    db_sessao.commit()
    db_sessao.add_all([
        Ausencia(membro_id=m.id, tipo="ferias", inicio=date(2024, 2, 5), fim=date(2024, 2, 24), status="aprovada",
                 dias_vendidos=10),  # 20 + 10 = 30 -> quita 1º período
        Ausencia(membro_id=m.id, tipo="ferias", inicio=date(2025, 3, 3), fim=date(2025, 3, 17), status="aprovada"),
    ])
    db_sessao.commit()
    s = servico.saldo(db_sessao, m, ref=date(2025, 12, 1))
    p1, p2, p3 = s.periodos
    assert (p1.usados, p1.situacao) == (30, "quitado")
    assert (p2.usados, p2.saldo, p2.concessivo_fim) == (15, 15, date(2026, 1, 9))
    assert p2.situacao == "vencendo"
    assert not p3.adquirido and p3.situacao == "em_aquisicao" and p3.direito == 25.0  # 10 meses
    assert s.disponivel == 15
    assert servico.saldo(db_sessao, m, ref=date(2026, 2, 1)).periodos[1].situacao == "vencida"


def test_cobertura(client):
    a = _membro(client, "Ana")
    b = _membro(client, "Beto")
    _membro(client, "Caio")
    client.post("/ausencias/regras", data={"min_TI": "2"})
    _ausencia(client, a, "2026-03-02", "2026-03-20", status="aprovada")
    avisos = _ausencia(client, b, "2026-03-09", "2026-03-27").json()["avisos"]
    assert any("Também ausentes" in x and "Ana" in x for x in avisos)
    assert any("Cobertura abaixo do mínimo" in x and "10 dia(s)" in x for x in avisos)


def test_paginas(client):
    mid = _membro(client)
    hoje = date.today()
    _ausencia(client, mid, hoje, hoje + timedelta(days=14), status="aprovada")
    for url in ("/ausencias", "/ausencias/calendario", f"/ausencias/calendario?mes={hoje:%Y-%m}&area=TI",
                "/ausencias/saldos", "/ausencias/historico", "/ausencias/regras", "/ausencias/nova",
                "/ausencias/1", f"/equipe/{mid}", "/"):
        r = client.get(url)
        assert r.status_code == 200, url
    assert "Ausentes hoje" in client.get("/").text
    # criação pelo formulário + decisão
    r = client.post("/ausencias/nova", data={"membro_id": mid, "tipo": "folga", "inicio": "2030-01-07",
                                             "fim": "2030-01-07"})
    assert "Ausência registrada" in r.text
    aid = client.get(f"/api/ausencias?membro_id={mid}&tipo=folga").json()[0]["id"]
    client.post(f"/ausencias/{aid}/status", data={"status": "recusada", "motivo": "entrega"})
    assert client.get(f"/api/ausencias/{aid}").json()["status"] == "recusada"
    # erro de sobreposição volta com mensagem
    r = client.post("/ausencias/nova", data={"membro_id": mid, "tipo": "folga", "inicio": str(hoje), "fim": str(hoje)})
    assert "Já existe" in r.text


def test_exportacoes(client):
    mid = _membro(client)
    _ausencia(client, mid, date.today(), date.today() + timedelta(days=5), status="aprovada", observacao="praia; sol")
    csv = client.get("/ausencias/exportar.csv").text
    assert "Ana" in csv and "Férias" in csv
    ics = client.get("/ausencias/calendario.ics").text
    assert "BEGIN:VEVENT" in ics and "Ana — Férias" in ics and r"praia\; sol" in ics
