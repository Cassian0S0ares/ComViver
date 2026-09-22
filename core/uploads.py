import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

TAMANHO_MAXIMO_MB = 10

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp"}
EXTENSOES_DOCUMENTO = EXTENSOES_IMAGEM | {".pdf", ".odt", ".docx"}


@deconstructible
class CaminhoOpaco:
    """`upload_to` que descarta o nome original do arquivo.

    O nome enviado vira parte da URL do arquivo. Um arquivo chamado
    'ana-clara-souza.jpg' identificaria a crianca sem que ninguem abrisse a
    ficha — exatamente o que o art. 143 do ECA veda. Alem disso, nome original
    permite colisao e carrega caracteres que o sistema de arquivos rejeita.

    E uma classe, e nao uma funcao interna, porque o Django precisa gravar o
    `upload_to` na migration.
    """

    def __init__(self, prefixo: str):
        self.prefixo = prefixo

    def __call__(self, instance, nome_original: str) -> str:
        extensao = Path(nome_original).suffix.lower()
        if extensao not in EXTENSOES_DOCUMENTO:
            extensao = ".bin"
        return f"{self.prefixo}/{uuid.uuid4().hex}{extensao}"

    def __eq__(self, outro):
        return isinstance(outro, CaminhoOpaco) and self.prefixo == outro.prefixo


def caminho_opaco(prefixo: str) -> CaminhoOpaco:
    return CaminhoOpaco(prefixo)


def _validar(arquivo, permitidas: set[str]):
    extensao = Path(arquivo.name).suffix.lower()
    if extensao not in permitidas:
        aceitas = ", ".join(sorted(permitidas))
        raise ValidationError(
            f"O formato {extensao or 'desconhecido'} não é aceito. Envie um arquivo {aceitas}."
        )

    if arquivo.size > TAMANHO_MAXIMO_MB * 1024 * 1024:
        raise ValidationError(
            f"O arquivo tem {arquivo.size / 1024 / 1024:.1f} MB. O limite é {TAMANHO_MAXIMO_MB} MB."
        )


def validar_imagem(arquivo):
    """SVG fica de fora de proposito: e XML executavel, e um SVG aceito como
    foto viraria script rodando na origem do sistema."""
    _validar(arquivo, EXTENSOES_IMAGEM)


def validar_documento(arquivo):
    _validar(arquivo, EXTENSOES_DOCUMENTO)
