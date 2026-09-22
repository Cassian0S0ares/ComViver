from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models, transaction
from django.db.models.functions import Lower


class Perfil(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    TECNICO = "TECNICO", "Técnico"
    OPERACIONAL = "OPERACIONAL", "Operacional"


class UsuarioManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("perfil", Perfil.ADMIN)
        extra_fields.setdefault("precisa_trocar_senha", False)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """Usuario do sistema.

    O campo `perfil` determina o que a pessoa enxerga. O recorte entre TECNICO e
    OPERACIONAL existe por causa do art. 143 do ECA: quem trabalha na recepcao
    nao pode acessar dado que identifique a situacao do acolhido.
    """

    perfil = models.CharField(
        "perfil", max_length=15, choices=Perfil.choices, default=Perfil.OPERACIONAL
    )
    telefone = models.CharField("telefone", max_length=20, blank=True)
    precisa_trocar_senha = models.BooleanField(
        "precisa trocar a senha",
        default=True,
        help_text="Marcado para usuario novo; desmarcado apos a primeira troca.",
    )

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["first_name", "username"]
        constraints = [
            # O e-mail e a credencial de login; dois cadastros com o mesmo e-mail
            # tornariam o acesso ambiguo.
            models.UniqueConstraint(
                Lower("email"),
                name="usuario_email_unico",
                condition=~models.Q(email=""),
                violation_error_message="Já existe um usuário com este e-mail.",
            )
        ]

    def __str__(self) -> str:
        nome = self.get_full_name() or self.username
        return f"{nome} ({self.get_perfil_display()})"

    @property
    def e_admin(self) -> bool:
        return self.perfil == Perfil.ADMIN

    @property
    def e_tecnico(self) -> bool:
        return self.perfil == Perfil.TECNICO

    @property
    def e_operacional(self) -> bool:
        return self.perfil == Perfil.OPERACIONAL

    def pode_ver_ficha_completa(self) -> bool:
        """Ficha de acolhimento, situacao juridica e dados de saude."""
        return self.perfil in {Perfil.ADMIN, Perfil.TECNICO}

    def pode_gerenciar_usuarios(self) -> bool:
        return self.e_admin

    GRUPO_POR_PERFIL = {
        Perfil.ADMIN: "Administrador",
        Perfil.TECNICO: "Técnico",
        Perfil.OPERACIONAL: "Operacional",
    }

    def save(self, *args, **kwargs):
        with transaction.atomic(using=kwargs.get("using")):
            super().save(*args, **kwargs)
            self.sincronizar_grupo()

    def sincronizar_grupo(self) -> None:
        """Mantem o usuario em exatamente um grupo, o do seu perfil."""
        from django.contrib.auth.models import Group

        grupo, _ = Group.objects.get_or_create(name=self.GRUPO_POR_PERFIL[self.perfil])
        self.groups.set([grupo])


class AcaoFicha(models.TextChoices):
    VIEW = "VIEW", "Consultou"
    EDIT = "EDIT", "Alterou"


class LogAcessoFicha(models.Model):
    """Registro de acesso a ficha de acolhido.

    O historico de alteracoes nao revela quem apenas abriu e leu a ficha. Em
    instituicao de acolhimento essa informacao e necessaria, e precisa
    sobreviver a exclusao do usuario — por isso `usuario_descricao` guarda a
    identificacao em texto.
    """

    usuario = models.ForeignKey(
        "accounts.Usuario", null=True, on_delete=models.SET_NULL, related_name="acessos_ficha"
    )
    usuario_descricao = models.CharField("usuário", max_length=200, blank=True)
    acolhido = models.ForeignKey(
        "acolhidos.Acolhido", on_delete=models.CASCADE, related_name="acessos"
    )
    data_hora = models.DateTimeField("data e hora", auto_now_add=True)
    acao = models.CharField("ação", max_length=5, choices=AcaoFicha.choices)

    class Meta:
        verbose_name = "acesso a ficha"
        verbose_name_plural = "acessos a fichas"
        ordering = ["-data_hora"]
        indexes = [models.Index(fields=["acolhido", "-data_hora"])]

    def __str__(self) -> str:
        return f"{self.usuario_descricao} {self.get_acao_display().lower()} em {self.data_hora}"

    @classmethod
    def registrar(cls, usuario, acolhido, acao=AcaoFicha.VIEW):
        return cls.objects.create(
            usuario=usuario,
            usuario_descricao=str(usuario),
            acolhido=acolhido,
            acao=acao,
        )
