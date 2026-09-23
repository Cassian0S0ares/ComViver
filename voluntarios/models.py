from datetime import date

from django.db import models

from core.models import Endereco, SoftDeleteModel
from core.uploads import caminho_opaco, validar_documento


class StatusVoluntario(models.TextChoices):
    ATIVO = "ATIVO", "Ativo"
    INATIVO = "INATIVO", "Inativo"


class DiaSemana(models.IntegerChoices):
    SEGUNDA = 0, "Segunda-feira"
    TERCA = 1, "Terça-feira"
    QUARTA = 2, "Quarta-feira"
    QUINTA = 3, "Quinta-feira"
    SEXTA = 4, "Sexta-feira"
    SABADO = 5, "Sábado"
    DOMINGO = 6, "Domingo"


class Turno(models.TextChoices):
    MANHA = "MANHA", "Manhã"
    TARDE = "TARDE", "Tarde"
    NOITE = "NOITE", "Noite"


ABREVIACAO_DIA = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}


class Funcao(SoftDeleteModel):
    """Tabela de apoio: cozinha, reforco escolar, recreacao, manutencao."""

    nome = models.CharField("nome", max_length=80, unique=True)
    descricao = models.TextField("descrição", blank=True)

    class Meta:
        verbose_name = "função"
        verbose_name_plural = "funções"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Voluntario(SoftDeleteModel, Endereco):
    nome = models.CharField("nome completo", max_length=150)
    cpf = models.CharField("CPF", max_length=11, blank=True, unique=True, null=True)
    rg = models.CharField("RG", max_length=20, blank=True)
    nascimento = models.DateField("data de nascimento", null=True, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)

    funcoes = models.ManyToManyField(
        Funcao, verbose_name="funções", blank=True, related_name="voluntarios"
    )
    data_cadastro = models.DateField("data de cadastro", default=date.today)
    status = models.CharField(
        "situação",
        max_length=10,
        choices=StatusVoluntario.choices,
        default=StatusVoluntario.ATIVO,
    )
    observacoes = models.TextField("observações", blank=True)

    criado_por = models.ForeignKey(
        "accounts.Usuario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voluntarios_cadastrados",
    )

    class Meta:
        verbose_name = "voluntário"
        verbose_name_plural = "voluntários"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs):
        if not self.cpf:
            self.cpf = None
        super().save(*args, **kwargs)

    @property
    def idade(self) -> int | None:
        if not self.nascimento:
            return None
        hoje = date.today()
        return (
            hoje.year
            - self.nascimento.year
            - ((hoje.month, hoje.day) < (self.nascimento.month, self.nascimento.day))
        )

    def esta_disponivel(self, dia_semana: int, turno: str) -> bool:
        return self.disponibilidades.filter(dia_semana=dia_semana, turno=turno).exists()

    @property
    def resumo_disponibilidade(self) -> str:
        """Ex.: 'Seg: manhã, tarde · Qua: manhã'.

        Aparece na listagem e na lista de sugestoes ao montar escala — o
        coordenador precisa ver isso sem abrir o cadastro.
        """
        por_dia: dict[int, list[str]] = {}
        for item in self.disponibilidades.order_by("dia_semana", "turno"):
            por_dia.setdefault(item.dia_semana, []).append(item.get_turno_display().lower())
        if not por_dia:
            return "Não informada"
        return " · ".join(
            f"{ABREVIACAO_DIA[dia]}: {', '.join(turnos)}" for dia, turnos in sorted(por_dia.items())
        )


class Disponibilidade(models.Model):
    voluntario = models.ForeignKey(
        Voluntario, on_delete=models.CASCADE, related_name="disponibilidades"
    )
    dia_semana = models.IntegerField("dia da semana", choices=DiaSemana.choices)
    turno = models.CharField("turno", max_length=6, choices=Turno.choices)

    class Meta:
        verbose_name = "disponibilidade"
        verbose_name_plural = "disponibilidades"
        ordering = ["dia_semana", "turno"]
        constraints = [
            models.UniqueConstraint(
                fields=["voluntario", "dia_semana", "turno"],
                name="disponibilidade_unica",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_dia_semana_display()} — {self.get_turno_display()}"


class DocumentoVoluntario(SoftDeleteModel):
    voluntario = models.ForeignKey(
        Voluntario, on_delete=models.CASCADE, related_name="documentos"
    )
    arquivo = models.FileField(
        "arquivo",
        upload_to=caminho_opaco("voluntarios/documentos"),
        validators=[validar_documento],
    )
    tipo = models.CharField("tipo", max_length=80)

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"

    def __str__(self) -> str:
        return f"{self.tipo} — {self.voluntario.nome}"
