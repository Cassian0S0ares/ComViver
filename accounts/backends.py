from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Autentica pelo e-mail, sem diferenciar maiusculas.

    O formulario de login continua enviando o campo como `username` para que o
    django-axes aplique o bloqueio por tentativas sobre o e-mail digitado.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (kwargs.get("email") or username or "").strip()
        if not email or password is None:
            return None
        Usuario = get_user_model()
        try:
            usuario = Usuario._default_manager.get(email__iexact=email)
        except (Usuario.DoesNotExist, Usuario.MultipleObjectsReturned):
            # Mesmo custo de hash de um login valido, para nao revelar quais
            # e-mails existem pelo tempo de resposta.
            Usuario().set_password(password)
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
