# Aplica as migrations e cria o administrador em um banco remoto (ex.: Neon).
# Uso, na raiz do projeto:  powershell -ExecutionPolicy Bypass -File scripts\preparar_banco_remoto.ps1
# A URI do banco é pedida na hora e fica só neste processo; nada é gravado em disco.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$venv = ".venv-deploy"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    py -3.12 -m venv $venv 2>$null
    if (-not (Test-Path "$venv\Scripts\python.exe")) {
        Write-Host "Python 3.12 não encontrado; usando o Python padrão." -ForegroundColor Yellow
        py -m venv $venv
    }
    # WeasyPrint só é usado para PDF no servidor; aqui não é necessário.
    Get-Content requirements\base.txt | Where-Object { $_ -notmatch "^weasyprint" } |
        Set-Content "$venv\requisitos.txt"
    & "$venv\Scripts\python.exe" -m pip install -q -r "$venv\requisitos.txt"
}

$uri = Read-Host "Cole a DATABASE_URL do Neon (conexão direta, sem -pooler)"
if ($uri -match "-pooler") { throw "Use a URI direta, sem '-pooler' no host." }
$uri = $uri -replace "[?&]channel_binding=[^&]*", ""

$env:DATABASE_URL = $uri.Trim()
$env:SECRET_KEY = "somente-para-comandos-locais"
$env:ALLOWED_HOSTS = "localhost"
$env:DJANGO_SETTINGS_MODULE = "comviver.settings.prod"

$py = "$venv\Scripts\python.exe"
Write-Host "`n[1/2] Aplicando migrations..." -ForegroundColor Cyan
& $py manage.py migrate --noinput
Write-Host "`n[2/2] Criando o administrador..." -ForegroundColor Cyan
& $py manage.py createsuperuser
Write-Host "`nPronto." -ForegroundColor Green
