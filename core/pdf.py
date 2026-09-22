"""Recibos locais: o renderizador não acessa a rede nem arquivos arbitrários."""

import mimetypes
import os
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.template.loader import render_to_string

ARQUIVOS_PERMITIDOS = {
    "css/recibo.css",
    "vendor/fonts/manrope.woff2",
    "vendor/fonts/source-sans-3.woff2",
}


def buscar_recurso_local(url, *args, **kwargs):
    partes = urlsplit(url)
    prefixo = settings.STATIC_URL
    if not partes.path.startswith(prefixo) or partes.scheme not in ("", "https"):
        raise ValueError("Recurso externo bloqueado no PDF.")
    if partes.netloc not in ("", "comviver.invalid"):
        raise ValueError("Host externo bloqueado no PDF.")
    nome = partes.path[len(prefixo) :]
    # Whitenoise pode acrescentar hash ao nome em produção.
    from django.contrib.staticfiles.storage import staticfiles_storage

    nomes = {staticfiles_storage.url(item): item for item in ARQUIVOS_PERMITIDOS}
    nome = nomes.get(partes.path, nome)
    if nome not in ARQUIVOS_PERMITIDOS:
        raise ValueError("Arquivo não autorizado no PDF.")
    caminho = finders.find(nome)
    if not caminho:
        raise ValueError("Recurso do recibo não encontrado.")
    return {
        "string": Path(caminho).read_bytes(),
        "mime_type": mimetypes.guess_type(nome)[0] or "application/octet-stream",
    }


def renderizar_pdf(template, contexto, nome_arquivo, request=None):
    # Import tardio: cadastros continuam disponíveis sem o runtime nativo.
    if os.name == "nt" and not os.environ.get("WEASYPRINT_DLL_DIRECTORIES"):
        runtime = settings.BASE_DIR / ".tools" / "weasyprint" / "runtime"
        if runtime.is_dir():
            os.environ["WEASYPRINT_DLL_DIRECTORIES"] = str(runtime)
    from weasyprint import HTML

    html = render_to_string(template, {**contexto, "pdf": True}, request=request)
    pdf = HTML(
        string=html, base_url="https://comviver.invalid/", url_fetcher=buscar_recurso_local
    ).write_pdf()
    resposta = HttpResponse(pdf, content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    resposta["Cache-Control"] = "private, no-store"
    return resposta
