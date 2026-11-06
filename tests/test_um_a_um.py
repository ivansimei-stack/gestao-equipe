from datetime import date, timedelta

from app.ferramentas.equipe.models import Membro
from app.ferramentas.um_a_um import servico
from app.ferramentas.um_a_um.models import Reuniao


def _membro(client, nome="Ana Lima"):
    return client.post("/api/equipe", json={"nome": nome}).json()["id"]


def _reuniao(client, mid, dias_atras=0, **kw):
    corpo = {"membro_id": mid, "data": str(date.today() - timedelta(days=dias_atras)), **kw}
    return client.post("/api/um_a_um/reunioes", json=corpo)


def test_situacao_cadencia(client):
    mid = _membro(client)
    sit = lambda: next(s for s in client.get("/api/um_a_um/situacao").json() if s["membro_id"] == mid)  # noqa: E731
    assert sit()["estado"] == "nunca"
    _reuniao(client, mid, dias_atras=20, humor=4, carga=3)
    s = sit()
    assert s["estado"] == "atrasada" and s["dias_atraso"] == 6  # cadência padrão 14
    client.patch(f"/api/um_a_um/config/{mid}", json={"cadencia_dias": 30})
    assert sit()["estado"] == "em_dia"
    _reuniao(client, mid, dias_atras=-3, status="agendada")
    assert sit()["estado"] == "agendada"
    client.patch(f"/api/um_a_um/config/{mid}", json={"pausado": True})
    assert sit()["estado"] == "pausado"


def test_acoes_e_topicos_fluem_para_proxima_reuniao(client):
    mid = _membro(client)
    client.post("/api/um_a_um/topicos", json={"membro_id": mid, "texto": "Promoção", "autor": "membro"})
    r = _reuniao(client, mid, dias_atras=7, humor=3, novas_acoes=[
        {"descricao": "Enviar plano de estudos", "responsavel": "membro", "prazo": str(date.today() - timedelta(days=1))},
        {"descricao": "Conversar com RH", "responsavel": "gestor"},
    ]).json()
    assert len(r["acoes"]) == 2
    acoes = client.get(f"/api/um_a_um/acoes?membro_id={mid}&abertas=true").json()
    assert sum(a["atrasada"] for a in acoes) == 1
    # a pauta da próxima reunião traz tópicos e ações abertas
    pagina = client.get(f"/um_a_um/nova?membro_id={mid}").text
    assert "Promoção" in pagina and "Enviar plano de estudos" in pagina
    topico_id = client.get(f"/api/um_a_um/topicos/{mid}").json()[0]["id"]
    r2 = _reuniao(client, mid, humor=4, concluir_acoes=[acoes[0]["id"]], topicos_discutidos=[topico_id]).json()
    assert [t["texto"] for t in r2["topicos"]] == ["Promoção"]
    assert client.get(f"/api/um_a_um/topicos/{mid}").json() == []
    assert len(client.get(f"/api/um_a_um/acoes?membro_id={mid}&abertas=true").json()) == 1


def test_validacao(client):
    mid = _membro(client)
    assert _reuniao(client, mid, humor=7).status_code == 422
    assert _reuniao(client, mid, status="xyz").status_code == 422


def test_alertas_humor_e_carga(db_sessao):
    m = Membro(nome="Caio")
    db_sessao.add(m)
    db_sessao.commit()
    hoje = date.today()
    for i, (h, c) in enumerate([(5, 3), (4, 4), (3, 5)]):
        db_sessao.add(Reuniao(membro_id=m.id, data=hoje - timedelta(days=30 - i * 10), humor=h, carga=c))
    db_sessao.commit()
    s = servico.situacao(db_sessao, m)
    assert s.humores == [5, 4, 3] and s.alerta_humor  # queda de 2 pontos
    assert s.alerta_carga


def test_paginas(client):
    mid = _membro(client)
    r = client.post("/um_a_um/nova", data={
        "membro_id": mid, "data": str(date.today()), "status": "realizada", "humor": "2", "carga": "5",
        "pauta": "- carreira", "anotacoes": "Conversamos sobre carreira", "notas_privadas": "segredo",
        "acao_descricao": ["Ler livro X", ""], "acao_responsavel": ["membro", "membro"], "acao_prazo": ["", ""]})
    assert "1:1 com Ana registrada" in r.text and "segredo" in r.text
    rid = client.get(f"/api/um_a_um/reunioes?membro_id={mid}").json()[0]["id"]
    client.post(f"/um_a_um/pessoa/{mid}/topicos", data={"texto": "Férias de julho", "autor": "membro"})
    for url in ("/um_a_um", "/um_a_um/acoes", "/um_a_um/acoes?ver=todas&responsavel=gestor",
                f"/um_a_um/pessoa/{mid}", "/um_a_um/nova", f"/um_a_um/{rid}", f"/um_a_um/{rid}?editar=1",
                f"/equipe/{mid}", "/"):
        assert client.get(url).status_code == 200, url
    assert "Sinais de atenção" in client.get("/").text
    assert "Férias de julho" in client.get(f"/um_a_um/pessoa/{mid}").text
    # editar e concluir ação
    client.post(f"/um_a_um/{rid}", data={"data": str(date.today()), "status": "realizada", "humor": "3",
                                          "anotacoes": "editado", "acao_descricao": [], "acao_responsavel": [],
                                          "acao_prazo": []})
    assert client.get(f"/api/um_a_um/reunioes/{rid}").json()["humor"] == 3
    aid = client.get(f"/api/um_a_um/acoes?membro_id={mid}").json()[0]["id"]
    client.post(f"/um_a_um/acoes/{aid}/alternar")
    assert client.get(f"/api/um_a_um/acoes?membro_id={mid}").json()[0]["concluida"] is True
    client.post(f"/um_a_um/{rid}/excluir")
    assert client.get(f"/api/um_a_um/reunioes/{rid}").status_code == 404
    # ação sobrevive à exclusão da reunião (reuniao_id vira nulo)
    assert client.get(f"/api/um_a_um/acoes?membro_id={mid}").json()[0]["reuniao_id"] is None
