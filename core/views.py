from django.contrib import messages
from django.db.models import Q
from django.urls import reverse
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

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
        from django.utils import timezone

        from acolhidos.models import Acolhido, Medicacao, StatusAcolhido
        from doacoes.models import Doacao
        from doacoes.services import doadores_recorrentes_inativos, total_arrecadado

        cartoes = [
            {
                "titulo": "Acolhidos",
                "valor": Acolhido.objects.filter(status=StatusAcolhido.ACOLHIDO).count(),
                "descricao": "em acolhimento hoje",
                "icone": "emoji-smile",
                "url": reverse("acolhidos:lista"),
            }
        ]

        if self.request.user.pode_ver_ficha_completa():
            cartoes.append(
                {
                    "titulo": "Medicações do dia",
                    "valor": Medicacao.em_vigor.filter(
                        acolhido__status=StatusAcolhido.ACOLHIDO,
                        acolhido__deleted_at__isnull=True,
                    ).count(),
                    "descricao": "em uso hoje",
                    "icone": "capsule",
                    "url": reverse("acolhidos:medicacoes"),
                }
            )

        if self.request.user.pode_gerenciar_usuarios():
            cartoes.append(
                {
                    "titulo": "Usuários ativos",
                    "valor": Usuario.objects.filter(is_active=True).count(),
                    "descricao": "com acesso ao sistema",
                    "icone": "people",
                    "url": reverse("accounts:usuario_list"),
                }
            )

        hoje = timezone.localdate()
        recebidas = Doacao.objects.filter(
            data_recebimento__gte=hoje.replace(day=1), data_recebimento__lte=hoje
        )
        valor = f"{total_arrecadado(recebidas):,.2f}"
        valor = valor.replace(",", "X").replace(".", ",").replace("X", ".")
        cartoes.append(
            {
                "titulo": "Doações do mês",
                "valor": f"R$ {valor}",
                "descricao": f"em dinheiro · {recebidas.count()} contribuições de todos os tipos",
                "icone": "box2-heart",
                "url": reverse("doacoes:lista"),
            }
        )
        if self.request.user.e_admin:
            cartoes.append(
                {
                    "titulo": "Doadores para retomar contato",
                    "valor": doadores_recorrentes_inativos().count(),
                    "descricao": "recorrentes sem contribuição há 60 dias",
                    "icone": "person-heart",
                    "url": reverse("doacoes:doador_lista") + "?inativos=1",
                }
            )
        return cartoes


class BaseListView(PerfilRequiredMixin, ListView):
    """Listagem com busca textual e paginacao.

    Declare `campos_busca` com os campos que o `?q=` deve varrer.
    """

    paginate_by = 25
    campos_busca: list[str] = []

    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get("page"))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_queryset(self):
        qs = super().get_queryset()
        busca = self.request.GET.get("q", "").strip()
        if busca and self.campos_busca:
            filtro = Q()
            for campo in self.campos_busca:
                filtro |= Q(**{f"{campo}__icontains": busca})
            qs = qs.filter(filtro)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["busca"] = self.request.GET.get("q", "")
        filtros = self.request.GET.copy()
        filtros.pop("page", None)
        contexto["filtros_query"] = filtros.urlencode()
        return contexto


class _SalvarComAutorMixin:
    """Injeta o usuario no formulario e registra quem criou o registro."""

    mensagem_sucesso: str = "Registro salvo."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not form.instance.pk and hasattr(form.instance, "criado_por"):
            form.instance.criado_por = self.request.user
        resposta = super().form_valid(form)
        messages.success(self.request, self.mensagem_sucesso)
        return resposta


class BaseCreateView(PerfilRequiredMixin, _SalvarComAutorMixin, CreateView):
    pass


class BaseUpdateView(PerfilRequiredMixin, _SalvarComAutorMixin, UpdateView):
    pass
