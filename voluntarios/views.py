from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin
from core.views import BaseCreateView, BaseListView, BaseUpdateView
from voluntarios.forms import FuncaoForm, VoluntarioForm
from voluntarios.models import Funcao, StatusVoluntario, Voluntario

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
QUEM_GERENCIA = [Perfil.ADMIN, Perfil.OPERACIONAL]


class VoluntarioListView(BaseListView):
    model = Voluntario
    template_name = "voluntarios/voluntario_list.html"
    context_object_name = "voluntarios"
    campos_busca = ["nome", "email", "telefone"]
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("funcoes", "disponibilidades")
        situacao = self.request.GET.get("situacao", StatusVoluntario.ATIVO)
        if situacao != "TODOS":
            qs = qs.filter(status=situacao)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["situacao"] = self.request.GET.get("situacao", StatusVoluntario.ATIVO)
        return contexto


class VoluntarioDetailView(PerfilRequiredMixin, DetailView):
    model = Voluntario
    template_name = "voluntarios/voluntario_detail.html"
    context_object_name = "voluntario"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        from escalas.models import Alocacao

        contexto = super().get_context_data(**kwargs)
        contexto["alocacoes"] = (
            Alocacao.objects.filter(voluntario=self.object)
            .select_related("turno", "turno__atividade", "turno__escala")
            .order_by("-turno__data")[:20]
        )
        return contexto


class VoluntarioCreateView(BaseCreateView):
    model = Voluntario
    form_class = VoluntarioForm
    template_name = "voluntarios/voluntario_form.html"
    mensagem_sucesso = "Voluntário cadastrado."
    perfis_permitidos = QUEM_GERENCIA

    def get_success_url(self):
        return reverse("voluntarios:detalhe", args=[self.object.pk])


class VoluntarioUpdateView(BaseUpdateView):
    model = Voluntario
    form_class = VoluntarioForm
    template_name = "voluntarios/voluntario_form.html"
    mensagem_sucesso = "Dados do voluntário atualizados."
    perfis_permitidos = QUEM_GERENCIA

    def get_success_url(self):
        return reverse("voluntarios:detalhe", args=[self.object.pk])


class FuncaoListView(BaseListView):
    model = Funcao
    template_name = "voluntarios/funcao_list.html"
    context_object_name = "funcoes"
    campos_busca = ["nome"]
    perfis_permitidos = TODOS_OS_PERFIS


class FuncaoCreateView(BaseCreateView):
    model = Funcao
    form_class = FuncaoForm
    template_name = "voluntarios/funcao_form.html"
    mensagem_sucesso = "Função cadastrada."
    success_url = reverse_lazy("voluntarios:funcao_lista")
    perfis_permitidos = [Perfil.ADMIN]
