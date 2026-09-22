@echo off
setlocal
title ComViver - servidor de desenvolvimento
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%~dp0.venv312\Scripts\python.exe" set "PY=%~dp0.venv312\Scripts\python.exe"
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

echo O navegador sera aberto quando o servidor estiver pronto.
start "" /b "%PY%" "%~dp0scripts\abrir_navegador.py" %PORTA%

echo Servidor iniciando. Feche esta janela ou pressione Ctrl+C para parar.
echo.
"%PY%" manage.py runserver %PORTA%

pause
endlocal
