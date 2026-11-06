from datetime import date

from app.util import dias_uteis, feriado, pascoa, somar_meses


def test_pascoa():
    assert pascoa(2025) == date(2025, 4, 20)
    assert pascoa(2026) == date(2026, 4, 5)


def test_feriados():
    assert feriado(date(2026, 2, 17)) == "Carnaval"
    assert feriado(date(2026, 6, 4)) == "Corpus Christi"
    assert feriado(date(2026, 11, 20)) == "Consciência Negra"


def test_dias_uteis():
    # semana de 16 a 20/02/2026: seg e ter de carnaval
    assert dias_uteis(date(2026, 2, 16), date(2026, 2, 22)) == 3


def test_somar_meses():
    assert somar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert somar_meses(date(2026, 11, 15), 3) == date(2027, 2, 15)
