from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import APP_NOME

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["APP_NOME"] = APP_NOME
