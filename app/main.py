import base64
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import config
from app.database import criar_tabelas, get_db
from app.ferramentas import FERRAMENTAS
from app.web import templates


@asynccontextmanager
async def lifespan(_: FastAPI):
    criar_tabelas()
    yield


app = FastAPI(title=config.APP_NOME, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.middleware("http")
async def autenticacao(request: Request, call_next):
    if not (config.APP_USUARIO and config.APP_SENHA) or request.url.path == "/saude":
        return await call_next(request)
    cab = request.headers.get("authorization", "")
    if cab.startswith("Basic "):
        try:
            usuario, _, senha = base64.b64decode(cab[6:]).decode().partition(":")
        except ValueError:
            usuario = senha = ""
        if secrets.compare_digest(usuario, config.APP_USUARIO) and secrets.compare_digest(senha, config.APP_SENHA):
            return await call_next(request)
    return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="gestao"'})


for f in FERRAMENTAS:
    app.include_router(f["router"])

templates.env.globals["FERRAMENTAS"] = FERRAMENTAS


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def inicio(request: Request, db: Session = Depends(get_db)):
    paineis = []
    for f in FERRAMENTAS:
        if f.get("painel"):
            itens = f["painel"](db)
            if itens:
                paineis.append({"ferramenta": f, "itens": itens})
    return templates.TemplateResponse(request, "index.html", {"paineis": paineis})


@app.get("/saude", tags=["sistema"])
def saude():
    return {"status": "ok"}
