from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from simple_history.models import HistoricalRecords

from core.managers import SoftDeleteManager, SoftDeleteQuerySet
from core.models import Endereco, SoftDeleteModel


class TipoPessoa(models.TextChoices):
    PF = "PF", "Pessoa física"
    PJ = "PJ", "Pessoa jurídica"


class TipoDoacao(models.TextChoices):
    """O que chegou. Em ITEM, a categoria do estoque diz o que e (Alimentos,
    Limpeza...) e a doacao entra no estoque; dinheiro e servico ficam fora."""

    DINHEIRO = "DINHEIRO", "Dinheiro"
    ITEM = "ITEM", "Itens"
    SERVICO = "SERVICO", "Serviço"


# Itens contam so em unidades: e o que o estoque consegue somar e dar baixa.
# Servico nao vai para o estoque e continua podendo ser medido em horas.
UNIDADES_DOACAO = [
    ("unidades", "Unidade"),
    ("horas", "Hora"),
]

UNIDADES_POR_TIPO = {
    TipoDoacao.ITEM: ("unidades",),
    TipoDoacao.SERVICO: ("unidades", "horas"),
}


def rotulo_do_tipo(tipo, categoria) -> str:
    """'Alimentos' para itens, 'Dinheiro' ou 'Serviço' para o resto."""
    if tipo == TipoDoacao.ITEM and categoria is not None:
        return categoria.nome
    return TipoDoacao(tipo).label if tipo in TipoDoacao.values else tipo


class Doador(SoftDeleteModel, Endereco):
    tipo = models.CharField("tipo", max_length=2, choices=TipoPessoa.choices, default=TipoPessoa.PF)
    nome = models.CharField("nome ou razão social", max_length=150)
    cpf_cnpj = models.CharField("CPF ou CNPJ", max_length=14, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    recorrente = models.BooleanField(
        "doador recorrente",
        default=False,
        help_text="Marque se a pessoa ou empresa doa com regularidade.",
    )
    observacoes = models.TextField("observações", blank=True)

    criado_por = models.ForeignKey(
        "accounts.Usuario",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="doadores_cadastrados",
    )

    class Meta:
        verbose_name = "doador"
        verbose_name_plural = "doadores"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    @property
    def documento_formatado(self) -> str:
        numero = "".join(filter(str.isdigit, self.cpf_cnpj))
        if len(numero) == 11:
            return f"{numero[:3]}.{numero[3:6]}.{numero[6:9]}-{numero[9:]}"
        if len(numero) == 14:
            return f"{numero[:2]}.{numero[2:5]}.{numero[5:8]}/{numero[8:12]}-{numero[12:]}"
        return "—"

    @property
    def total_doado(self) -> Decimal:
        """Soma apenas doacoes em dinheiro: 'R$ 500' e '20 kg de arroz' nao
        somam no mesmo total."""
        total = self.doacoes.filter(tipo=TipoDoacao.DINHEIRO, deleted_at__isnull=True).aggregate(
            soma=Sum("valor")
        )["soma"]
        return total or Decimal("0")


class CampanhaQuerySet(SoftDeleteQuerySet):
    def ativas(self):
        """Campanhas que aceitam doacao hoje.

        Espelha a propriedade `esta_ativa` em consulta ao banco: ja comecou,
        ainda nao terminou e nao foi encerrada a mao.
        """
        hoje = timezone.localdate()
        return self.filter(
            models.Q(encerrada_em__isnull=True, data_inicio__lte=hoje)
            & (models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=hoje))
        )


class CampanhaManager(SoftDeleteManager):
    """Manager padrao do core, com o queryset proprio das campanhas."""

    def get_queryset(self):
        return CampanhaQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)

    def ativas(self):
        return self.get_queryset().ativas()


class Campanha(SoftDeleteModel):
    nome = models.CharField("nome", max_length=120)
    descricao = models.TextField("descrição", blank=True)
    data_inicio = models.DateField("início")
    data_fim = models.DateField("término", null=True, blank=True)
    encerrada_em = models.DateTimeField("encerrada em", null=True, blank=True, editable=False)
    meta_valor = models.DecimalField(
        "meta em reais", max_digits=10, decimal_places=2, null=True, blank=True
    )

    objects = CampanhaManager()

    class Meta:
        verbose_name = "campanha"
        verbose_name_plural = "campanhas"
        ordering = ["-data_inicio"]

    def __str__(self) -> str:
        return self.nome

    @property
    def esta_ativa(self) -> bool:
        hoje = timezone.localdate()
        if self.encerrada_em is not None or self.data_inicio > hoje:
            return False
        return self.data_fim is None or self.data_fim >= hoje

    @property
    def arrecadado(self) -> Decimal:
        total = self.doacoes.filter(tipo=TipoDoacao.DINHEIRO, deleted_at__isnull=True).aggregate(
            soma=Sum("valor")
        )["soma"]
        return total or Decimal("0")

    @property
    def percentual_da_meta(self) -> int:
        if not self.meta_valor:
            return 0
        return int(self.arrecadado / self.meta_valor * 100)

    @property
    def metas_com_progresso(self) -> list[dict]:
        metas = []
        if self.meta_valor:
            arrecadado = self.arrecadado
            percentual = int(arrecadado / self.meta_valor * 100)
            metas.append(
                {
                    "tipo": TipoDoacao.DINHEIRO,
                    "rotulo": "Dinheiro",
                    "alvo": self.meta_valor,
                    "recebido": arrecadado,
                    "unidade": "",
                    "percentual": percentual,
                    "progresso": min(percentual, 100),
                }
            )
        totais = {
            (linha["tipo"], linha["categoria"], linha["unidade"]): linha["total"] or 0
            for linha in self.doacoes.filter(deleted_at__isnull=True)
            .exclude(tipo=TipoDoacao.DINHEIRO)
            .values("tipo", "categoria", "unidade")
            .annotate(total=Sum("quantidade"))
        }
        for meta in self.metas_itens.select_related("categoria"):
            recebido = totais.get((meta.tipo, meta.categoria_id, meta.unidade), 0)
            percentual = int(recebido / meta.quantidade * 100)
            metas.append(
                {
                    "tipo": meta.tipo,
                    "rotulo": meta.rotulo,
                    "alvo": meta.quantidade,
                    "recebido": recebido,
                    "unidade": meta.unidade,
                    "percentual": percentual,
                    "progresso": min(percentual, 100),
                }
            )
        return metas

    def clean(self):
        super().clean()
        erros = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "O término não pode ser anterior ao início."
        if self.meta_valor is not None and self.meta_valor <= 0:
            erros["meta_valor"] = "A meta precisa ser maior que zero."
        if erros:
            raise ValidationError(erros)


class MetaItemCampanha(models.Model):
    campanha = models.ForeignKey(Campanha, on_delete=models.CASCADE, related_name="metas_itens")
    tipo = models.CharField(
        "tipo de item",
        max_length=10,
        choices=[opcao for opcao in TipoDoacao.choices if opcao[0] != TipoDoacao.DINHEIRO],
    )
    categoria = models.ForeignKey(
        "estoque.CategoriaItem", null=True, blank=True, on_delete=models.PROTECT,
        related_name="metas_campanha", verbose_name="categoria",
    )
    quantidade = models.PositiveIntegerField("quantidade desejada")
    unidade = models.CharField("unidade", max_length=30, choices=UNIDADES_DOACAO)

    class Meta:
        verbose_name = "meta de item"
        verbose_name_plural = "metas de itens"
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["campanha", "tipo", "categoria", "unidade"],
                name="meta_item_campanha_unica",
            )
        ]

    def __str__(self) -> str:
        return f"{self.quantidade} {self.unidade} de {self.rotulo}"

    @property
    def rotulo(self) -> str:
        return rotulo_do_tipo(self.tipo, self.categoria)

    def clean(self):
        super().clean()
        if self.quantidade is not None and self.quantidade < 1:
            raise ValidationError({"quantidade": "A quantidade precisa ser maior que zero."})
        if self.tipo == TipoDoacao.ITEM and not self.categoria_id:
            raise ValidationError({"tipo": "Escolha a categoria do item."})

        if self.tipo and self.unidade and self.unidade not in UNIDADES_POR_TIPO.get(self.tipo, ()):
            raise ValidationError(
                {"unidade": "Esta unidade não é compatível com o tipo escolhido."}
            )


class Doacao(SoftDeleteModel):
    """Uma doacao recebida.

    `valor` e separado de `quantidade` porque 'R$ 500' e '20 kg de arroz' nao
    cabem no mesmo campo, e o relatorio financeiro precisa somar apenas o
    primeiro.
    """

    doador = models.ForeignKey(
        Doador,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="doacoes",
        help_text="Deixe vazio para doação anônima.",
    )
    campanha = models.ForeignKey(
        Campanha, null=True, blank=True, on_delete=models.SET_NULL, related_name="doacoes"
    )
    tipo = models.CharField("tipo", max_length=10, choices=TipoDoacao.choices)
    categoria = models.ForeignKey(
        "estoque.CategoriaItem", null=True, blank=True, on_delete=models.PROTECT,
        related_name="doacoes", verbose_name="categoria no estoque",
    )
    descricao = models.CharField(
        "descrição", max_length=200, blank=True, help_text="Ex.: Arroz 5kg, cobertores"
    )
    quantidade = models.DecimalField(
        "quantidade", max_digits=10, decimal_places=2, null=True, blank=True
    )
    unidade = models.CharField(
        "unidade", max_length=30, blank=True, help_text="Ex.: pacotes, caixas, peças"
    )
    valor = models.DecimalField(
        "valor em reais", max_digits=10, decimal_places=2, null=True, blank=True
    )
    data_recebimento = models.DateField("data de recebimento", default=date.today)
    recebido_por = models.ForeignKey(
        "accounts.Usuario",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="doacoes_recebidas",
    )
    recibo_emitido = models.BooleanField("recibo emitido", default=False)
    observacoes = models.TextField("observações", blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "doação"
        verbose_name_plural = "doações"
        ordering = ["-data_recebimento", "-criado_em"]
        indexes = [models.Index(fields=["-data_recebimento"])]

    def __str__(self) -> str:
        quem = self.doador.nome if self.doador else "Anônimo"
        return f"{self.tipo_rotulo} — {quem} ({self.data_recebimento:%d/%m/%Y})"

    @property
    def tipo_rotulo(self) -> str:
        return rotulo_do_tipo(self.tipo, self.categoria)

    def clean(self):
        super().clean()
        erros = {}

        if self.tipo == TipoDoacao.DINHEIRO:
            if self.valor is None:
                erros["valor"] = "Informe o valor da doação em dinheiro."
            elif self.valor <= 0:
                erros["valor"] = "O valor precisa ser maior que zero."
        elif self.tipo:
            if self.tipo == TipoDoacao.ITEM and not self.categoria_id:
                erros["tipo"] = "Escolha a categoria do item no estoque."
            if not self.descricao.strip():
                erros["descricao"] = "Descreva o que foi doado."
            if self.quantidade is None:
                erros["quantidade"] = "Informe a quantidade doada."
            elif self.quantidade <= 0:
                erros["quantidade"] = "A quantidade precisa ser maior que zero."
            elif self.quantidade % 1 != 0:
                erros["quantidade"] = "A quantidade precisa ser um número inteiro."
            if not self.unidade:
                erros["unidade"] = "Selecione a unidade da doação."
            elif self.unidade not in UNIDADES_POR_TIPO.get(self.tipo, ()):
                erros["unidade"] = "Esta unidade não é compatível com o tipo escolhido."

        if self.valor is not None and self.valor <= 0:
            erros["valor"] = "O valor precisa ser maior que zero."
        if self.data_recebimento and self.data_recebimento > timezone.localdate():
            erros["data_recebimento"] = "A data de recebimento não pode ser no futuro."

        if erros:
            raise ValidationError(erros)

    @property
    def descricao_quantidade(self) -> str:
        if self.tipo == TipoDoacao.DINHEIRO and self.valor is not None:
            return f"R$ {self.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if self.quantidade is not None:
            quantidade = Decimal(self.quantidade).normalize()
            return f"{quantidade:f} {self.unidade}".strip()
        return self.descricao or "—"
