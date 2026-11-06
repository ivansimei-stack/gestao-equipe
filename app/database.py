from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def ativar_fk_sqlite(eng) -> None:
    """SQLite só respeita ON DELETE CASCADE com foreign_keys=ON."""
    if eng.dialect.name == "sqlite":
        @event.listens_for(eng, "connect")
        def _fk(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")


ativar_fk_sqlite(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def criar_tabelas() -> None:
    # Importa os modelos de todas as ferramentas para registrá-los no metadata
    import app.ferramentas  # noqa: F401

    Base.metadata.create_all(bind=engine)
