from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import APP_NOME
from app.util import DIAS_SEMANA, MESES

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
env = templates.env
env.globals.update(APP_NOME=APP_NOME, MESES=MESES, DIAS_SEMANA=DIAS_SEMANA, hoje=date.today)


def _data(d, fmt="%d/%m/%Y"):
    return d.strftime(fmt) if d else "—"


def _pct(v, casas=0):
    return f"{(v or 0) * 100:.{casas}f}%"


def _num(v, casas=1):
    if v is None:
        return "—"
    if float(v).is_integer():
        return f"{int(v):,}".replace(",", ".")
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _nota(v):
    return "—" if v is None else f"{v:.2f}".replace(".", ",")


env.filters.update(data=_data, pct=_pct, num=_num, nota=_nota)


def redirecionar(url: str, msg: str | None = None, erro: str | None = None) -> RedirectResponse:
    """Redireciona (303) levando uma mensagem flash pela query string."""
    params = {k: v for k, v in (("msg", msg), ("erro", erro)) if v}
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    return RedirectResponse(url, status_code=303)
