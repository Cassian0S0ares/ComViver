from datetime import date

from django.db import models
from simple_history.models import HistoricalRecords

from core.models import Endereco, SoftDeleteModel
from core.uploads import caminho_opaco, validar_imagem


class StatusAcolhido(models.TextChoices):
    ACOLHIDO = "ACOLHIDO", "Acolhido"
    DESLIGADO = "DESLIGADO", "Desligado"


class Sexo(models.TextChoices):
    FEMININO = "F", "Feminino"
    MASCULINO = "M", "Masculino"
    OUTRO = "O", "Outro"


class Acolhido(SoftDeleteModel):
    """Crianca ou adolescente em acolhimento institucional.

    Dado sensivel de menor. O acesso e recortado por perfil e toda leitura da
    ficha e registrada em accounts.LogAcessoFicha (art. 143 do ECA).
    """

    nome = models.CharField("nome completo", max_length=150)
    nome_social = models.CharField(
        "nome social",
        max_length=150,
        blank=True,
        help_text="Preencha se a pessoa é chamada por outro nome.",
    )
    nascimento = models.DateField("data de nascimento")
    sexo = models.CharField("sexo", max_length=1, choices=Sexo.choices)
    naturalidade = models.CharField("naturalidade", max_length=100, blank=True)
    foto = models.ImageField(
        "foto",
        upload_to=caminho_opaco("acolhidos/fotos"),
        validators=[validar_imagem],
        blank=True,
    )

    cpf = models.CharField("CPF", max_length=11, blank=True, unique=True, null=True)
    rg = models.CharField("RG", max_length=20, blank=True)
    certidao_nascimento = models.CharField("certidão de nascimento", max_length=50, blank=True)
    cartao_sus = models.CharField("cartão SUS", max_length=20, blank=True)

    status = models.CharField(
        "situação",
        max_length=10,
        choices=StatusAcolhido.choices,
        default=StatusAcolhido.ACOLHIDO,
    )
    observacoes = models.TextField("observações", blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "acolhido"
        verbose_name_plural = "acolhidos"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome_exibicao

    def save(self, *args, **kwargs):
        # CPF vazio precisa virar NULL: unique=True trata "" como valor repetido,
        # e crianca acolhida frequentemente chega sem documento.
        if not self.cpf:
            self.cpf = None
        super().save(*args, **kwargs)

    @property
    def nome_exibicao(self) -> str:
        return self.nome_social or self.nome

    @property
    def idade(self) -> int:
        hoje = date.today()
        return (
            hoje.year
            - self.nascimento.year
            - ((hoje.month, hoje.day) < (self.nascimento.month, self.nascimento.day))
        )

    @property
    def tempo_acolhimento(self) -> int | None:
        """Dias desde a entrada. None quando a ficha ainda nao foi preenchida."""
        ficha = getattr(self, "ficha", None)
        if ficha is None or ficha.data_entrada is None:
            return None
        fim = ficha.data_desligamento or date.today()
        return (fim - ficha.data_entrada).days


class Responsavel(SoftDeleteModel, Endereco):
    """Familiar ou responsavel legal. Vive fora da instituicao."""

    nome = models.CharField("nome completo", max_length=150)
    cpf = models.CharField("CPF", max_length=11, blank=True)
    rg = models.CharField("RG", max_length=20, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "responsável"
        verbose_name_plural = "responsáveis"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class VinculoFamiliar(SoftDeleteModel):
    """Liga acolhido e responsavel, com os atributos do vinculo.

    E uma relacao muitos-para-muitos com dados proprios: um responsavel pode
    ter vinculo com dois irmaos acolhidos, e um acolhido tem varios
    responsaveis com papeis distintos.
    """

    acolhido = models.ForeignKey(Acolhido, on_delete=models.CASCADE, related_name="vinculos")
    responsavel = models.ForeignKey(Responsavel, on_delete=models.CASCADE, related_name="vinculos")
    parentesco = models.CharField("parentesco", max_length=50)
    e_guardiao = models.BooleanField("é guardião legal", default=False)
    autorizado_visita = models.BooleanField("autorizado a visitar", default=True)
    autorizado_retirar = models.BooleanField("autorizado a retirar", default=False)
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "vínculo familiar"
        verbose_name_plural = "vínculos familiares"
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["acolhido", "responsavel"], name="vinculo_unico_por_par"
            )
        ]

    def __str__(self) -> str:
        return f"{self.responsavel.nome} — {self.parentesco} de {self.acolhido.nome_exibicao}"
