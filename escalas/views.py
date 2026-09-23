from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin
from core.views import BaseCreateView, BaseListView
from escalas.forms import EscalaForm, TurnoForm
from escalas.models import Alocacao, Escala, StatusEscala, Turno
from escalas.services import grade_da_escala, voluntarios_disponiveis
from voluntarios.models import StatusVoluntario, Voluntario

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
QUEM_MONTA = [Perfil.ADMIN, Perfil.OPERACIONAL]


class EscalaListView(BaseListView):
    model = Escala
    template_name = "escalas/escala_list.html"
    context_object_name = "escalas"
    campos_busca = ["titulo"]
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        return super().get_queryset().prefetch_related("turnos__alocacoes")


class EscalaCreateView(BaseCreateView):
    model = Escala
    form_class = EscalaForm
    template_name = "escalas/escala_form.html"
    mensagem_sucesso = "Escala criada. Agora adicione os turnos."
    perfis_permitidos = QUEM_MONTA

    def get_success_url(self):
        return reverse("escalas:grade", args=[self.object.pk])


class EscalaGradeView(PerfilRequiredMixin, DetailView):
    """Grade semanal: turnos nas linhas, dias nas colunas.

    A pergunta real do coordenador nao e 'quem esta escalado', e sim 'onde
    esta o buraco' — por isso turno descoberto recebe destaque.
    """

    model = Escala
    template_name = "escalas/escala_grade.html"
    context_object_name = "escala"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto |= grade_da_escala(self.object)
        contexto["pode_montar"] = self.request.user.perfil in QUEM_MONTA
        return contexto


class TurnoCreateView(BaseCreateView):
    model = Turno
    form_class = TurnoForm
    template_name = "escalas/turno_form.html"
    mensagem_sucesso = "Turno adicionado à escala."
    perfis_permitidos = QUEM_MONTA

    def dispatch(self, request, *args, **kwargs):
        self.escala = get_object_or_404(Escala, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"escala": self.escala}

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"escala": self.escala}

    def form_valid(self, form):
        form.instance.escala = self.escala
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("escalas:grade", args=[self.escala.pk])


class DisponiveisView(PerfilRequiredMixin, View):
    """Fragmento HTMX: quem pode assumir este turno."""

    perfis_permitidos = QUEM_MONTA

    def get(self, request, pk):
        turno = get_object_or_404(Turno, pk=pk)
        return render(
            request,
            "escalas/partials/_lista_disponiveis.html",
            {"turno": turno, "voluntarios": voluntarios_disponiveis(turno)},
        )


class AlocarView(PerfilRequiredMixin, View):
    """Aloca um voluntario no turno e devolve a celula atualizada."""

    perfis_permitidos = QUEM_MONTA

    def post(self, request, pk):
        turno = get_object_or_404(Turno, pk=pk)

        voluntario = get_object_or_404(
            Voluntario, pk=request.POST.get("voluntario"), status=StatusVoluntario.ATIVO
        )
        alocacao = Alocacao(turno=turno, voluntario=voluntario)

        try:
            alocacao.full_clean()
        except ValidationError as erro:
            mensagens = [m for lista in erro.message_dict.values() for m in lista]
            # Renderiza por template: a mensagem contem o nome do voluntario,
            # que e dado de entrada. Montar o HTML com f-string entregaria XSS
            # refletido a quem conseguisse cadastrar um nome com marcacao.
            return render(
                request,
                "escalas/partials/_erro_alocacao.html",
                {"mensagens": mensagens},
                status=200,
            )

        alocacao.save()
        return render(
            request, "escalas/partials/_celula_turno.html",
            {"turno": turno, "pode_montar": True},
        )


class DesalocarView(PerfilRequiredMixin, View):
    perfis_permitidos = QUEM_MONTA

    def post(self, request, pk):
        alocacao = get_object_or_404(Alocacao, pk=pk)
        turno = alocacao.turno
        alocacao.delete()
        return render(
            request, "escalas/partials/_celula_turno.html",
            {"turno": turno, "pode_montar": True},
        )


class PublicarView(PerfilRequiredMixin, View):
    perfis_permitidos = QUEM_MONTA

    def post(self, request, pk):
        escala = get_object_or_404(Escala, pk=pk)

        if not escala.turnos.exists():
            messages.error(
                request, "Adicione pelo menos um turno antes de publicar a escala."
            )
        else:
            escala.status = StatusEscala.PUBLICADA
            escala.save(update_fields=["status"])
            descobertos = escala.turnos_descobertos
            if descobertos:
                messages.warning(
                    request,
                    f"Escala publicada com {descobertos} turno(s) ainda sem "
                    "voluntário. Você pode continuar preenchendo.",
                )
            else:
                messages.success(request, "Escala publicada.")

        return redirect("escalas:grade", pk=escala.pk)
