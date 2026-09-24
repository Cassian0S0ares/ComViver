from datetime import time

from django.core.exceptions import ValidationError
from django.db import models

from core.models import SoftDeleteModel


class StatusEscala(models.TextChoices):
    RASCUNHO = "RASCUNHO", "Rascunho"
    PUBLICADA = "PUBLICADA", "Publicada"


class StatusAlocacao(models.TextChoices):
    PREVISTO = "PREVISTO", "Previsto"
    CONFIRMADO = "CONFIRMADO", "Compareceu"
    FALTOU = "FALTOU", "Faltou"


class Atividade(SoftDeleteModel):
    """Tabela de apoio: acompanhamento escolar, recreacao, cozinha, portaria."""

    nome = models.CharField("nome", max_length=100, unique=True)
    descricao = models.TextField("descrição", blank=True)
    ativa = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "atividade"
        verbose_name_plural = "atividades"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Escala(SoftDeleteModel):
    """Conjunto de turnos de um periodo.

    Em RASCUNHO pode ser remontada livremente; ao ser publicada, vira registro.
    """

    titulo = models.CharField("título", max_length=120)
    data_inicio = models.DateField("início")
    data_fim = models.DateField("término")
    status = models.CharField(
        "situação", max_length=10, choices=StatusEscala.choices,
        default=StatusEscala.RASCUNHO,
    )
    observacoes = models.TextField("observações", blank=True)

    criado_por = models.ForeignKey(
        "accounts.Usuario", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="escalas_criadas",
    )

    class Meta:
        verbose_name = "escala"
        verbose_name_plural = "escalas"
        ordering = ["-data_inicio"]

    def __str__(self) -> str:
        return self.titulo

    def clean(self):
        super().clean()
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError(
                {"data_fim": "O término não pode ser anterior ao início."}
            )

    @property
    def total_turnos(self) -> int:
        return self.turnos.count()

    @property
    def turnos_descobertos(self) -> int:
        return sum(1 for turno in self.turnos.all() if turno.esta_descoberto)

    @property
    def esta_publicada(self) -> bool:
        return self.status == StatusEscala.PUBLICADA


class Turno(SoftDeleteModel):
    escala = models.ForeignKey(Escala, on_delete=models.CASCADE, related_name="turnos")
    data = models.DateField("data")
    hora_inicio = models.TimeField("início")
    hora_fim = models.TimeField("término")
    atividade = models.ForeignKey(
        Atividade, on_delete=models.PROTECT, related_name="turnos"
    )
    vagas = models.PositiveSmallIntegerField("vagas", default=1)
    observacoes = models.CharField("observações", max_length=200, blank=True)

    class Meta:
        verbose_name = "turno"
        verbose_name_plural = "turnos"
        ordering = ["data", "hora_inicio"]

    def __str__(self) -> str:
        return (
            f"{self.data:%d/%m} {self.hora_inicio:%H:%M}–{self.hora_fim:%H:%M} "
            f"· {self.atividade.nome}"
        )

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fim and self.hora_fim <= self.hora_inicio:
            raise ValidationError(
                {"hora_fim": "O término precisa ser depois do início."}
            )

    def sobrepoe(self, outro: "Turno") -> bool:
        """Dois turnos no mesmo dia com intersecao de horario.

        Encostar nao e sobrepor: terminar as 12h e comecar as 12h e troca de
        turno, situacao normal.
        """
        if self.data != outro.data:
            return False
        return self.hora_inicio < outro.hora_fim and outro.hora_inicio < self.hora_fim

    def pode_ser_gerenciado_por(self, usuario) -> bool:
        """Editar e excluir cabem a quem criou o turno ou a um administrador."""
        return usuario.e_admin or (
            self.criado_por_id is not None and self.criado_por_id == usuario.pk
        )

    @property
    def duracao(self) -> str:
        minutos = (self.hora_fim.hour * 60 + self.hora_fim.minute
                   - self.hora_inicio.hour * 60 - self.hora_inicio.minute)
        if self.hora_fim.minute == 59:  # 23:59 marca o fim do dia
            minutos += 1
        horas, resto = divmod(minutos, 60)
        return f"{horas}h{resto:02d}" if horas and resto else f"{horas}h" if horas else f"{resto} min"

    @property
    def percentual_ocupado(self) -> int:
        return min(100, round(100 * self.vagas_ocupadas / self.vagas)) if self.vagas else 100

    @property
    def vagas_ocupadas(self) -> int:
        return self.alocacoes.count()

    @property
    def vagas_livres(self) -> int:
        return max(0, self.vagas - self.vagas_ocupadas)

    @property
    def esta_descoberto(self) -> bool:
        """Qualquer vaga em aberto conta: duas vagas com uma pessoa e um buraco."""
        return self.vagas_ocupadas < self.vagas

    @property
    def turno_do_dia(self) -> str:
        """Classifica pela hora de inicio, para casar com a disponibilidade
        declarada pelo voluntario."""
        if self.hora_inicio < time(12, 0):
            return "MANHA"
        if self.hora_inicio < time(18, 0):
            return "TARDE"
        return "NOITE"


class Alocacao(SoftDeleteModel):
    """Um voluntário ou usuário responsável por um turno."""

    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name="alocacoes")
    voluntario = models.ForeignKey(
        "voluntarios.Voluntario", on_delete=models.CASCADE, related_name="alocacoes",
        null=True, blank=True,
    )
    usuario = models.ForeignKey(
        "accounts.Usuario", on_delete=models.PROTECT, related_name="alocacoes",
        null=True, blank=True,
    )
    status = models.CharField(
        "situação", max_length=10, choices=StatusAlocacao.choices,
        default=StatusAlocacao.PREVISTO,
    )
    observacao = models.CharField("observação", max_length=200, blank=True)

    class Meta:
        verbose_name = "alocação"
        verbose_name_plural = "alocações"
        constraints = [
            models.UniqueConstraint(
                fields=["turno", "voluntario"], name="alocacao_unica_por_turno"
            ),
            models.UniqueConstraint(
                fields=["turno", "usuario"], name="alocacao_usuario_unica_por_turno"
            ),
            models.CheckConstraint(
                condition=(models.Q(voluntario__isnull=False, usuario__isnull=True)
                           | models.Q(voluntario__isnull=True, usuario__isnull=False)),
                name="alocacao_exatamente_um_responsavel",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nome_responsavel} — {self.turno}"

    @property
    def nome_responsavel(self):
        if self.usuario_id:
            return self.usuario.get_full_name() or self.usuario.username
        return self.voluntario.nome if self.voluntario_id else "Sem responsável"

    def clean(self):
        """Recusa alocar a mesma pessoa em turnos que se sobrepoem.

        A regra vive aqui, e nao na view, para valer igualmente no admin, em
        importacao e em qualquer tela futura. A pessoa e uma so: o conflito
        atravessa escalas diferentes.
        """
        super().clean()
        if bool(self.voluntario_id) == bool(self.usuario_id):
            raise ValidationError("Selecione um usuário ou um voluntário como responsável.")
        if not self.turno_id:
            return

        pessoa = {"usuario_id": self.usuario_id} if self.usuario_id else {
            "voluntario_id": self.voluntario_id
        }

        outras = (
            Alocacao.objects.filter(
                **pessoa, turno__data=self.turno.data
            )
            .exclude(pk=self.pk)
            .select_related("turno")
        )

        for outra in outras:
            if self.turno.sobrepoe(outra.turno):
                raise ValidationError(
                    f"{self.nome_responsavel} já está escalada neste horário: "
                    f"{outra.turno.hora_inicio:%H:%M}–{outra.turno.hora_fim:%H:%M}, "
                    f"{outra.turno.atividade.nome}."
                )
