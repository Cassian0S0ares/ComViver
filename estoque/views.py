from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, DetailView, FormView

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin
from core.views import BaseListView
from estoque.forms import BaixaForm, CategoriaForm, EntradaForm
from estoque.models import CategoriaItem, ItemEstoque
from estoque.services import (
    DIAS_ALERTA_VALIDADE, dar_baixa, item_por_nome, itens_disponiveis, perto_da_validade,
    registrar_entrada,
)

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
# Entrada manual e categorias: administracao e equipe tecnica. A baixa e de todos,
# porque quem usa o item no dia a dia e quem registra a saida.
QUEM_ABASTECE = [Perfil.ADMIN, Perfil.TECNICO]


def _pode_abastecer(usuario) -> bool:
    return usuario.perfil in QUEM_ABASTECE


def _contexto_validade() -> dict:
    hoje = timezone.localdate()
    return {"hoje": hoje, "limite_validade": hoje + timedelta(days=DIAS_ALERTA_VALIDADE)}


class EstoqueListView(BaseListView):
    model = ItemEstoque
    template_name = "estoque/estoque_list.html"
    context_object_name = "itens"
    perfis_permitidos = TODOS_OS_PERFIS

    def _categoria(self):
        valor = self.request.GET.get("categoria", "")
        return CategoriaItem.objects.filter(pk=valor).first() if valor.isdecimal() else None

    def get_queryset(self):
        return itens_disponiveis(self.request.GET.get("q", ""), self._categoria())

    def get_context_data(self, **kwargs):
        categoria = self._categoria()
        return super().get_context_data(**kwargs) | _contexto_validade() | {
            "categorias": CategoriaItem.objects.all(),
            "categoria_filtrada": categoria.pk if categoria else "",
            "pode_abastecer": _pode_abastecer(self.request.user),
            "baixa_form": BaixaForm(auto_id="baixa_%s"),
            "total_perto_validade": perto_da_validade().count(),
        }


class ItemDetailView(PerfilRequiredMixin, DetailView):
    model = ItemEstoque
    template_name = "estoque/item_detail.html"
    context_object_name = "item"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        return ItemEstoque.objects.select_related("categoria")

    def get_context_data(self, **kwargs):
        lotes = self.object.lotes.filter(saldo__gt=0).select_related("doacao__doador")
        return super().get_context_data(**kwargs) | _contexto_validade() | {
            "lotes": lotes,
            "disponivel": sum(lote.saldo for lote in lotes),
            "movimentacoes": self.object.movimentacoes.select_related("usuario")[:30],
            "pode_abastecer": _pode_abastecer(self.request.user),
            "baixa_form": kwargs.get("baixa_form") or BaixaForm(),
        }


class EntradaView(PerfilRequiredMixin, FormView):
    """Entrada manual: compra, sobra de bazar, item que chegou sem ser doacao."""

    form_class = EntradaForm
    template_name = "estoque/entrada_form.html"
    perfis_permitidos = QUEM_ABASTECE

    def get_initial(self):
        inicial = super().get_initial()
        item = self.request.GET.get("item", "")
        item = ItemEstoque.objects.filter(pk=item).first() if item.isdecimal() else None
        if item:
            inicial |= {"categoria": item.categoria_id, "item_nome": item.nome}
        elif (categoria := self.request.GET.get("categoria", "")).isdecimal():
            inicial["categoria"] = categoria
        return inicial

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "itens_catalogo": ItemEstoque.objects.select_related("categoria"),
        }

    def form_valid(self, form):
        dados = form.cleaned_data
        with transaction.atomic():
            item = item_por_nome(dados["categoria"], dados["item_nome"])
            registrar_entrada(item, dados["quantidade"], self.request.user,
                              validade=dados.get("validade"), observacao=dados["observacao"])
        messages.success(self.request, f"{dados['quantidade']} unidade(s) de {item.nome} "
                                       "adicionada(s) ao estoque.")
        if "salvar_e_novo" in self.request.POST:
            return redirect(f"{reverse('estoque:entrada')}?categoria={item.categoria_id}")
        return redirect("estoque:lista")


class BaixaView(PerfilRequiredMixin, View):
    perfis_permitidos = TODOS_OS_PERFIS

    def post(self, request, pk):
        item = get_object_or_404(ItemEstoque, pk=pk)
        destino = request.POST.get("proximo", "")
        if not url_has_allowed_host_and_scheme(destino, {request.get_host()}):
            destino = reverse("estoque:lista")
        form = BaixaForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Informe uma quantidade inteira maior que zero.")
            return redirect(destino)
        quantidade = form.cleaned_data["quantidade"]
        try:
            dar_baixa(item, quantidade, request.user, form.cleaned_data["observacao"])
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
        else:
            messages.success(request, f"Baixa de {quantidade} unidade(s) de {item.nome} registrada.")
        return redirect(destino)


class CategoriaCreateView(PerfilRequiredMixin, CreateView):
    model = CategoriaItem
    form_class = CategoriaForm
    template_name = "estoque/categoria_form.html"
    perfis_permitidos = QUEM_ABASTECE

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        resposta = super().form_valid(form)
        messages.success(self.request, f"Categoria {self.object.nome} criada.")
        return resposta

    def get_success_url(self):
        return f"{reverse('estoque:entrada')}?categoria={self.object.pk}"
