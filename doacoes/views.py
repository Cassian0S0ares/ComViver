import re
from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import DetailView, ListView, View

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin
from core.pdf import renderizar_pdf
from core.views import BaseCreateView, BaseListView, BaseUpdateView
from doacoes.forms import CampanhaForm, DoacaoForm, DoadorForm, MetasItemFormSet
from doacoes.models import Campanha, Doacao, Doador, TipoDoacao

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
QUEM_REGISTRA = [Perfil.ADMIN, Perfil.OPERACIONAL]


NOMES_MESES = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


class DoacaoListView(BaseListView):
    model = Doacao
    template_name = "doacoes/doacao_list.html"
    context_object_name = "doacoes"
    campos_busca = ["descricao", "doador__nome"]
    perfis_permitidos = TODOS_OS_PERFIS

    def _mes_filtrado(self):
        mes = self.request.GET.get("mes", "")
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            return ""
        try:
            date.fromisoformat(f"{mes}-01")
        except ValueError:
            return ""
        return mes

    def _meses_disponiveis(self, mes_filtrado):
        """Meses com doacoes, do mais recente ao mais antigo, com rotulo legivel."""
        valores = [
            dia.strftime("%Y-%m")
            for dia in self.model._default_manager.dates("data_recebimento", "month", order="DESC")
        ]
        if mes_filtrado and mes_filtrado not in valores:
            valores.append(mes_filtrado)
            valores.sort(reverse=True)
        opcoes = []
        for valor in valores:
            ano, numero_mes = valor.split("-")
            opcoes.append((valor, f"{NOMES_MESES[int(numero_mes) - 1]} de {ano}"))
        return opcoes

    def get_queryset(self):
        qs = super().get_queryset().select_related("doador", "campanha", "recebido_por")
        tipo = self.request.GET.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)
        mes = self._mes_filtrado()
        if mes:
            ano, numero_mes = map(int, mes.split("-"))
            inicio = date(ano, numero_mes, 1)
            if ano == 9999 and numero_mes == 12:
                qs = qs.filter(data_recebimento__gte=inicio)
            else:
                proximo_mes = (
                    date(ano + 1, 1, 1)
                    if numero_mes == 12
                    else date(ano, numero_mes + 1, 1)
                )
                qs = qs.filter(data_recebimento__gte=inicio, data_recebimento__lt=proximo_mes)
        return qs

    def get_context_data(self, **kwargs):
        from doacoes.services import totais_por_tipo

        contexto = super().get_context_data(**kwargs)
        contexto["tipo_filtrado"] = self.request.GET.get("tipo", "")
        contexto["mes_filtrado"] = self._mes_filtrado()
        contexto["meses_disponiveis"] = self._meses_disponiveis(contexto["mes_filtrado"])
        contexto["totais"] = totais_por_tipo(self.get_queryset())
        contexto["form_tipos"] = TipoDoacao.choices
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
        doador = self.request.GET.get("doador", "")
        if doador.isdecimal() and len(doador) < 19 and Doador.objects.filter(pk=doador).exists():
            inicial["doador"] = doador
        try:
            data = parse_date(self.request.GET.get("data", ""))
        except ValueError:
            data = None
        if data and data <= timezone.localdate():
            inicial["data_recebimento"] = data
        return inicial

    def form_valid(self, form):
        form.instance.recebido_por = self.request.user
        with transaction.atomic():
            resposta = super().form_valid(form)
            form.sincronizar_estoque(self.object, self.request.user)
        return resposta

    def get_context_data(self, **kwargs):
        from estoque.models import ItemEstoque

        return super().get_context_data(**kwargs) | {"itens_catalogo": ItemEstoque.objects.select_related("categoria")}

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

    def form_valid(self, form):
        with transaction.atomic():
            resposta = super().form_valid(form)
            form.sincronizar_estoque(self.object, self.request.user)
        return resposta

    def get_context_data(self, **kwargs):
        from estoque.models import ItemEstoque

        return super().get_context_data(**kwargs) | {"itens_catalogo": ItemEstoque.objects.select_related("categoria")}


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

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.GET.get("inativos") == "1":
            from doacoes.services import doadores_recorrentes_inativos

            qs = qs.filter(pk__in=doadores_recorrentes_inativos().values("pk"))
        return qs


class DoadorDetailView(PerfilRequiredMixin, DetailView):
    model = Doador
    template_name = "doacoes/doador_detail.html"
    context_object_name = "doador"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        pagina = Paginator(self.object.doacoes.select_related("campanha"), 25).get_page(
            self.request.GET.get("page")
        )
        contexto.update(doacoes=pagina.object_list, page_obj=pagina, paginator=pagina.paginator)
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

    SITUACOES = {"ativas", "inativas", "todas"}

    def _situacao(self) -> str:
        """A tela abre no que esta valendo hoje; o resto fica a um filtro."""
        situacao = self.request.GET.get("situacao", "ativas")
        return situacao if situacao in self.SITUACOES else "ativas"

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("metas_itens").annotate(
            registros_itens=Count(
                "doacoes",
                filter=Q(
                    doacoes__deleted_at__isnull=True,
                    doacoes__tipo__in=[
                        tipo for tipo, _ in TipoDoacao.choices if tipo != TipoDoacao.DINHEIRO
                    ],
                ),
            )
        )
        qs = qs.order_by("-data_inicio", "-pk")
        situacao = self._situacao()
        if situacao == "ativas":
            return qs.ativas()
        if situacao == "inativas":
            return qs.exclude(pk__in=Campanha.objects.ativas().values("pk"))
        return qs

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"situacao_filtrada": self._situacao()}


class CampanhaDetailView(PerfilRequiredMixin, DetailView):
    model = Campanha
    template_name = "doacoes/campanha_detail.html"
    context_object_name = "campanha"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        doacoes = self.object.doacoes.select_related("doador", "recebido_por")
        pagina = Paginator(doacoes, 25).get_page(self.request.GET.get("page"))
        itens = list(
            Doacao.objects.filter(campanha=self.object)
            .exclude(tipo=TipoDoacao.DINHEIRO)
            .values("tipo", "descricao", "unidade")
            .annotate(quantidade_total=Sum("quantidade"), registros=Count("pk"))
            .order_by("tipo", "descricao", "unidade")
        )
        tipos = dict(TipoDoacao.choices)
        for item in itens:
            item["tipo_display"] = tipos[item["tipo"]]
        contexto.update(
            doacoes=pagina.object_list,
            page_obj=pagina,
            paginator=pagina.paginator,
            filtros_query="",
            resumo_itens=itens,
            total_registros_itens=sum(item["registros"] for item in itens),
        )
        return contexto


class MetasCampanhaMixin:
    def get_metas_formset(self):
        return MetasItemFormSet(
            data=self.request.POST if self.request.method == "POST" else None,
            instance=self.object or Campanha(),
            prefix="metas",
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["metas_formset"] = getattr(self, "metas_formset", None) or self.get_metas_formset()
        return contexto

    def form_valid(self, form):
        self.metas_formset = self.get_metas_formset()
        if not self.metas_formset.is_valid():
            return self.form_invalid(form)
        with transaction.atomic():
            if not form.instance.pk:
                form.instance.criado_por = self.request.user
            self.object = form.save()
            self.metas_formset.instance = self.object
            metas = self.metas_formset.save(commit=False)
            for removida in self.metas_formset.deleted_objects:
                removida.delete()
            for meta in metas:
                meta.save()
            self.metas_formset.save_m2m()
        messages.success(self.request, self.mensagem_sucesso)
        return HttpResponseRedirect(self.get_success_url())

class CampanhaCreateView(MetasCampanhaMixin, BaseCreateView):
    model = Campanha
    form_class = CampanhaForm
    template_name = "doacoes/campanha_form.html"
    mensagem_sucesso = "Campanha criada."
    success_url = reverse_lazy("doacoes:campanha_lista")
    perfis_permitidos = [Perfil.ADMIN]


class CampanhaUpdateView(MetasCampanhaMixin, BaseUpdateView):
    model = Campanha
    form_class = CampanhaForm
    template_name = "doacoes/campanha_form.html"
    mensagem_sucesso = "Campanha atualizada."
    success_url = reverse_lazy("doacoes:campanha_lista")
    perfis_permitidos = [Perfil.ADMIN]


class CampanhaEncerrarView(PerfilRequiredMixin, View):
    perfis_permitidos = [Perfil.ADMIN]

    def post(self, request, *args, **kwargs):
        campanha = get_object_or_404(Campanha, pk=self.kwargs["pk"])
        if campanha.encerrada_em is None:
            campanha.encerrada_em = timezone.now()
            campanha.save(update_fields=["encerrada_em", "atualizado_em"])
            messages.success(request, "Campanha encerrada.")
        else:
            messages.info(request, "Esta campanha já foi encerrada.")
        return redirect("doacoes:campanha_editar", pk=campanha.pk)


class ReciboView(PerfilRequiredMixin, DetailView):
    """Recibo individual da doacao, em tela ou PDF."""

    model = Doacao
    template_name = "doacoes/recibo.html"
    context_object_name = "doacao"
    perfis_permitidos = QUEM_REGISTRA

    def get_queryset(self):
        return super().get_queryset().select_related("doador", "campanha", "recebido_por")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["emitido_em"] = timezone.localtime()
        contexto["emitido_por"] = self.request.user
        contexto["instituicao"] = {
            "nome": "Lar Padre José Gumercindo",
            "cnpj": "",
            "endereco": "",
        }
        responsavel = self.object.recebido_por
        contexto["responsavel_nome"] = (
            responsavel.get_full_name() or responsavel.username
            if responsavel
            else contexto["instituicao"]["nome"]
        )
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
            self.object.save(update_fields=["recibo_emitido", "atualizado_em"])
            messages.success(request, "Recibo marcado como entregue.")
        return redirect("doacoes:recibo", pk=self.object.pk)
