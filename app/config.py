import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    """Carrega variáveis de um arquivo .env simples (CHAVE=valor), se existir."""
    env = BASE_DIR / ".env"
    if not env.exists():
        return
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"'))


_load_env()

APP_NOME = os.getenv("APP_NOME", "Gestão da Equipe")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'gestao.db'}")
# Se definidos, o app exige login HTTP Basic (recomendado fora da sua máquina)
APP_USUARIO = os.getenv("APP_USUARIO", "")
APP_SENHA = os.getenv("APP_SENHA", "")
