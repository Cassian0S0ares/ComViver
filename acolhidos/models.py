from datetime import date

from django.db import models
from simple_history.models import HistoricalRecords

from core.managers import SoftDeleteManager
from core.models import Endereco, SoftDeleteModel
from core.uploads import caminho_opaco, validar_documento, validar_imagem


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


class MedicacaoEmVigorManager(SoftDeleteManager):
    """Medicacao valida hoje: ja comecou, ainda nao terminou e nao foi excluida."""

    def get_queryset(self):
        hoje = date.today()
        return (
            super()
            .get_queryset()
            .filter(inicio__lte=hoje)
            .filter(models.Q(fim__isnull=True) | models.Q(fim__gte=hoje))
        )


class Destino(models.TextChoices):
    REINTEGRACAO = "REINTEGRACAO", "Reintegração familiar"
    ADOCAO = "ADOCAO", "Adoção"
    MAIORIDADE = "MAIORIDADE", "Maioridade"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferência para outra instituição"
    OUTRO = "OUTRO", "Outro"


class FichaAcolhimento(SoftDeleteModel):
    """Circunstancias do acolhimento e situacao juridica.

    Conteudo vedado ao perfil Operacional (art. 143 do ECA).
    """

    acolhido = models.OneToOneField(Acolhido, on_delete=models.CASCADE, related_name="ficha")
    data_entrada = models.DateField("data de entrada")
    motivo = models.TextField("motivo do acolhimento", blank=True)
    orgao_requisitante = models.CharField("órgão requisitante", max_length=150, blank=True)
    processo_numero = models.CharField("número do processo", max_length=50, blank=True)
    vara = models.CharField("vara", max_length=100, blank=True)
    medida_protetiva = models.TextField("medida protetiva", blank=True)

    data_desligamento = models.DateField("data de desligamento", null=True, blank=True)
    destino = models.CharField(
        "destino após o desligamento", max_length=150, choices=Destino.choices, blank=True
    )
    observacao_desligamento = models.TextField("observação do desligamento", blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "ficha de acolhimento"
        verbose_name_plural = "fichas de acolhimento"

    def __str__(self) -> str:
        return f"Ficha de {self.acolhido.nome_exibicao}"

    def esta_completa(self) -> bool:
        """Campos minimos para a ficha servir a prestacao de contas."""
        return bool(self.motivo and self.orgao_requisitante and self.processo_numero)


class DadosSaude(SoftDeleteModel):
    acolhido = models.OneToOneField(Acolhido, on_delete=models.CASCADE, related_name="saude")
    tipo_sanguineo = models.CharField("tipo sanguíneo", max_length=3, blank=True)
    alergias = models.TextField("alergias", blank=True)
    condicoes = models.TextField("condições de saúde", blank=True)
    plano_saude = models.CharField("plano de saúde", max_length=100, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "dados de saúde"
        verbose_name_plural = "dados de saúde"

    def __str__(self) -> str:
        return f"Saúde de {self.acolhido.nome_exibicao}"


class Medicacao(SoftDeleteModel):
    """Medicamento em uso.

    Unico dado de saude visivel ao perfil Operacional: sem ele, quem esta na
    casa no turno da tarde nao sabe o que administrar.
    """

    acolhido = models.ForeignKey(Acolhido, on_delete=models.CASCADE, related_name="medicacoes")
    nome = models.CharField("medicamento", max_length=120)
    dosagem = models.CharField("dosagem", max_length=60)
    frequencia = models.CharField("frequência", max_length=80, help_text="Ex.: 8h e 20h")
    inicio = models.DateField("início")
    fim = models.DateField("fim", null=True, blank=True, help_text="Vazio = uso contínuo")
    observacoes = models.TextField("observações", blank=True)

    # `objects` continua sendo o manager de exclusao logica herdado, e
    # `em_vigor` tambem ignora os excluidos: remedio suspenso e apagado nao
    # pode seguir na lista de quem administra.
    em_vigor = MedicacaoEmVigorManager()

    class Meta:
        verbose_name = "medicação"
        verbose_name_plural = "medicações"
        ordering = ["nome"]

    def __str__(self) -> str:
        return f"{self.nome} {self.dosagem}"


class Turno(models.TextChoices):
    MANHA = "MANHA", "Manhã"
    TARDE = "TARDE", "Tarde"
    NOITE = "NOITE", "Noite"


class Escolaridade(SoftDeleteModel):
    acolhido = models.ForeignKey(Acolhido, on_delete=models.CASCADE, related_name="escolaridades")
    escola = models.CharField("escola", max_length=150)
    serie = models.CharField("série", max_length=50)
    turno = models.CharField("turno", max_length=10, choices=Turno.choices, blank=True)
    ano_letivo = models.PositiveIntegerField("ano letivo")

    class Meta:
        verbose_name = "escolaridade"
        verbose_name_plural = "escolaridades"
        ordering = ["-ano_letivo"]

    def __str__(self) -> str:
        return f"{self.serie} — {self.escola} ({self.ano_letivo})"


class DocumentoAcolhido(SoftDeleteModel):
    acolhido = models.ForeignKey(Acolhido, on_delete=models.CASCADE, related_name="documentos")
    arquivo = models.FileField(
        "arquivo",
        upload_to=caminho_opaco("acolhidos/documentos"),
        validators=[validar_documento],
    )
    tipo = models.CharField("tipo", max_length=80)
    descricao = models.CharField("descrição", max_length=200, blank=True)

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"

    def __str__(self) -> str:
        return f"{self.tipo} — {self.acolhido.nome_exibicao}"


class Consentimento(SoftDeleteModel):
    """Termo de consentimento do responsavel (art. 14 da LGPD).

    Tratamento de dado de crianca exige consentimento especifico de quem
    responde por ela, com finalidade declarada.
    """

    acolhido = models.OneToOneField(
        Acolhido, on_delete=models.CASCADE, related_name="consentimento"
    )
    responsavel = models.ForeignKey(
        Responsavel, on_delete=models.PROTECT, related_name="consentimentos"
    )
    data_assinatura = models.DateField("data da assinatura")
    finalidade = models.TextField(
        "finalidade declarada",
        default="Registro administrativo do acolhimento e prestação de contas "
        "aos órgãos de controle.",
    )
    termo_assinado = models.FileField(
        "termo assinado",
        upload_to=caminho_opaco("acolhidos/consentimentos"),
        validators=[validar_documento],
        blank=True,
    )

    class Meta:
        verbose_name = "consentimento"
        verbose_name_plural = "consentimentos"

    def __str__(self) -> str:
        return f"Consentimento de {self.acolhido.nome_exibicao}"
