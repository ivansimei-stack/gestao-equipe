from datetime import date, timedelta


def _base(client):
    ids = [client.post("/api/equipe", json={"nome": n, "area": "TI"}).json()["id"] for n in ("Ana", "Beto", "Caio")]
    c = client.post("/api/competencias", json={"nome": "Fechamento", "critica": True, "minimo_pessoas": 2}).json()
    return ids, c


def test_fator_onibus_e_risco(client):
    (a, b, c_), comp = _base(client)
    an = lambda: next(x for x in client.get("/api/competencias/analise").json() if x["competencia_id"] == comp["id"])  # noqa
    assert an()["risco"] == "sem_cobertura"
    client.put(f"/api/competencias/{comp['id']}/membros/{a}", json={"nivel": 4})
    assert an()["fator_onibus"] == 1 and an()["risco"] == "alto"
    client.put(f"/api/competencias/{comp['id']}/membros/{b}", json={"nivel": 3})
    assert an()["risco"] == "ok"
    assert client.put(f"/api/competencias/{comp['id']}/membros/{b}", json={"nivel": 7}).status_code == 422


def test_dias_sem_cobertura_por_ausencia(client):
    (a, b, c_), comp = _base(client)
    client.put(f"/api/competencias/{comp['id']}/membros/{a}", json={"nivel": 3})
    d = date.today() + timedelta(days=10)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    client.post("/api/ausencias", json={"membro_id": a, "tipo": "folga", "inicio": str(d), "fim": str(d),
                                        "status": "aprovada"})
    x = next(x for x in client.get("/api/competencias/analise").json() if x["competencia_id"] == comp["id"])
    assert str(d) in x["dias_descobertos"]
    assert "Críticas sem cobertura" in client.get("/").text


def test_mentoria_vira_pdi(client):
    (a, b, c_), comp = _base(client)
    client.put(f"/api/competencias/{comp['id']}/membros/{a}", json={"nivel": 4})
    client.put(f"/api/competencias/{comp['id']}/membros/{c_}", json={"nivel": 1, "interesse": True})
    pagina = client.get("/competencias/riscos").text
    assert "quer aprender" in pagina
    r = client.post("/competencias/mentoria-pdi", data={"competencia_id": comp["id"], "mentor_id": a, "aprendiz_id": c_})
    assert "Item de PDI criado para Caio" in r.text
    assert client.get(f"/api/avaliacoes/pdi?membro_id={c_}").json()[0]["descricao"] == "Desenvolver Fechamento com mentoria de Ana"


def test_matriz_formulario_e_paginas(client):
    (a, b, c_), comp = _base(client)
    r = client.post("/competencias/matriz", data={f"n_{a}_{comp['id']}": "3", f"i_{b}_{comp['id']}": "on",
                                                  f"n_{b}_{comp['id']}": "1", f"n_{c_}_{comp['id']}": "0"})
    assert "2 nível(is) atualizado(s)" in r.text
    niveis = {(n["membro_id"]): n for n in client.get("/api/competencias/matriz").json()}
    assert niveis[a]["nivel"] == 3 and niveis[b]["interesse"] is True and c_ not in niveis
    client.post("/competencias/catalogo/exemplos")
    assert len(client.get("/api/competencias").json()) == 10
    r = client.post("/competencias/catalogo", data={"nome": "", "categoria": "X"})
    assert "Informe o nome" in r.text
    for url in ("/competencias", "/competencias?editar=1&area=TI", "/competencias/riscos", "/competencias/catalogo",
                f"/competencias/pessoa/{a}", f"/equipe/{a}", "/"):
        assert client.get(url).status_code == 200, url
    assert "Fechamento" in client.get(f"/equipe/{a}").text
