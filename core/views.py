from django.views.generic import TemplateView

from accounts.models import Perfil, Usuario
from core.mixins import PerfilRequiredMixin


class PainelView(PerfilRequiredMixin, TemplateView):
    """Tela inicial. Os cartoes variam conforme o perfil (spec 6.7).

    As fases 2 a 5 acrescentam cartoes a esta lista: acolhidos ativos,
    doacoes do mes, escala de hoje e turnos descobertos.
    """

    template_name = "core/painel.html"
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["cartoes"] = self._montar_cartoes()
        return contexto

    def _montar_cartoes(self) -> list[dict]:
        cartoes = []

        if self.request.user.pode_gerenciar_usuarios():
            cartoes.append(
                {
                    "titulo": "Usuários ativos",
                    "valor": Usuario.objects.filter(is_active=True).count(),
                    "descricao": "com acesso ao sistema",
                    "icone": "people",
                }
            )

        return cartoes
