@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Instalação - Gestão da Equipe
echo.
echo  ============================================
echo     Gestão da Equipe - instalação
echo  ============================================
echo.

rem ---------- 1. Python ----------
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo  [ERRO] Python não encontrado.
    echo.
    echo  Baixe em https://www.python.org/downloads/ e, na primeira tela do
    echo  instalador, MARQUE a opção "Add python.exe to PATH".
    echo  Depois rode este arquivo de novo.
    echo.
    pause
    exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo  [ERRO] É preciso Python 3.11 ou mais novo. Instale a versão atual em python.org.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PY% -c "import sys, platform; print(sys.version.split()[0], platform.machine())"') do set "PYVER=%%v"
echo  [ok] Python encontrado: %PYVER%

rem ---------- 2. Ambiente e dependências ----------
if not exist ".venv\Scripts\python.exe" (
    echo  Criando ambiente isolado...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo  [ERRO] Não foi possível criar o ambiente. Veja a mensagem acima.
        pause
        exit /b 1
    )
)
echo  Instalando componentes (pode levar alguns minutos)...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo  [ERRO] Falha ao instalar os componentes.
    echo   - Se a mensagem fala em "Failed building wheel" ou "Microsoft Visual C++":
    echo     instale o Python 3.13 em https://www.python.org/downloads/windows/
    echo     ^(versao "Windows installer 64-bit"^), apague a pasta .venv daqui e rode de novo.
    echo   - Se fala em "connection", "proxy" ou "SSL": a rede da empresa bloqueou o download.
    echo  Mande um print desta tela para quem esta te ajudando.
    pause
    exit /b 1
)
echo  [ok] Componentes instalados.

rem ---------- 3. Onde ficam os dados ----------
if defined OneDrive (
    set "PASTA_DADOS=%OneDrive%\GestaoEquipe"
) else (
    set "PASTA_DADOS=%USERPROFILE%\Documents\GestaoEquipe"
)
if not exist "%PASTA_DADOS%" mkdir "%PASTA_DADOS%"
if exist ".env" goto env_pronto
> ".env" echo APP_NOME=Gestão da Equipe
>> ".env" echo DATABASE_URL=sqlite:///%PASTA_DADOS:\=/%/gestao.db
:env_pronto
echo  [ok] Seus dados ficarão em: %PASTA_DADOS%

rem ---------- 4. Atalhos na Área de Trabalho ----------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$w = New-Object -ComObject WScript.Shell; $d = [Environment]::GetFolderPath('Desktop');" ^
  "$s = $w.CreateShortcut((Join-Path $d 'Gestão da Equipe.lnk')); $s.TargetPath = '%~dp0iniciar.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,165'; $s.Save();" ^
  "$s = $w.CreateShortcut((Join-Path $d 'Gestão da Equipe (demonstração).lnk')); $s.TargetPath = '%~dp0demonstracao.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,23'; $s.Save()"
echo  [ok] Atalhos criados na Área de Trabalho.

echo.
echo  ============================================
echo   Pronto! Use o atalho "Gestão da Equipe"
echo   na Área de Trabalho para abrir o sistema.
echo  ============================================
echo.
pause
