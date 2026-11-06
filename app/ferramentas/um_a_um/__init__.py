from datetime import date

from app.ferramentas.um_a_um import models  # noqa: F401
from app.ferramentas.um_a_um import servico
from app.ferramentas.um_a_um.router import router


def painel(db):
    sits = servico.situacoes(db)
    db.commit()
    if not sits:
        return []
    atrasadas = [s for s in sits if s.estado in ("atrasada", "nunca")]
    hoje = [s for s in sits if s.agendada and s.agendada.data == date.today()]
    humor = [s for s in sits if s.alerta_humor or s.alerta_carga]
    acoes_atrasadas = sum(s.acoes_atrasadas for s in sits)
    return [
        {"titulo": "1:1s atrasadas", "valor": len(atrasadas), "link": "/um_a_um",
         "nivel": "risco" if atrasadas else "ok",
         "detalhe": ", ".join(s.membro.primeiro_nome for s in atrasadas[:4]) or "todas em dia"},
        {"titulo": "1:1s hoje", "valor": len(hoje), "link": "/um_a_um",
         "detalhe": ", ".join(s.membro.primeiro_nome for s in hoje[:4])},
        {"titulo": "Sinais de atenção", "valor": len(humor), "link": "/um_a_um",
         "nivel": "alerta" if humor else "ok", "detalhe": ", ".join(s.membro.primeiro_nome for s in humor[:4])
         or "humor e carga ok"},
        {"titulo": "Ações atrasadas", "valor": acoes_atrasadas, "link": "/um_a_um/acoes",
         "nivel": "alerta" if acoes_atrasadas else "ok"},
    ]


def perfil(db, membro):
    s = servico.situacao(db, membro)
    db.commit()
    return {"s": s, "estados": servico.ESTADOS, "acoes": servico.acoes(db, membro_id=membro.id, abertas=True)}


FERRAMENTA = {
    "slug": "um_a_um",
    "nome": "1:1s",
    "descricao": "Reuniões individuais: cadência, pauta, humor e carga, tópicos e ações combinadas.",
    "router": router,
    "painel": painel,
    "perfil": perfil,
}
