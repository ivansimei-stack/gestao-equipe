from datetime import date, timedelta


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


def test_email_duplicado(client):
    client.post("/api/equipe", json={"nome": "A", "email": "a@x.com"})
    assert client.post("/api/equipe", json={"nome": "B", "email": "a@x.com"}).status_code == 409


def test_paginas(client):
    assert client.get("/").status_code == 200
    r = client.post("/equipe/novo", data={"nome": "Bruno Lima", "area": "TI"})
    assert r.status_code == 200 and "Bruno Lima" in r.text  # segue o redirect para o perfil
    assert "Bruno Lima" in client.get("/equipe").text
    assert "Bruno Lima" in client.get("/equipe?area=TI").text
    assert "Bruno Lima" not in client.get("/equipe?status=inativos").text


def test_editar_e_excluir_pela_pagina(client):
    mid = client.post("/api/equipe", json={"nome": "Carla Souza"}).json()["id"]
    client.post(f"/equipe/{mid}/editar", data={"nome": "Carla S.", "cargo": "Líder"})
    assert client.get(f"/api/equipe/{mid}").json()["cargo"] == "Líder"
    client.post(f"/equipe/{mid}/excluir", data={"confirmacao": "errado"})
    assert client.get(f"/api/equipe/{mid}").status_code == 200
    client.post(f"/equipe/{mid}/excluir", data={"confirmacao": "carla"})
    assert client.get(f"/api/equipe/{mid}").status_code == 404


def test_aniversarios(client):
    amanha = date.today() + timedelta(days=1)
    client.post("/api/equipe", json={"nome": "Davi", "data_nascimento": amanha.replace(year=1990).isoformat(),
                                     "data_admissao": amanha.replace(year=amanha.year - 3).isoformat()})
    pagina = client.get("/").text
    assert "Aniversário" in pagina and "3 anos de casa" in pagina


def test_tempo_de_casa():
    from app.ferramentas.equipe.models import Membro
    m = Membro(nome="X", data_admissao=date(2020, 5, 10))
    assert m.tempo_de_casa(date(2023, 8, 9)) == "3 anos e 2 meses"
    assert m.tempo_de_casa(date(2020, 5, 20)) == "0 meses"
