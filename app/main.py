from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_NOME
from app.database import criar_tabelas
from app.ferramentas import FERRAMENTAS
from app.web import templates


@asynccontextmanager
async def lifespan(_: FastAPI):
    criar_tabelas()
    yield


app = FastAPI(title=APP_NOME, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

for f in FERRAMENTAS:
    app.include_router(f["router"])

templates.env.globals["FERRAMENTAS"] = FERRAMENTAS


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def inicio(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/saude", tags=["sistema"])
def saude():
    return {"status": "ok"}
