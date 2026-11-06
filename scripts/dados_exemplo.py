"""Popula o banco com uma equipe fictícia para demonstração.

Uso: python scripts/dados_exemplo.py [--limpar]
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, criar_tabelas, engine  # noqa: E402
from app.ferramentas.ausencias.models import Ausencia, RegraCobertura  # noqa: E402
from app.ferramentas.equipe.models import Membro  # noqa: E402
from app.ferramentas.okrs.models import Checkin, Ciclo, Objetivo, ResultadoChave  # noqa: E402
from app.ferramentas.um_a_um.models import Acao, ConfigUmAUm, Reuniao, Topico  # noqa: E402

random.seed(42)
HOJE = date.today()

PESSOAS = [
    ("Ana Ribeiro", "Coordenadora", "Operações", 2019, 3),
    ("Bruno Carvalho", "Analista Sênior", "Operações", 2021, 7),
    ("Camila Duarte", "Analista Pleno", "Operações", 2023, 2),
    ("Diego Fernandes", "Analista Júnior", "Operações", 2024, 12),
    ("Elisa Gomes", "Especialista", "Dados", 2020, 11),
    ("Felipe Hashimoto", "Analista de Dados", "Dados", 2022, 5),
    ("Gabriela Ito", "Cientista de Dados", "Dados", 2024, 1),
    ("Henrique Lopes", "Analista de Suporte", "Atendimento", 2021, 4),
    ("Isabela Martins", "Analista de Suporte", "Atendimento", 2023, 8),
    ("João Nogueira", "Assistente", "Atendimento", 2025, 2),
]


def segunda(d: date) -> date:
    return d - timedelta(days=d.weekday())


def criar(db):
    membros = []
    for i, (nome, cargo, area, ano, mes) in enumerate(PESSOAS):
        login = nome.lower().split()[0]
        m = Membro(nome=nome, cargo=cargo, area=area, email=f"{login}@exemplo.com.br",
                   telefone=f"(11) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
                   data_admissao=date(ano, mes, random.randint(1, 28)),
                   data_nascimento=date(random.randint(1980, 2000), random.randint(1, 12), random.randint(1, 28)))
        if i == 3:  # aniversário em breve, para o painel
            m.data_nascimento = (HOJE + timedelta(days=5)).replace(year=1998)
        membros.append(m)
    db.add_all(membros)
    db.flush()

    db.add_all([RegraCobertura(area="Operações", minimo_presentes=3),
                RegraCobertura(area="Atendimento", minimo_presentes=2)])

    a = []
    ana, bruno, camila, diego, elisa, felipe, gabi, henrique, isabela, joao = membros
    db.flush()
    # férias passadas: quita cada período aquisitivo já completado (Diego fica com um período "vencendo")
    from app.ferramentas.ausencias import servico as aus
    for m in membros:
        periodos = aus.saldo(db, m).periodos
        for idx, p in enumerate(periodos):
            if not p.adquirido:
                continue
            ini = segunda(p.fim + timedelta(days=random.randint(60, 200)))
            if ini + timedelta(days=29) >= HOJE - timedelta(days=7) or (m is diego and idx == len(periodos) - 2):
                continue
            if random.random() < 0.5:
                a.append(Ausencia(membro=m, tipo="ferias", inicio=ini, fim=ini + timedelta(days=29), status="aprovada"))
            else:  # fracionadas 20 + 10
                ini2 = segunda(ini + timedelta(days=random.randint(70, 120)))
                a.append(Ausencia(membro=m, tipo="ferias", inicio=ini, fim=ini + timedelta(days=19), status="aprovada"))
                a.append(Ausencia(membro=m, tipo="ferias", inicio=ini2, fim=ini2 + timedelta(days=9), status="aprovada"))
            db.add_all(a[-2:])
            db.flush()
    # acontecendo agora / em breve
    a += [
        Ausencia(membro=bruno, tipo="ferias", inicio=segunda(HOJE), fim=segunda(HOJE) + timedelta(days=13),
                 status="aprovada", observacao="Viagem em família"),
        Ausencia(membro=elisa, tipo="treinamento", inicio=HOJE + timedelta(days=3), fim=HOJE + timedelta(days=4),
                 status="aprovada", observacao="Conferência de dados"),
        Ausencia(membro=henrique, tipo="licenca_medica", inicio=HOJE - timedelta(days=1), fim=HOJE + timedelta(days=1),
                 status="aprovada"),
        Ausencia(membro=felipe, tipo="folga", inicio=HOJE + timedelta(days=8), fim=HOJE + timedelta(days=8),
                 status="aprovada", observacao="Banco de horas"),
        # pendentes (uma com conflito de cobertura em Operações)
        Ausencia(membro=camila, tipo="ferias", inicio=segunda(HOJE) + timedelta(days=7),
                 fim=segunda(HOJE) + timedelta(days=21), status="solicitada"),
        Ausencia(membro=isabela, tipo="ferias", inicio=segunda(HOJE) + timedelta(days=35),
                 fim=segunda(HOJE) + timedelta(days=49), status="solicitada", dias_vendidos=10),
        Ausencia(membro=gabi, tipo="folga", inicio=HOJE + timedelta(days=12), fim=HOJE + timedelta(days=12),
                 status="solicitada"),
    ]
    db.add_all(a)
    n_reunioes = criar_um_a_um(db, membros)
    n_krs = criar_okrs(db, membros)
    db.commit()
    print(f"{len(membros)} membros, {len(a)} ausências, {n_reunioes} 1:1s e {n_krs} KRs criados.")


ANOTACOES = [
    "Falamos sobre as entregas do mês. Está confiante com o projeto atual.",
    "Comentou que as reuniões estão tomando muito tempo; vamos revisar a agenda do time.",
    "Quer se aprofundar em automação. Combinamos buscar um curso.",
    "Relatou dificuldade de alinhamento com outra área. Vou intermediar.",
    "Semana puxada por causa do fechamento. Pediu ajuda para priorizar.",
    "Ótimo momento, recebeu elogio do cliente interno.",
]
ACOES = ["Montar plano de desenvolvimento", "Revisar processo de fechamento", "Inscrever-se no curso de SQL",
         "Agendar conversa com a área de TI", "Documentar rotina de conciliação", "Apresentar resultado ao time"]


def criar_um_a_um(db, membros):
    total = 0
    perfis = {  # (cadência, deslocamento da última 1:1, tendência de humor)
        "Ana": (14, 5, [4, 4, 5, 4]), "Bruno": (14, 25, [4, 3, 3, 3]), "Camila": (14, 10, [4, 3, 2, 2]),
        "Diego": (7, 3, [3, 4, 4, 5]), "Elisa": (21, 12, [5, 5, 4, 5]), "Felipe": (14, 30, [3, 3, 4, 3]),
        "Gabriela": (14, 8, [4, 4, 4, 4]), "Henrique": (14, 16, [3, 3, 2, 3]), "Isabela": (14, 2, [4, 5, 4, 4]),
    }
    for m in membros:
        if m.primeiro_nome not in perfis:
            continue  # João: nunca teve 1:1
        cad, desloc, humores = perfis[m.primeiro_nome]
        db.add(ConfigUmAUm(membro_id=m.id, cadencia_dias=cad, pausado=False))
        datas = [HOJE - timedelta(days=desloc + cad * i) for i in range(len(humores))][::-1]
        for i, (d, h) in enumerate(zip(datas, humores)):
            carga = 5 if m.primeiro_nome == "Camila" and i >= 2 else random.choice([2, 3, 3, 4])
            r = Reuniao(membro_id=m.id, data=d, status="realizada", humor=h, carga=carga,
                        pauta="- Prioridades da semana\n- Bloqueios", anotacoes=random.choice(ANOTACOES))
            db.add(r)
            db.flush()
            total += 1
            if random.random() < 0.6:
                prazo = d + timedelta(days=random.choice([7, 14, 21]))
                db.add(Acao(membro_id=m.id, reuniao_id=r.id, descricao=random.choice(ACOES),
                            responsavel=random.choice(["membro", "membro", "gestor"]), prazo=prazo,
                            concluida=i < len(humores) - 2, concluida_em=prazo if i < len(humores) - 2 else None))
        if m.primeiro_nome in ("Diego", "Gabriela"):
            prox = HOJE + timedelta(days=2)
            prox += timedelta(days=(7 - prox.weekday()) % 7 if prox.weekday() >= 5 else 0)
            db.add(Reuniao(membro_id=m.id, data=prox, status="agendada"))
    ana, bruno, camila = membros[:3]
    db.add_all([Topico(membro_id=camila.id, texto="Volume de demandas do fechamento", autor="gestor"),
                Topico(membro_id=camila.id, texto="Quer conversar sobre férias", autor="membro"),
                Topico(membro_id=bruno.id, texto="Feedback da apresentação para a diretoria", autor="gestor")])
    return total


def main():
    if "--limpar" in sys.argv:
        import app.ferramentas  # noqa: F401
        Base.metadata.drop_all(engine)
    criar_tabelas()
    with SessionLocal() as db:
        if db.query(Membro).count() and "--limpar" not in sys.argv:
            sys.exit("O banco já tem dados. Use --limpar para recriar (apaga tudo!).")
        criar(db)



def criar_okrs(db, membros):
    from app.util import somar_meses
    ana, bruno, camila, diego, elisa, felipe, gabi, henrique, isabela, joao = membros
    tri = (HOJE.month - 1) // 3
    ini = date(HOJE.year, tri * 3 + 1, 1)
    fim = somar_meses(ini, 3) - timedelta(days=1)
    ant_ini = somar_meses(ini, -3)
    anterior = Ciclo(nome=f"{ant_ini.year} T{(ant_ini.month - 1) // 3 + 1}", inicio=ant_ini, fim=ini - timedelta(days=1),
                     arquivado=False)
    atual = Ciclo(nome=f"{ini.year} T{tri + 1}", inicio=ini, fim=fim)
    # (objetivo, dono, [(kr, tipo, inicial, alvo, unidade, responsável, fração atingida, confiança)])
    plano = [
        ("Encantar nossos clientes internos", None, [
            ("Aumentar o NPS interno", "numero", 32, 60, "pontos", ana, 0.55, 7),
            ("Reduzir o tempo médio de resposta", "numero", 48, 24, "horas", henrique, 0.35, 5),
            ("Publicar a central de autoatendimento", "binario", 0, 1, None, isabela, 0, 6),
        ]),
        ("Automatizar a rotina operacional", bruno, [
            ("Processos automatizados", "numero", 2, 10, "processos", bruno, 0.62, 8),
            ("Horas manuais economizadas por mês", "numero", 0, 120, "h", camila, 0.2, 3),
        ]),
        ("Decidir com dados", elisa, [
            ("Painéis em produção no Qlik", "numero", 3, 8, "painéis", felipe, 0.6, 8),
            ("Cobertura de qualidade de dados", "percentual", 60, 95, None, gabi, 0.5, 7),
            ("Economia gerada por análises", "moeda", 0, 50000, None, elisa, 0.48, 6),
        ]),
    ]
    n = 0
    for c, fator in ((anterior, 1.0), (atual, 1.0)):
        for i, (titulo, dono, krs) in enumerate(plano):
            o = Objetivo(titulo=titulo, dono=dono, ordem=i, ciclo=c)
            for desc, tipo, v0, alvo, un, resp, frac, conf in krs:
                k = ResultadoChave(descricao=desc, tipo=tipo, valor_inicial=v0, valor_alvo=alvo, unidade=un,
                                   responsavel=resp, valor_atual=v0, objetivo=o)
                n += 1
                if c is anterior:
                    frac, conf = random.choice([0.7, 0.85, 1.0, 1.0]), None
                hoje_ref = min(HOJE, c.fim)
                dias = (hoje_ref - c.inicio).days
                pontos = max(1, dias // 14)
                for j in range(1, pontos + 1):
                    d = c.inicio + timedelta(days=j * 14)
                    if d > hoje_ref:
                        break
                    if tipo == "binario":
                        v = 1 if (c is anterior and frac >= 1 and j == pontos) else 0
                    else:
                        ruido = random.uniform(-0.05, 0.05) if j < pontos else 0
                        v = round(v0 + (alvo - v0) * max(0, min(1, frac * j / pontos + ruido)), 1)
                    k.checkins.append(Checkin(data=d, valor=v, confianca=conf if j == pontos else random.randint(6, 9),
                                              comentario="Atualização quinzenal" if j < pontos else None))
                    k.valor_atual = v
            db.add(o)
    db.add_all([anterior, atual])
    return n


if __name__ == "__main__":
    main()
