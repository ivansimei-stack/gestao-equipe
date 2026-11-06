import os

os.environ["DATABASE_URL"] = "sqlite://"  # banco em memória para testes

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.main import app as fastapi_app


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.ativar_fk_sqlite(engine)
    import app.ferramentas  # noqa: F401
    database.Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, expire_on_commit=False)

    def _db():
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[database.get_db] = _db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
