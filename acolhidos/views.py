from django.views.generic import DetailView

from accounts.models import Perfil
from acolhidos.models import Acolhido, Medicacao, StatusAcolhido, VinculoFamiliar
from core.mixins import PerfilRequiredMixin, RegistraAcessoFichaMixin
from core.views import BaseListView

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
SITUACOES = [
    (StatusAcolhido.ACOLHIDO, "Acolhidos"),
    (StatusAcolhido.DESLIGADO, "Desligados"),
    ("TODOS", "Todos"),
]


class AcolhidoListView(BaseListView):
    """Lista com nome, foto, idade e situacao — e nada mais.

    E tela que fica aberta na sala: nenhum dado da ficha aparece aqui, nem
    para o Admin.
    """

    model = Acolhido
    template_name = "acolhidos/acolhido_list.html"
    context_object_name = "acolhidos"
    campos_busca = ["nome", "nome_social"]
    perfis_permitidos = TODOS_OS_PERFIS

    def _situacao(self) -> str:
        situacao = self.request.GET.get("situacao", StatusAcolhido.ACOLHIDO)
        return situacao if situacao in dict(SITUACOES) else StatusAcolhido.ACOLHIDO

    def get_queryset(self):
        qs = super().get_queryset()
        situacao = self._situacao()
        if situacao != "TODOS":
            qs = qs.filter(status=situacao)
        return qs.order_by("nome", "pk")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["situacao"] = self._situacao()
        contexto["situacoes"] = SITUACOES
        return contexto


class AcolhidoDetailView(PerfilRequiredMixin, RegistraAcessoFichaMixin, DetailView):
    """Ficha do acolhido, recortada pelo perfil.

    Todos os perfis abrem a ficha, mas o Operacional recebe apenas o bloco de
    cuidado diario. Os dados sigilosos nao sao renderizados — nao basta
    esconde-los, precisam estar ausentes do HTML (spec 5.2, camada 3).
    """

    model = Acolhido
    template_name = "acolhidos/acolhido_detail.html"
    context_object_name = "acolhido"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        acolhido = self.object

        contexto["pode_ver_ficha"] = self.request.user.pode_ver_ficha_completa()
        contexto["medicacoes_em_vigor"] = Medicacao.em_vigor.filter(acolhido=acolhido)
        contexto["autorizados_retirar"] = VinculoFamiliar.objects.filter(
            acolhido=acolhido, autorizado_retirar=True
        ).select_related("responsavel")

        # Os dados sigilosos so entram no contexto quando o perfil pode ve-los:
        # o template nao tem como renderiza-los por engano.
        if contexto["pode_ver_ficha"]:
            contexto["ficha"] = getattr(acolhido, "ficha", None)
            contexto["saude"] = getattr(acolhido, "saude", None)
            contexto["vinculos"] = acolhido.vinculos.select_related("responsavel")
            contexto["escolaridades"] = acolhido.escolaridades.all()
            contexto["documentos"] = acolhido.documentos.all()

        return contexto
