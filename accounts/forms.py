from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.template import loader

from accounts.emails import LOGO_CID, anexar_logo
from accounts.models import Usuario


class FormularioAcessivelMixin:
    def full_clean(self):
        super().full_clean()
        for nome in self.errors:
            if nome in self.fields:
                attrs = self.fields[nome].widget.attrs
                attrs["aria-invalid"] = "true"
                attrs["aria-describedby"] = f"id_{nome}_error id_{nome}_helptext"


class GestaoUsuarioFormMixin(FormularioAcessivelMixin):
    def __init__(self, *args, actor=None, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        if actor is None or not actor.pode_gerenciar_usuarios():
            raise PermissionDenied("Seu perfil não pode gerenciar usuários.")
        self.fields["email"].required = True
        self.fields["email"].help_text = "É com este e-mail que a pessoa entra no sistema."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if len(email) > 150:
            raise forms.ValidationError("Use um e-mail de até 150 caracteres.")
        repetido = Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("email"):
            # O nome de acesso deixou de ser digitado; acompanha o e-mail.
            self.instance.username = cleaned["email"]
        if self.actor is None or not self.actor.pode_gerenciar_usuarios():
            raise forms.ValidationError("Seu perfil não pode gerenciar usuários.")
        if self.instance.pk == self.actor.pk:
            if not cleaned.get("is_active", True):
                self.add_error("is_active", "Você não pode desativar o seu próprio acesso.")
            if cleaned.get("perfil") != self.actor.perfil:
                self.add_error("perfil", "Peça a outro administrador para alterar seu perfil.")
        return cleaned


class LoginForm(FormularioAcessivelMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "E-mail ou senha incorretos.",
        "inactive": "Este usuário está desativado. Procure a coordenação.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O campo segue se chamando `username` (o axes bloqueia por ele), mas
        # recebe o e-mail; ver accounts.backends.EmailBackend.
        self.fields["username"] = forms.EmailField(
            label="E-mail",
            max_length=254,
            widget=forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "autofocus": True,
                    "autocomplete": "email",
                    "placeholder": "seu@email.com",
                }
            ),
        )
        self.fields["password"].label = "Senha"
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Sua senha"}
        )


class TrocaSenhaForm(FormularioAcessivelMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Senha atual"
        self.fields["new_password1"].label = "Nova senha"
        self.fields["new_password2"].label = "Repita a nova senha"
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})


class EsqueciSenhaForm(FormularioAcessivelMixin, PasswordResetForm):
    """So envia o link a usuario cadastrado, ativo e com senha utilizavel.

    O filtro e o do proprio Django (`get_users`); o e-mail desconhecido recebe a
    mesma resposta na tela para nao revelar quem tem conta.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "E-mail"
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "autofocus": True, "placeholder": "seu@email.com"}
        )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        """Envia texto e HTML, com a logo anexada dentro da mensagem.

        A logo vai como anexo inline (cid:) e nao como link: o servidor pode
        nao ser acessivel de fora, e muitos clientes bloqueiam imagem remota.
        """
        context = {**context, "logo_cid": LOGO_CID}
        assunto = "".join(loader.render_to_string(subject_template_name, context).splitlines())
        mensagem = EmailMultiAlternatives(
            assunto,
            loader.render_to_string(email_template_name, context),
            from_email,
            [to_email],
        )
        if html_email_template_name:
            mensagem.attach_alternative(
                loader.render_to_string(html_email_template_name, context), "text/html"
            )
            anexar_logo(mensagem)
        mensagem.send()


class NovaSenhaForm(FormularioAcessivelMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Nova senha"
        self.fields["new_password2"].label = "Repita a nova senha"
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})

    def save(self, commit=True):
        # Quem definiu a senha pelo link ja escolheu a propria; nao e provisoria.
        self.user.precisa_trocar_senha = False
        return super().save(commit=commit)


CAMPOS_USUARIO = ["first_name", "last_name", "email", "telefone", "perfil"]

ROTULOS = {
    "first_name": "Nome",
    "last_name": "Sobrenome",
    "email": "E-mail",
    "telefone": "Telefone",
    "perfil": "Perfil",
    "is_active": "Usuário ativo",
}


class UsuarioCreationForm(GestaoUsuarioFormMixin, UserCreationForm):
    class Meta:
        model = Usuario
        fields = CAMPOS_USUARIO
        labels = ROTULOS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Senha provisória"
        self.fields["password2"].label = "Repita a senha provisória"
        self.fields[
            "password1"
        ].help_text = "O usuário será obrigado a trocá-la no primeiro acesso."
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})
        self.fields["perfil"].widget.attrs.update({"class": "form-select"})


class UsuarioForm(GestaoUsuarioFormMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = CAMPOS_USUARIO + ["is_active"]
        labels = ROTULOS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome, campo in self.fields.items():
            if nome == "is_active":
                campo.widget.attrs.update({"class": "form-check-input"})
            elif nome == "perfil":
                campo.widget.attrs.update({"class": "form-select"})
            else:
                campo.widget.attrs.update({"class": "form-control"})
