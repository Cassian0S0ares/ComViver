from django.db import models

from core.models import Endereco, SoftDeleteModel, TimeStampedModel


class ModeloDatado(TimeStampedModel):
    """Model concreto usado apenas para testar TimeStampedModel."""

    nome = models.CharField(max_length=50)


class ModeloExcluivel(SoftDeleteModel):
    """Model concreto usado apenas para testar SoftDeleteModel."""

    nome = models.CharField(max_length=50)


class ModeloComEndereco(Endereco):
    """Model concreto usado apenas para testar Endereco."""

    nome = models.CharField(max_length=50)


class ModeloPesquisavel(SoftDeleteModel):
    """Model concreto para exercitar as views base do core."""

    nome = models.CharField(max_length=80)
    apelido = models.CharField(max_length=80, blank=True)
    segredo = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["nome"]

    def get_absolute_url(self):
        return "/lista/"
