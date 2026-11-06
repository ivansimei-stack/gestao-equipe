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
    db.commit()
    print(f"{len(membros)} membros e {len(a)} ausências criados.")


def main():
    if "--limpar" in sys.argv:
        import app.ferramentas  # noqa: F401
        Base.metadata.drop_all(engine)
    criar_tabelas()
    with SessionLocal() as db:
        if db.query(Membro).count() and "--limpar" not in sys.argv:
            sys.exit("O banco já tem dados. Use --limpar para recriar (apaga tudo!).")
        criar(db)


if __name__ == "__main__":
    main()
