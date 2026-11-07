@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Rode primeiro o arquivo instalar.bat
    pause
    exit /b 1
)
rem Banco separado, recriado a cada abertura: não mexe nos seus dados reais
set "DATABASE_URL=sqlite:///./data/demonstracao.db"
set "APP_NOME=Gestão da Equipe (DEMONSTRAÇÃO)"
title DEMONSTRAÇÃO - Gestão da Equipe (dados fictícios)
echo.
echo  Gerando equipe fictícia...
".venv\Scripts\python.exe" scripts\dados_exemplo.py --limpar
echo.
echo  Demonstração em http://127.0.0.1:8001 (seus dados reais NÃO são afetados)
echo  Para desligar, feche esta janela.
echo.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8001'"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --log-level warning
if errorlevel 1 pause
