from django.conf import settings
from django.db import models
from django.utils import timezone

from core.managers import SoftDeleteManager, TodosManager


class TimeStampedModel(models.Model):
    """Registra quando o objeto foi criado e alterado pela ultima vez."""

    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    """Exclusao logica.

    Prestacao de contas e historico de acolhimento nao podem ter lacuna, e
    usuario leigo aciona exclusao por engano. A linha permanece no banco.
    """

    deleted_at = models.DateTimeField("excluido em", null=True, blank=True, editable=False)

    objects = SoftDeleteManager()
    todos = TodosManager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restaurar(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    @property
    def excluido(self) -> bool:
        return self.deleted_at is not None


class Endereco(models.Model):
    """Campos de endereco, reaproveitados por acolhidos, doadores e voluntarios."""

    UF_CHOICES = [
        ("AC", "Acre"),
        ("AL", "Alagoas"),
        ("AP", "Amapá"),
        ("AM", "Amazonas"),
        ("BA", "Bahia"),
        ("CE", "Ceará"),
        ("DF", "Distrito Federal"),
        ("ES", "Espírito Santo"),
        ("GO", "Goiás"),
        ("MA", "Maranhão"),
        ("MT", "Mato Grosso"),
        ("MS", "Mato Grosso do Sul"),
        ("MG", "Minas Gerais"),
        ("PA", "Pará"),
        ("PB", "Paraíba"),
        ("PR", "Paraná"),
        ("PE", "Pernambuco"),
        ("PI", "Piauí"),
        ("RJ", "Rio de Janeiro"),
        ("RN", "Rio Grande do Norte"),
        ("RS", "Rio Grande do Sul"),
        ("RO", "Rondônia"),
        ("RR", "Roraima"),
        ("SC", "Santa Catarina"),
        ("SP", "São Paulo"),
        ("SE", "Sergipe"),
        ("TO", "Tocantins"),
    ]

    cep = models.CharField("CEP", max_length=9, blank=True)
    logradouro = models.CharField("logradouro", max_length=150, blank=True)
    numero = models.CharField("número", max_length=10, blank=True)
    complemento = models.CharField("complemento", max_length=50, blank=True)
    bairro = models.CharField("bairro", max_length=80, blank=True)
    cidade = models.CharField("cidade", max_length=80, blank=True)
    uf = models.CharField("UF", max_length=2, choices=UF_CHOICES, blank=True)

    class Meta:
        abstract = True

    @property
    def endereco_formatado(self) -> str:
        if not self.logradouro:
            return ""
        return f"{self.logradouro}, {self.numero} - {self.bairro}, {self.cidade}/{self.uf}"
