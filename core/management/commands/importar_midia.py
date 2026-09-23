from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models

from core.models import ArquivoEnviado


class Command(BaseCommand):
    help = "Importa para o banco os uploads antigos ainda guardados em media/."

    def handle(self, *args, **options):
        raiz = Path(settings.MEDIA_ROOT).resolve()
        nomes = set()
        for model in apps.get_models():
            for campo in model._meta.local_fields:
                if isinstance(campo, models.FileField):
                    nomes.update(
                        nome
                        for nome in model._base_manager.values_list(campo.attname, flat=True).iterator()
                        if nome
                    )

        importados = 0
        ausentes = 0
        for nome in sorted(nomes):
            if ArquivoEnviado.objects.filter(nome=nome).exists():
                continue
            caminho = (raiz / nome).resolve()
            if not caminho.is_relative_to(raiz) or not caminho.is_file():
                ausentes += 1
                self.stderr.write(f"Arquivo local ausente: {nome}")
                continue
            dados = caminho.read_bytes()
            _, criado = ArquivoEnviado.objects.get_or_create(
                nome=nome,
                defaults={"conteudo": dados, "tamanho": len(dados)},
            )
            importados += criado

        self.stdout.write(
            self.style.SUCCESS(
                f"{importados} arquivo(s) importado(s); {ausentes} arquivo(s) ausente(s)."
            )
        )
