import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.db import IntegrityError, transaction
from django.urls import reverse

from core.models import ArquivoEnviado


class BancoDeDadosStorage(Storage):
    """Grava uploads no PostgreSQL e ainda le arquivos locais antigos."""

    def _legado(self):
        return FileSystemStorage(location=settings.MEDIA_ROOT)

    def _open(self, name, mode="rb"):
        conteudo = ArquivoEnviado.objects.filter(nome=name).values_list("conteudo", flat=True).first()
        if conteudo is not None:
            return ContentFile(bytes(conteudo), name=name)
        return self._legado().open(name, mode)

    def _save(self, name, content):
        dados = b"".join(content.chunks())
        try:
            with transaction.atomic():
                ArquivoEnviado.objects.create(nome=name, conteudo=dados, tamanho=len(dados))
        except IntegrityError:
            # Outro upload obteve o mesmo nome entre exists() e create().
            return self.save(name, ContentFile(dados))
        return name

    def exists(self, name):
        return ArquivoEnviado.objects.filter(nome=name).exists() or self._legado().exists(name)

    def size(self, name):
        tamanho = ArquivoEnviado.objects.filter(nome=name).values_list("tamanho", flat=True).first()
        return tamanho if tamanho is not None else self._legado().size(name)

    def delete(self, name):
        if name:
            if not ArquivoEnviado.objects.filter(nome=name).delete()[0]:
                self._legado().delete(name)

    def url(self, name):
        return reverse("media_protegida", args=[name])


class RascunhoAcolhimentoStorage(BancoDeDadosStorage):
    """Rascunhos do assistente no banco, com nomes impossíveis de adivinhar."""

    @property
    def location(self):
        """Pasta usada apenas por rascunhos iniciados antes desta mudança."""
        return str(settings.ASSISTENTE_TEMP_DIR)

    def _legado(self):
        # Mantém rascunhos iniciados antes da troca do armazenamento.
        return FileSystemStorage(location=settings.ASSISTENTE_TEMP_DIR)

    def get_available_name(self, name, max_length=None):
        extensao = Path(name).suffix.lower()
        if extensao not in {".jpg", ".jpeg", ".png", ".webp"}:
            extensao = ".bin"
        nome_opaco = f"_rascunhos/acolhidos/{uuid.uuid4().hex}{extensao}"
        return super().get_available_name(nome_opaco, max_length=max_length)
