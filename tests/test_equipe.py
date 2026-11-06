def test_saude(client):
    assert client.get("/saude").json() == {"status": "ok"}


def test_crud_membro(client):
    r = client.post("/api/equipe", json={"nome": "Ana", "cargo": "Analista", "data_admissao": "2024-03-01"})
    assert r.status_code == 201
    mid = r.json()["id"]

    assert client.patch(f"/api/equipe/{mid}", json={"ativo": False}).json()["ativo"] is False
    assert client.get("/api/equipe?apenas_ativos=true").json() == []
    assert client.delete(f"/api/equipe/{mid}").status_code == 204
    assert client.get(f"/api/equipe/{mid}").status_code == 404


def test_paginas(client):
    assert client.get("/").status_code == 200
    client.post("/equipe", data={"nome": "Bruno"})
    assert "Bruno" in client.get("/equipe").text
