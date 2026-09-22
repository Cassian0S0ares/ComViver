@echo off
setlocal
title ComViver - servidor de desenvolvimento
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "DJANGO_SETTINGS_MODULE=comviver.settings.dev"
set "PORTA=8000"

if not exist "%PY%" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv
    echo Crie com: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements\dev.txt
    pause
    exit /b 1
)

if not exist "%~dp0.env" (
    echo [ERRO] Arquivo .env nao encontrado. Copie .env.example para .env e preencha.
    pause
    exit /b 1
)

echo.
echo === ComViver ===
echo Testando conexao com o banco...
"%PY%" manage.py check --database default
if errorlevel 1 (
    echo [ERRO] Falha na verificacao do Django/banco.
    pause
    exit /b 1
)

echo Aplicando migracoes pendentes...
"%PY%" manage.py migrate --noinput
if errorlevel 1 (
    echo [ERRO] Falha ao aplicar migracoes.
    pause
    exit /b 1
)

echo Abrindo navegador em http://127.0.0.1:%PORTA%/
start "" http://127.0.0.1:%PORTA%/

echo Servidor iniciando. Feche esta janela ou pressione Ctrl+C para parar.
echo.
"%PY%" manage.py runserver %PORTA%

pause
endlocal
