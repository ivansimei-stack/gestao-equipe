.PHONY: setup dev test nova exemplo

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

dev:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	.venv/bin/pytest -q

# uso: make nova NOME=ferias
nova:
	.venv/bin/python scripts/nova_ferramenta.py $(NOME)

# popula com dados fictícios (use LIMPAR=1 para apagar tudo antes)
exemplo:
	.venv/bin/python scripts/dados_exemplo.py $(if $(LIMPAR),--limpar,)
