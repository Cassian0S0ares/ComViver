#!/usr/bin/env bash
# ComViver - servidor de desenvolvimento (equivalente Linux do iniciar.bat)

cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY="$PWD/.venv/bin/python"
[ -x "$PWD/.venv312/bin/python" ] && PY="$PWD/.venv312/bin/python"
export DJANGO_SETTINGS_MODULE=comviver.settings.dev
PORTA=8000

pausar() {
    read -rp "Pressione Enter para sair..." _
}

if [ ! -x "$PY" ]; then
    echo "[ERRO] Ambiente virtual nao encontrado em .venv"
    echo "Crie com: python3.12 -m venv .venv && .venv/bin/pip install -r requirements/dev.txt"
    pausar
    exit 1
fi

if [ ! -f .env ]; then
    echo "[ERRO] Arquivo .env nao encontrado. Copie .env.example para .env e preencha."
    pausar
    exit 1
fi

echo
echo "=== ComViver ==="
echo "Testando conexao com o banco..."
if ! "$PY" manage.py check --database default; then
    echo "[ERRO] Falha na verificacao do Django/banco."
    pausar
    exit 1
fi

echo "Aplicando migracoes pendentes..."
if ! "$PY" manage.py migrate --noinput; then
    echo "[ERRO] Falha ao aplicar migracoes."
    pausar
    exit 1
fi

echo "O navegador sera aberto quando o servidor estiver pronto."
"$PY" scripts/abrir_navegador.py "$PORTA" &
NAVEGADOR_PID=$!
trap 'kill "$NAVEGADOR_PID" 2>/dev/null' EXIT

echo "Servidor iniciando. Feche esta janela ou pressione Ctrl+C para parar."
echo
"$PY" manage.py runserver "$PORTA"
