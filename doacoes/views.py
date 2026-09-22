from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin
from core.views import BaseCreateView, BaseListView, BaseUpdateView
from doacoes.forms import CampanhaForm, DoacaoForm, DoadorForm
from doacoes.models import Campanha, Doacao, Doador

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
QUEM_REGISTRA = [Perfil.ADMIN, Perfil.OPERACIONAL]


class DoacaoListView(BaseListView):
    model = Doacao
    template_name = "doacoes/doacao_list.html"
    context_object_name = "doacoes"
    campos_busca = ["descricao", "doador__nome"]
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        qs = super().get_queryset().select_related("doador", "campanha", "recebido_por")
        tipo = self.request.GET.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)
        return qs

    def get_context_data(self, **kwargs):
        from doacoes.services import totais_por_tipo

        contexto = super().get_context_data(**kwargs)
        contexto["tipo_filtrado"] = self.request.GET.get("tipo", "")
        contexto["totais"] = totais_por_tipo(self.get_queryset())
        return contexto


class DoacaoCreateView(BaseCreateView):
    """Registro rapido. Otimizado para volume: doacao chega em lote, na
    portaria, com fila esperando."""

    model = Doacao
    form_class = DoacaoForm
    template_name = "doacoes/doacao_form.html"
    mensagem_sucesso = "Doação registrada."
    perfis_permitidos = QUEM_REGISTRA

    def get_initial(self):
        inicial = super().get_initial()
        if doador := self.request.GET.get("doador"):
            inicial["doador"] = doador
        if data := self.request.GET.get("data"):
            inicial["data_recebimento"] = data
        return inicial

    def form_valid(self, form):
        form.instance.recebido_por = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        if "salvar_e_novo" in self.request.POST:
            parametros = f"?data={self.object.data_recebimento.isoformat()}"
            if self.object.doador_id:
                parametros += f"&doador={self.object.doador_id}"
            return reverse("doacoes:nova") + parametros
        return reverse("doacoes:lista")


class DoacaoUpdateView(BaseUpdateView):
    model = Doacao
    form_class = DoacaoForm
    template_name = "doacoes/doacao_form.html"
    mensagem_sucesso = "Doação atualizada."
    success_url = reverse_lazy("doacoes:lista")
    perfis_permitidos = QUEM_REGISTRA


class BuscarDoadorView(PerfilRequiredMixin, ListView):
    """Fragmento HTMX: sugere doadores a partir de tres caracteres."""

    model = Doador
    template_name = "doacoes/partials/_resultado_busca_doador.html"
    context_object_name = "doadores"
    perfis_permitidos = QUEM_REGISTRA

    def get_queryset(self):
        termo = self.request.GET.get("termo", "").strip()
        if len(termo) < 3:
            return Doador.objects.none()
        return Doador.objects.filter(nome__icontains=termo)[:8]


class DoadorListView(BaseListView):
    model = Doador
    template_name = "doacoes/doador_list.html"
    context_object_name = "doadores"
    campos_busca = ["nome", "cpf_cnpj", "email"]
    perfis_permitidos = TODOS_OS_PERFIS


class DoadorDetailView(PerfilRequiredMixin, DetailView):
    model = Doador
    template_name = "doacoes/doador_detail.html"
    context_object_name = "doador"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["doacoes"] = self.object.doacoes.select_related("campanha")
        return contexto


class DoadorCreateView(BaseCreateView):
    model = Doador
    form_class = DoadorForm
    template_name = "doacoes/doador_form.html"
    mensagem_sucesso = "Doador cadastrado."
    perfis_permitidos = QUEM_REGISTRA

    def get_success_url(self):
        return reverse("doacoes:doador_detalhe", args=[self.object.pk])


class DoadorUpdateView(BaseUpdateView):
    model = Doador
    form_class = DoadorForm
    template_name = "doacoes/doador_form.html"
    mensagem_sucesso = "Dados do doador atualizados."
    perfis_permitidos = QUEM_REGISTRA

    def get_success_url(self):
        return reverse("doacoes:doador_detalhe", args=[self.object.pk])


class CampanhaListView(BaseListView):
    model = Campanha
    template_name = "doacoes/campanha_list.html"
    context_object_name = "campanhas"
    campos_busca = ["nome"]
    perfis_permitidos = TODOS_OS_PERFIS


class CampanhaCreateView(BaseCreateView):
    model = Campanha
    form_class = CampanhaForm
    template_name = "doacoes/campanha_form.html"
    mensagem_sucesso = "Campanha criada."
    success_url = reverse_lazy("doacoes:campanha_lista")
    perfis_permitidos = [Perfil.ADMIN]


class CampanhaUpdateView(BaseUpdateView):
    model = Campanha
    form_class = CampanhaForm
    template_name = "doacoes/campanha_form.html"
    mensagem_sucesso = "Campanha atualizada."
    success_url = reverse_lazy("doacoes:campanha_lista")
    perfis_permitidos = [Perfil.ADMIN]

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from core.pdf import renderizar_pdf


class ReciboView(PerfilRequiredMixin, DetailView):
    """Recibo individual da doacao, em tela ou PDF."""

    model = Doacao
    template_name = "doacoes/recibo.html"
    context_object_name = "doacao"
    perfis_permitidos = QUEM_REGISTRA

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["emitido_em"] = timezone.localtime()
        contexto["emitido_por"] = self.request.user
        contexto["instituicao"] = {
            "nome": "Lar Padre José Gumercindo",
            "cnpj": "",
            "endereco": "",
        }
        return contexto

    def get(self, request, *args, **kwargs):
        resposta = super().get(request, *args, **kwargs)

        # A marcacao de "recibo emitido" acontece no POST, nunca aqui: um GET
        # nao deve alterar estado. Do jeito contrario, o prefetch do navegador
        # ou uma <img src> embutida em site externo marcaria recibos sozinha.
        if request.GET.get("formato") == "pdf":
            return renderizar_pdf(
                self.template_name,
                resposta.context_data,
                f"recibo-{self.object.pk}.pdf",
                request=request,
            )
        return resposta

    def post(self, request, *args, **kwargs):
        """Marca o recibo como entregue ao doador."""
        self.object = self.get_object()
        if not self.object.recibo_emitido:
            self.object.recibo_emitido = True
            self.object.save(update_fields=["recibo_emitido"])
            messages.success(request, "Recibo marcado como entregue.")
        return redirect("doacoes:recibo", pk=self.object.pk)
