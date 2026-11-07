@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Rode primeiro o arquivo instalar.bat
    pause
    exit /b 1
)
rem Se já estiver aberto, só abre o navegador
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/saude -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 (
    start "" http://127.0.0.1:8000
    exit /b 0
)
title Gestão da Equipe - NÃO feche esta janela enquanto usa o sistema
echo.
echo  Gestão da Equipe está ligado em http://127.0.0.1:8000
echo  O navegador vai abrir sozinho. Para desligar, feche esta janela.
echo.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8000'"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning
if errorlevel 1 pause
