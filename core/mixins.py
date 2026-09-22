from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied


class PerfilRequiredMixin(LoginRequiredMixin):
    """Restringe a view aos perfis declarados em `perfis_permitidos`.

    Primeira das tres camadas de controle de acesso (spec 5.2). As outras duas
    sao o formulario, que nao monta o campo restrito, e o template, que nao o
    renderiza.

    Omitir `perfis_permitidos` levanta ImproperlyConfigured: esquecer a
    declaracao tem de quebrar, nunca liberar acesso.
    """

    perfis_permitidos: list[str] | None = None

    def dispatch(self, request, *args, **kwargs):
        if self.perfis_permitidos is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} precisa declarar `perfis_permitidos`."
            )
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.perfil not in self.perfis_permitidos:
            raise PermissionDenied("Seu perfil não tem acesso a esta página.")
        return super().dispatch(request, *args, **kwargs)


class RegistraAcessoFichaMixin:
    """Registra em LogAcessoFicha toda abertura da ficha.

    Usar apenas em views cujo `get_object()` devolva um Acolhido.
    """

    def get_object(self, queryset=None):
        objeto = super().get_object(queryset)
        from accounts.models import AcaoFicha, LogAcessoFicha

        LogAcessoFicha.registrar(self.request.user, objeto, AcaoFicha.VIEW)
        return objeto
