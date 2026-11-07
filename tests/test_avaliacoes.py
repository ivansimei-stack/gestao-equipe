from datetime import date, timedelta


def _setup(client):
    mid = client.post("/api/equipe", json={"nome": "Rita Alves", "area": "TI"}).json()["id"]
    c = client.post("/api/avaliacoes/ciclos", json={"nome": "2026", "inicio": "2026-01-01", "fim": "2026-12-31",
                                                    "criterios": [{"nome": "Entrega", "peso": 2},
                                                                  {"nome": "Colaboração", "peso": 1}]}).json()
    return mid, c


def _notas(c, *valores):
    return [{"criterio_id": k["id"], "nota": v} for k, v in zip(c["criterios"], valores)]


def test_criterios_padrao(client):
    c = client.post("/api/avaliacoes/ciclos", json={"nome": "X", "inicio": "2026-01-01", "fim": "2026-06-30"}).json()
    assert len(c["criterios"]) == 6
    assert client.post("/api/avaliacoes/ciclos", json={"nome": "X", "inicio": "2026-06-01",
                                                       "fim": "2026-01-01"}).status_code == 422


def test_nota_ponderada_ninebox_e_gap(client):
    mid, c = _setup(client)
    url = f"/api/avaliacoes/ciclos/{c['id']}/membros/{mid}"
    r = client.put(f"{url}/auto", json={"notas": _notas(c, 5, 5), "enviar": True}).json()
    assert r["status"] == "enviada" and r["nota_final"] == 5
    # gestor: (4*2 + 2*1)/3 = 3.33 -> desempenho médio; potencial alto -> "Forte potencial"
    r = client.put(f"{url}/gestor", json={"notas": _notas(c, 4, 2), "potencial": 3, "enviar": True}).json()
    assert r["nota_final"] == 3.33
    res = client.get(f"/api/avaliacoes/ciclos/{c['id']}/resultados").json()[0]
    assert res["nine_box"] == "Forte potencial" and res["gap"] == 1.67
    pagina = client.get(f"/avaliacoes/ciclos/{c['id']}/calibracao").text
    assert "Colaboração: 5×2" in pagina  # divergência ≥ 2


def test_envio_exige_tudo_e_reabrir(client):
    mid, c = _setup(client)
    url = f"/api/avaliacoes/ciclos/{c['id']}/membros/{mid}/gestor"
    assert client.put(url, json={"notas": _notas(c, 4), "enviar": True}).status_code == 422
    assert client.put(url, json={"notas": _notas(c, 4, 4), "enviar": True}).status_code == 422  # falta potencial
    assert client.put(url, json={"notas": _notas(c, 4, 4), "potencial": 2, "enviar": True}).json()["status"] == "enviada"
    # ciclo encerrado bloqueia edição
    client.post(f"/api/avaliacoes/ciclos/{c['id']}/status/encerrado")
    assert client.put(url, json={"notas": _notas(c, 1, 1)}).status_code == 409
    assert client.put(url, json={"notas": [{"criterio_id": c["criterios"][0]["id"], "nota": 9}]}).status_code == 422


def test_paginas_formulario(client):
    mid, c = _setup(client)
    k1, k2 = (k["id"] for k in c["criterios"])
    base = f"/avaliacoes/ciclos/{c['id']}/membros/{mid}"
    # envio incompleto mantém rascunho e mostra erro
    r = client.post(f"{base}/gestor", data={f"nota_{k1}": "4", "pontos_fortes": "Dedicação", "acao": "enviar"})
    assert "Preencha todas as notas" in r.text and "Dedicação" in r.text
    r = client.post(f"{base}/gestor", data={f"nota_{k1}": "4", f"nota_{k2}": "5", "potencial": "2",
                                            "pontos_fortes": "Dedicação", "acao": "enviar"})
    assert "Avaliação do gestor enviada" in r.text and "Forte desempenho" in r.text
    r = client.post(f"{base}/gestor", data={"acao": "reabrir"})
    assert "reaberta" in r.text
    client.post("/avaliacoes/feedbacks", data={"membro_id": mid, "tipo": "reconhecimento",
                                               "texto": "Ótima apresentação", "data": "2026-05-10"})
    assert "Ótima apresentação" in client.get(f"{base}/gestor").text  # aparece como evidência
    client.post("/avaliacoes/pdi", data={"membro_id": mid, "descricao": "Curso de liderança", "tipo": "formal",
                                         "prazo": str(date.today() - timedelta(days=1))})
    for url in ("/avaliacoes", f"/avaliacoes?ciclo={c['id']}", "/avaliacoes/ciclos/novo",
                f"/avaliacoes/ciclos/{c['id']}/criterios", f"/avaliacoes/ciclos/{c['id']}/calibracao", base,
                f"{base}/auto", "/avaliacoes/feedbacks", f"/avaliacoes/feedbacks?membro_id={mid}", f"/equipe/{mid}", "/"):
        assert client.get(url).status_code == 200, url
    assert "Curso de liderança" in client.get(f"/equipe/{mid}").text
    assert "Itens de PDI atrasados" in client.get("/").text
    csv = client.get(f"/avaliacoes/ciclos/{c['id']}/exportar.csv").text
    assert "Rita Alves" in csv


def test_editar_criterios_e_copiar_ciclo(client):
    mid, c = _setup(client)
    k1, k2 = (k["id"] for k in c["criterios"])
    client.post(f"/avaliacoes/ciclos/{c['id']}/criterios", data={
        f"nome_{k1}": "Entregas", f"peso_{k1}": "3", f"nome_{k2}": "Colab", f"peso_{k2}": "1", f"remover_{k2}": "1",
        "novo_nome": "Inovação", "novo_peso": "1,5"})
    nomes = [(k["nome"], k["peso"]) for k in client.get("/api/avaliacoes/ciclos").json()[0]["criterios"]]
    assert nomes == [("Entregas", 3.0), ("Inovação", 1.5)]
    r = client.post("/avaliacoes/ciclos", data={"nome": "2027", "inicio": "2027-01-01", "fim": "2027-12-31",
                                                "copiar_de": str(c["id"])})
    assert "Ciclo criado" in r.text and "Inovação" in r.text


def test_sem_feedback(client):
    mid = client.post("/api/equipe", json={"nome": "Téo"}).json()["id"]
    assert "Sem feedback" in client.get("/").text
    client.post("/api/avaliacoes/feedbacks", json={"membro_id": mid, "texto": "Boa!"})
    assert "Sem feedback" not in client.get("/").text
