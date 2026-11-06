from datetime import date, timedelta


def _membros(client, *nomes):
    return [client.post("/api/equipe", json={"nome": n}).json()["id"] for n in nomes]


def _segunda(d=None):
    d = d or date.today()
    return d - timedelta(days=d.weekday()) + timedelta(days=7)


def _escala(client, ids, **kw):
    return client.post("/api/escalas", json={"nome": "Plantão", "participantes": ids, **kw}).json()


def test_rodizio_semanal(client):
    a, b, c = _membros(client, "Ana", "Beto", "Caio")
    e = _escala(client, [a, b, c])
    ini = _segunda()
    r = client.post(f"/api/escalas/{e['id']}/gerar", json={"de": str(ini), "ate": str(ini + timedelta(days=41))}).json()
    assert r["criados"] == 6
    turnos = client.get(f"/api/escalas/{e['id']}/turnos").json()
    assert [t["membro_id"] for t in turnos] == [a, b, c, a, b, c]
    assert turnos[0]["inicio"] == str(ini) and turnos[0]["fim"] == str(ini + timedelta(days=6))
    # gerar a continuação segue o rodízio
    nova = ini + timedelta(days=42)
    client.post(f"/api/escalas/{e['id']}/gerar", json={"de": str(nova), "ate": str(nova + timedelta(days=6))})
    assert client.get(f"/api/escalas/{e['id']}/turnos").json()[-1]["membro_id"] == a


def test_pula_ausente_e_compensa(client):
    a, b, c = _membros(client, "Ana", "Beto", "Caio")
    e = _escala(client, [a, b, c])
    ini = _segunda()
    # Beto de férias na 2ª semana
    client.post("/api/ausencias", json={"membro_id": b, "tipo": "ferias", "inicio": str(ini + timedelta(days=7)),
                                        "fim": str(ini + timedelta(days=13)), "status": "aprovada"})
    r = client.post(f"/api/escalas/{e['id']}/gerar", json={"de": str(ini), "ate": str(ini + timedelta(days=34))}).json()
    assert len(r["pulos"]) == 1
    ordem = [t["membro_id"] for t in client.get(f"/api/escalas/{e['id']}/turnos").json()]
    assert ordem == [a, c, b, a, b]  # Beto compensa logo que volta (troca de posição com Caio)


def test_diaria_dias_uteis(client):
    a, b = _membros(client, "Ana", "Beto")
    e = _escala(client, [a, b], duracao_dias=1, apenas_dias_uteis=True)
    # semana de carnaval 2027: 08 e 09/02 são feriados
    r = client.post(f"/api/escalas/{e['id']}/gerar", json={"de": "2027-02-08", "ate": "2027-02-14"}).json()
    assert r["criados"] == 3
    assert client.post("/api/escalas", json={"nome": "X", "duracao_dias": 7, "apenas_dias_uteis": True}).status_code == 422


def test_trocas_preservadas_e_permuta(client):
    a, b, c = _membros(client, "Ana", "Beto", "Caio")
    e = _escala(client, [a, b, c])
    ini = _segunda()
    client.post(f"/api/escalas/{e['id']}/gerar", json={"de": str(ini), "ate": str(ini + timedelta(days=20))})
    t1, t2, t3 = client.get(f"/api/escalas/{e['id']}/turnos").json()
    tr = client.post(f"/api/escalas/turnos/{t1['id']}/trocar", json={"membro_id": c, "observacao": "consulta"}).json()
    assert tr["origem"] == "troca" and tr["membro_original_id"] == a
    # regerar mantém a troca
    client.post(f"/api/escalas/{e['id']}/gerar", json={"de": str(ini), "ate": str(ini + timedelta(days=20))})
    assert client.get(f"/api/escalas/{e['id']}/turnos").json()[0]["membro_id"] == c
    # voltar para o original desfaz a troca
    assert client.post(f"/api/escalas/turnos/{t1['id']}/trocar", json={"membro_id": a}).json()["origem"] == "gerado"
    lista = client.get(f"/api/escalas/{e['id']}/turnos").json()
    client.post(f"/api/escalas/turnos/{lista[1]['id']}/permutar", json={"outro_turno_id": lista[2]["id"]})
    assert [t["membro_id"] for t in client.get(f"/api/escalas/{e['id']}/turnos").json()][1:] == [c, b]


def test_conflito_apos_geracao_e_paginas(client):
    a, b = _membros(client, "Ana", "Beto")
    e = _escala(client, [a, b])
    hoje = date.today()
    client.post(f"/api/escalas/{e['id']}/gerar", json={"de": str(hoje), "ate": str(hoje + timedelta(days=27))})
    t = client.get(f"/api/escalas/{e['id']}/turnos").json()[1]
    client.post("/api/ausencias", json={"membro_id": t["membro_id"], "tipo": "folga", "inicio": t["inicio"],
                                        "fim": t["inicio"], "status": "aprovada"})
    pagina = client.get(f"/escalas/{e['id']}").text
    assert "Conflitos com ausências" in pagina
    assert client.get(f"/api/escalas/{e['id']}/agora").json()["membro_id"] == a
    for url in ("/escalas", f"/escalas/{e['id']}?passados=1", f"/equipe/{a}", "/"):
        assert client.get(url).status_code == 200, url
    assert "conflito" in client.get("/").text
    assert "BEGIN:VEVENT" in client.get(f"/escalas/{e['id']}/escala.ics").text
    # formulários
    r = client.post("/escalas", data={"nome": "Suporte", "duracao_dias": "1", "participantes": [str(a), str(b)],
                                      "pular_ausentes": "1"})
    assert "Escala criada" in r.text
    eid = client.get("/api/escalas").json()[-1]["id"]
    r = client.post(f"/escalas/{eid}/gerar", data={"de": str(hoje), "ate": str(hoje + timedelta(days=6))})
    assert "turno(s) gerado(s)" in r.text
    pid = client.get(f"/api/escalas/{eid}").json()["participantes"][1]["id"]
    client.post(f"/escalas/{eid}/participantes/{pid}/subir")
    assert client.get(f"/api/escalas/{eid}").json()["participantes"][0]["membro_id"] == b
