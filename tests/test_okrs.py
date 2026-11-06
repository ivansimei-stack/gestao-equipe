from datetime import date, timedelta

from app.ferramentas.okrs import servico
from app.ferramentas.okrs.models import Checkin, Ciclo, Objetivo, ResultadoChave


def _ciclo(client, dias_passados=45, duracao=90, nome="T1"):
    ini = date.today() - timedelta(days=dias_passados)
    return client.post("/api/okrs/ciclos", json={"nome": nome, "inicio": str(ini),
                                                 "fim": str(ini + timedelta(days=duracao - 1))}).json()


def test_progresso_e_status(client):
    c = _ciclo(client)  # ~50% do tempo
    o = client.post(f"/api/okrs/ciclos/{c['id']}/objetivos", json={"titulo": "Atender melhor", "krs": [
        {"descricao": "NPS", "valor_inicial": 20, "valor_alvo": 60},
        {"descricao": "Tempo de resposta (h)", "valor_inicial": 48, "valor_alvo": 24},
        {"descricao": "Lançar portal", "tipo": "binario"},
    ]}).json()
    nps, tempo, portal = o["krs"]
    assert nps["progresso"] == 0 and nps["status"] == "em_risco"
    # NPS 40 -> 50% (no ritmo); tempo 30h -> 75% (redução)
    client.post(f"/api/okrs/krs/{nps['id']}/checkins", json={"valor": 40, "confianca": 7})
    client.post(f"/api/okrs/krs/{tempo['id']}/checkins", json={"valor": 30, "confianca": 8})
    k1 = client.get(f"/api/okrs/krs/{nps['id']}").json()
    k2 = client.get(f"/api/okrs/krs/{tempo['id']}").json()
    assert k1["progresso"] == 0.5 and k1["status"] == "no_prazo"
    assert k2["progresso"] == 0.75 and k2["status"] == "no_prazo"
    assert k1["projecao"] is not None and 55 < k1["projecao"] < 65
    # confiança baixa derruba o status
    client.post(f"/api/okrs/krs/{nps['id']}/checkins", json={"valor": 40, "confianca": 3})
    assert client.get(f"/api/okrs/krs/{nps['id']}").json()["status"] == "em_risco"
    # binário
    client.post(f"/api/okrs/krs/{portal['id']}/checkins", json={"valor": 1})
    p = client.get(f"/api/okrs/krs/{portal['id']}").json()
    assert p["progresso"] == 1 and p["status"] == "concluido"
    ciclo = client.get(f"/api/okrs/ciclos/{c['id']}").json()
    assert round(ciclo["objetivos"][0]["progresso"], 2) == round((0.5 + 0.75 + 1) / 3, 2)


def test_validacoes(client):
    assert client.post("/api/okrs/ciclos", json={"nome": "X", "inicio": "2026-03-01", "fim": "2026-01-01"}).status_code == 422
    c = _ciclo(client)
    r = client.post(f"/api/okrs/ciclos/{c['id']}/objetivos", json={"titulo": "O", "krs": [
        {"descricao": "igual", "valor_inicial": 5, "valor_alvo": 5}]})
    assert r.status_code == 422
    o = client.post(f"/api/okrs/ciclos/{c['id']}/objetivos", json={"titulo": "O"}).json()
    k = client.post(f"/api/okrs/objetivos/{o['id']}/krs", json={"descricao": "k", "valor_alvo": 10}).json()
    assert client.post(f"/api/okrs/krs/{k['id']}/checkins", json={"valor": 1, "confianca": 11}).status_code == 422


def test_checkin_fora_de_ordem_e_remocao(client):
    c = _ciclo(client)
    o = client.post(f"/api/okrs/ciclos/{c['id']}/objetivos", json={"titulo": "O"}).json()
    k = client.post(f"/api/okrs/objetivos/{o['id']}/krs", json={"descricao": "k", "valor_alvo": 100}).json()
    hoje = date.today()
    client.post(f"/api/okrs/krs/{k['id']}/checkins", json={"valor": 50, "data": str(hoje)})
    ch = client.post(f"/api/okrs/krs/{k['id']}/checkins", json={"valor": 20, "data": str(hoje - timedelta(days=10))}).json()
    assert client.get(f"/api/okrs/krs/{k['id']}").json()["valor_atual"] == 50  # vale o mais recente por data
    ult = client.get(f"/api/okrs/krs/{k['id']}").json()["checkins"][-1]["id"]
    client.delete(f"/api/okrs/checkins/{ult}")
    assert client.get(f"/api/okrs/krs/{k['id']}").json()["valor_atual"] == 20
    client.delete(f"/api/okrs/checkins/{ch['id']}")
    assert client.get(f"/api/okrs/krs/{k['id']}").json()["valor_atual"] == 0


def test_status_fora_do_ciclo(db_sessao):
    c = Ciclo(nome="Passado", inicio=date(2025, 1, 1), fim=date(2025, 3, 31))
    o = Objetivo(titulo="O", ciclo=c)
    k = ResultadoChave(descricao="k", valor_inicial=0, valor_alvo=10, valor_atual=4, objetivo=o)
    db_sessao.add(c)
    db_sessao.commit()
    assert servico.status_kr(k) == "encerrado"
    assert servico.status_kr(k, ref=date(2024, 12, 1)) == "nao_iniciado"
    k.valor_atual = 10
    assert servico.status_kr(k) == "concluido"


def test_duplicar_ciclo(client, db_sessao):
    c = _ciclo(client, nome="T1")
    o = client.post(f"/api/okrs/ciclos/{c['id']}/objetivos", json={"titulo": "Crescer", "krs": [
        {"descricao": "Clientes", "valor_inicial": 10, "valor_alvo": 50}]}).json()
    client.post(f"/api/okrs/krs/{o['krs'][0]['id']}/checkins", json={"valor": 30})
    r = client.post("/okrs/ciclos", data={"nome": "T2", "inicio": "2030-01-01", "fim": "2030-03-31",
                                          "copiar_de": c["id"], "partir_do_atual": "1"})
    assert "Ciclo T2 criado" in r.text
    novo = next(x for x in client.get("/api/okrs/ciclos").json() if x["nome"] == "T2")
    k = client.get(f"/api/okrs/ciclos/{novo['id']}").json()["objetivos"][0]["krs"][0]
    assert (k["valor_inicial"], k["valor_atual"], k["valor_alvo"]) == (30, 30, 50)


def test_paginas(client):
    assert "Nenhum ciclo" in client.get("/okrs").text
    mid = client.post("/api/equipe", json={"nome": "Lia Moura"}).json()["id"]
    c = _ciclo(client)
    r = client.post(f"/okrs/ciclos/{c['id']}/objetivo", data={
        "titulo": "Ser referência", "dono_id": str(mid), "n_krs": "3",
        "kr0_descricao": "Treinamentos", "kr0_tipo": "numero", "kr0_valor_inicial": "0", "kr0_valor_alvo": "4",
        "kr0_responsavel_id": str(mid), "kr1_descricao": "Manual publicado", "kr1_tipo": "binario",
        "kr2_descricao": ""})
    assert "Objetivo criado" in r.text and "Treinamentos" in r.text and "Manual publicado" in r.text
    kid = client.get(f"/api/okrs/ciclos/{c['id']}").json()["objetivos"][0]["krs"][0]["id"]
    oid = client.get(f"/api/okrs/ciclos/{c['id']}").json()["objetivos"][0]["id"]
    r = client.post(f"/okrs/krs/{kid}/checkin", data={"valor": "2,5", "confianca": "8", "comentario": "ok"})
    assert "Check-in registrado: 2,5" in r.text
    assert client.post(f"/okrs/krs/{kid}/checkin", data={"valor": "abc"}).text.count("Valor inválido") >= 1
    for url in ("/okrs", f"/okrs?ciclo={c['id']}&dono={mid}", f"/okrs?dono=equipe", "/okrs/ciclos",
                f"/okrs/krs/{kid}", f"/okrs/objetivos/{oid}", f"/okrs/ciclos/{c['id']}/objetivo",
                f"/equipe/{mid}", "/"):
        assert client.get(url).status_code == 200, url
    assert "Ser referência" in client.get(f"/equipe/{mid}").text
    assert "Progresso T1" in client.get("/").text
