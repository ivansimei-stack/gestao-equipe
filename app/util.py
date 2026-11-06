"""Utilidades compartilhadas: datas, feriados nacionais e dias úteis."""
from datetime import date, timedelta
from functools import lru_cache


def parse_data(valor: str | None) -> date | None:
    return date.fromisoformat(valor) if valor else None


def parse_int(valor: str | None) -> int | None:
    return int(valor) if valor not in (None, "") else None


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


@lru_cache(maxsize=64)
def feriados_nacionais(ano: int) -> dict[date, str]:
    p = pascoa(ano)
    feriados = {
        date(ano, 1, 1): "Confraternização Universal",
        p - timedelta(days=48): "Carnaval",
        p - timedelta(days=47): "Carnaval",
        p - timedelta(days=2): "Sexta-feira Santa",
        date(ano, 4, 21): "Tiradentes",
        date(ano, 5, 1): "Dia do Trabalho",
        p + timedelta(days=60): "Corpus Christi",
        date(ano, 9, 7): "Independência",
        date(ano, 10, 12): "Nossa Senhora Aparecida",
        date(ano, 11, 2): "Finados",
        date(ano, 11, 15): "Proclamação da República",
        date(ano, 12, 25): "Natal",
    }
    if ano >= 2024:
        feriados[date(ano, 11, 20)] = "Consciência Negra"
    return feriados


def feriado(d: date) -> str | None:
    return feriados_nacionais(d.year).get(d)


def eh_dia_util(d: date) -> bool:
    return d.weekday() < 5 and feriado(d) is None


def dias(inicio: date, fim: date):
    d = inicio
    while d <= fim:
        yield d
        d += timedelta(days=1)


def dias_corridos(inicio: date, fim: date) -> int:
    return (fim - inicio).days + 1


def dias_uteis(inicio: date, fim: date) -> int:
    return sum(1 for d in dias(inicio, fim) if eh_dia_util(d))


def sobrepoe(a_ini: date, a_fim: date, b_ini: date, b_fim: date) -> bool:
    return a_ini <= b_fim and b_ini <= a_fim


def inicio_mes(d: date) -> date:
    return d.replace(day=1)


def fim_mes(d: date) -> date:
    prox = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return prox - timedelta(days=1)


def somar_meses(d: date, meses: int) -> date:
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return d.replace(year=ano, month=mes, day=min(d.day, fim_mes(date(ano, mes, 1)).day))


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
