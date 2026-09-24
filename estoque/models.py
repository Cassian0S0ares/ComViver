from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from core.models import SoftDeleteModel, TimeStampedModel


class CategoriaItem(SoftDeleteModel):
    """Tipo de item do estoque: Alimentos, Higiene, Limpeza..."""

    nome = models.CharField("nome", max_length=60)
    tem_validade = models.BooleanField(
        "tem data de validade", default=False,
        help_text="Marque para alimentos e outros itens que vencem.",
    )

    class Meta:
        verbose_name = "categoria de item"
        verbose_name_plural = "categorias de itens"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(Lower("nome"), name="categoria_item_nome_unico"),
        ]

    def __str__(self) -> str:
        return self.nome


class ItemEstoque(SoftDeleteModel):
    """O que se guarda: 'Arroz 5kg' dentro de Alimentos. A quantidade vem dos lotes."""

    categoria = models.ForeignKey(
        CategoriaItem, on_delete=models.PROTECT, related_name="itens", verbose_name="categoria"
    )
    nome = models.CharField("nome", max_length=120)

    class Meta:
        verbose_name = "item do estoque"
        verbose_name_plural = "itens do estoque"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                "categoria", Lower("nome"), name="item_estoque_nome_unico_na_categoria"
            ),
        ]

    def __str__(self) -> str:
        return self.nome


class LoteEstoque(TimeStampedModel):
    """Uma entrada de itens. Cada lote tem a propria validade e o proprio saldo:
    o arroz que chegou hoje vence depois do que chegou no mes passado."""

    item = models.ForeignKey(ItemEstoque, on_delete=models.PROTECT, related_name="lotes")
    quantidade_inicial = models.PositiveIntegerField("quantidade recebida")
    saldo = models.PositiveIntegerField("quantidade disponível")
    validade = models.DateField("validade", null=True, blank=True)
    doacao = models.OneToOneField(
        "doacoes.Doacao", null=True, blank=True, on_delete=models.PROTECT,
        related_name="lote_estoque",
    )

    class Meta:
        verbose_name = "lote do estoque"
        verbose_name_plural = "lotes do estoque"
        ordering = [models.F("validade").asc(nulls_last=True), "criado_em", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(saldo__lte=models.F("quantidade_inicial")),
                name="lote_saldo_nao_passa_do_recebido",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.saldo}/{self.quantidade_inicial} {self.item}"

    @property
    def consumido(self) -> int:
        return self.quantidade_inicial - self.saldo

    def clean(self):
        super().clean()
        if self.quantidade_inicial is not None and self.quantidade_inicial < 1:
            raise ValidationError({"quantidade_inicial": "A quantidade precisa ser maior que zero."})


class TipoMovimentacao(models.TextChoices):
    ENTRADA = "ENTRADA", "Entrada"
    SAIDA = "SAIDA", "Saída"
    AJUSTE = "AJUSTE", "Ajuste"


class MovimentacaoEstoque(models.Model):
    """Registro de quem colocou ou tirou o que, e quando. Nunca e editado."""

    item = models.ForeignKey(ItemEstoque, on_delete=models.PROTECT, related_name="movimentacoes")
    lote = models.ForeignKey(
        LoteEstoque, null=True, blank=True, on_delete=models.PROTECT, related_name="movimentacoes"
    )
    tipo = models.CharField("tipo", max_length=10, choices=TipoMovimentacao.choices)
    quantidade = models.IntegerField("quantidade")
    observacao = models.CharField("observação", max_length=200, blank=True)
    usuario = models.ForeignKey(
        "accounts.Usuario", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField("registrado em", auto_now_add=True)

    class Meta:
        verbose_name = "movimentação do estoque"
        verbose_name_plural = "movimentações do estoque"
        ordering = ["-criado_em", "-pk"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} de {self.quantidade} {self.item}"
