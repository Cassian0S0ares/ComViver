import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404

# Prefixos cujo conteudo e vedado ao perfil Operacional.
PREFIXOS_SIGILOSOS = ("acolhidos/documentos/", "acolhidos/consentimentos/")

# Tipos que o navegador pode renderizar em linha com seguranca. Qualquer outro
# e entregue como download.
TIPOS_EM_LINHA = {"image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"}


@login_required
def servir_media_protegida(request, caminho: str):
    """Entrega uploads do banco (ou arquivos locais antigos) a quem pode ve-los.

    Arquivo em diretorio publico ficaria acessivel a quem descobrisse a URL —
    e aqui isso significaria a foto de uma crianca acolhida exposta sem login.
    """
    raiz = Path(settings.MEDIA_ROOT).resolve()
    destino = (raiz / caminho).resolve()

    # Impede travessia de diretorio: `../` sairia de media/ e alcancaria o .env.
    if not destino.is_relative_to(raiz):
        raise PermissionDenied("Caminho inválido.")

    # O prefixo e conferido no destino ja resolvido: no caminho bruto,
    # `acolhidos/fotos/../documentos/x.pdf` passaria pela checagem.
    relativo = destino.relative_to(raiz).as_posix()
    if relativo.startswith("_rascunhos/"):
        raise Http404("Arquivo não encontrado.")
    if relativo.startswith(PREFIXOS_SIGILOSOS) and not request.user.pode_ver_ficha_completa():
        raise PermissionDenied("Seu perfil não tem acesso a este documento.")

    if not default_storage.exists(relativo):
        raise Http404("Arquivo não encontrado.")

    tipo, _ = mimetypes.guess_type(destino.name)
    tipo = tipo or "application/octet-stream"

    # Arquivo que o navegador executaria (SVG, HTML) sai como download, nunca
    # renderizado: renderizado, rodaria script na mesma origem do sistema, com
    # a sessao de quem abriu.
    resposta = FileResponse(
        default_storage.open(relativo, "rb"),
        content_type=tipo,
        as_attachment=tipo not in TIPOS_EM_LINHA,
        filename=destino.name,
    )
    # Impede o navegador de adivinhar um tipo diferente do declarado.
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return resposta
