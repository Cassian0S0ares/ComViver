from datetime import date

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView, UpdateView
from formtools.wizard.views import SessionWizardView

from accounts.models import AcaoFicha, LogAcessoFicha, Perfil
from acolhidos import estatisticas
from acolhidos.forms import (
    DesligamentoForm,
    EtapaAcolhimentoCadastroForm,
    EtapaAcolhimentoForm,
    EtapaIdentificacaoForm,
    EtapaResponsavelForm,
    EtapaSaudeEscolaForm,
    MedicacaoForm,
    VinculoForm,
)
from acolhidos.models import (
    Acolhido,
    Escolaridade,
    FichaAcolhimento,
    Medicacao,
    Responsavel,
    StatusAcolhido,
    VinculoFamiliar,
)
from core.mixins import PerfilRequiredMixin, RegistraAcessoFichaMixin
from core.views import BaseCreateView, BaseListView, BaseUpdateView

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
EQUIPE_TECNICA = [Perfil.ADMIN, Perfil.TECNICO]
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


class EstatisticasView(PerfilRequiredMixin, TemplateView):
    """Visao geral dos acolhidos: so contagens, nenhum nome.

    Agrega saude e tempo de acolhimento, por isso fica com a equipe tecnica.
    """

    template_name = "acolhidos/estatisticas.html"
    perfis_permitidos = EQUIPE_TECNICA

    def _situacao(self) -> str:
        situacao = self.request.GET.get("situacao", StatusAcolhido.ACOLHIDO)
        return situacao if situacao in dict(SITUACOES) else StatusAcolhido.ACOLHIDO

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        situacao = self._situacao()
        acolhidos = Acolhido.objects.select_related("ficha", "saude")
        if situacao != "TODOS":
            acolhidos = acolhidos.filter(status=situacao)
        contexto["situacao"] = situacao
        contexto["situacoes"] = SITUACOES
        contexto["estatisticas"] = estatisticas.calcular(acolhidos)
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
            # Medicacao encerrada e historico de saude: fica com a equipe
            # tecnica, fora do bloco de cuidado diario.
            contexto["medicacoes_encerradas"] = acolhido.medicacoes.exclude(
                pk__in=contexto["medicacoes_em_vigor"].values("pk")
            ).order_by("-inicio")

        return contexto


ETAPAS = [
    ("identificacao", EtapaIdentificacaoForm),
    ("acolhimento", EtapaAcolhimentoCadastroForm),
    ("saude", EtapaSaudeEscolaForm),
    ("responsavel", EtapaResponsavelForm),
]

TITULOS_ETAPA = {
    "identificacao": "Identificação",
    "acolhimento": "Acolhimento",
    "saude": "Saúde e escola",
    "responsavel": "Responsável",
}


class AcolhimentoWizard(PerfilRequiredMixin, SessionWizardView):
    """Cadastro de novo acolhimento em quatro etapas.

    Sao cerca de 30 campos, e a etapa 2 e restrita a equipe tecnica. O
    rascunho fica na sessao: uma interrupcao no meio nao descarta o trabalho.

    Nada e gravado antes da ultima etapa — acolhido sem ficha nem responsavel
    seria pior que nenhum registro.
    """

    form_list = ETAPAS
    template_name = "acolhidos/acolhido_wizard.html"
    perfis_permitidos = EQUIPE_TECNICA
    # Fora de MEDIA_ROOT de proposito: a rota /media/ entrega o que estiver la
    # a qualquer usuario logado, e a foto do rascunho ainda tem o nome original.
    file_storage = FileSystemStorage(location=settings.ASSISTENTE_TEMP_DIR)

    def get_context_data(self, form, **kwargs):
        contexto = super().get_context_data(form=form, **kwargs)
        atual = self.steps.index
        contexto["etapas"] = [
            {
                "numero": i + 1,
                "titulo": TITULOS_ETAPA[nome],
                "atual": i == atual,
                "feita": i < atual,
            }
            for i, nome in enumerate(self.steps.all)
        ]
        contexto["titulo_atual"] = TITULOS_ETAPA[self.steps.current]
        return contexto

    @transaction.atomic
    def done(self, form_list, form_dict, **kwargs):
        acolhido = form_dict["identificacao"].save(commit=False)
        acolhido.criado_por = self.request.user
        acolhido.save()

        ficha = form_dict["acolhimento"].save(commit=False)
        ficha.acolhido = acolhido
        ficha.criado_por = self.request.user
        ficha.save()

        etapa_saude = form_dict["saude"]
        saude = etapa_saude.save(commit=False)
        saude.acolhido = acolhido
        saude.criado_por = self.request.user
        saude.save()

        if etapa_saude.cleaned_data.get("escola"):
            Escolaridade.objects.create(
                acolhido=acolhido,
                escola=etapa_saude.cleaned_data["escola"],
                serie=etapa_saude.cleaned_data.get("serie", ""),
                turno=etapa_saude.cleaned_data.get("turno", ""),
                ano_letivo=date.today().year,
                criado_por=self.request.user,
            )

        dados_responsavel = form_dict["responsavel"].cleaned_data
        responsavel = Responsavel.objects.create(
            nome=dados_responsavel["nome"],
            cpf=dados_responsavel.get("cpf", ""),
            telefone=dados_responsavel.get("telefone", ""),
            criado_por=self.request.user,
        )
        VinculoFamiliar.objects.create(
            acolhido=acolhido,
            responsavel=responsavel,
            parentesco=dados_responsavel["parentesco"],
            e_guardiao=dados_responsavel.get("e_guardiao", False),
            autorizado_visita=dados_responsavel.get("autorizado_visita", False),
            autorizado_retirar=dados_responsavel.get("autorizado_retirar", False),
            criado_por=self.request.user,
        )

        messages.success(self.request, f"Acolhimento de {acolhido.nome_exibicao} registrado.")
        return redirect("acolhidos:detalhe", pk=acolhido.pk)


def _registrar_alteracao(usuario, acolhido):
    LogAcessoFicha.registrar(usuario, acolhido, AcaoFicha.EDIT)


class AcolhidoUpdateView(BaseUpdateView):
    model = Acolhido
    form_class = EtapaIdentificacaoForm
    template_name = "acolhidos/acolhido_form.html"
    context_object_name = "acolhido"
    mensagem_sucesso = "Dados do acolhido atualizados."
    perfis_permitidos = EQUIPE_TECNICA

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop("usuario", None)  # EtapaIdentificacaoForm nao recorta campos por perfil
        return kwargs

    def form_valid(self, form):
        resposta = super().form_valid(form)
        _registrar_alteracao(self.request.user, self.object)
        return resposta

    def get_success_url(self):
        return reverse("acolhidos:detalhe", args=[self.object.pk])


class FichaUpdateView(PerfilRequiredMixin, UpdateView):
    model = FichaAcolhimento
    form_class = EtapaAcolhimentoForm
    template_name = "acolhidos/ficha_form.html"
    perfis_permitidos = EQUIPE_TECNICA

    def get_object(self, queryset=None):
        self.acolhido = get_object_or_404(Acolhido, pk=self.kwargs["pk"])
        # Sem ficha, o formulario parte de um objeto ainda nao salvo: abrir a
        # tela nao pode gravar uma ficha com data de entrada inventada.
        return getattr(self.acolhido, "ficha", None) or FichaAcolhimento(acolhido=self.acolhido)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"acolhido": self.acolhido}

    def form_valid(self, form):
        if not form.instance.pk:
            form.instance.criado_por = self.request.user
        resposta = super().form_valid(form)
        _registrar_alteracao(self.request.user, self.acolhido)
        messages.success(self.request, "Ficha de acolhimento atualizada.")
        return resposta

    def get_success_url(self):
        return reverse("acolhidos:detalhe", args=[self.acolhido.pk])


class DesligamentoView(PerfilRequiredMixin, FormView):
    template_name = "acolhidos/acolhido_desligar.html"
    form_class = DesligamentoForm
    perfis_permitidos = EQUIPE_TECNICA

    def dispatch(self, request, *args, **kwargs):
        self.acolhido = get_object_or_404(Acolhido, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.acolhido.status == StatusAcolhido.DESLIGADO:
            return self._ja_desligado()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.acolhido.status == StatusAcolhido.DESLIGADO:
            return self._ja_desligado()
        return super().post(request, *args, **kwargs)

    def _ja_desligado(self):
        messages.info(self.request, f"{self.acolhido.nome_exibicao} já está desligado.")
        return redirect("acolhidos:detalhe", pk=self.acolhido.pk)

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"acolhido": self.acolhido}

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"acolhido": self.acolhido}

    @transaction.atomic
    def form_valid(self, form):
        data = form.cleaned_data["data_desligamento"]
        # Sem ficha, a entrada e registrada como o proprio dia do desligamento:
        # qualquer outra data seria inventada.
        ficha = getattr(self.acolhido, "ficha", None) or FichaAcolhimento(
            acolhido=self.acolhido, data_entrada=data, criado_por=self.request.user
        )
        ficha.data_desligamento = data
        ficha.destino = form.cleaned_data["destino"]
        ficha.observacao_desligamento = form.cleaned_data.get("observacao", "")
        ficha.save()

        self.acolhido.status = StatusAcolhido.DESLIGADO
        self.acolhido.save(update_fields=["status", "atualizado_em"])

        _registrar_alteracao(self.request.user, self.acolhido)
        messages.success(
            self.request,
            f"Desligamento de {self.acolhido.nome_exibicao} registrado. "
            "O histórico permanece consultável.",
        )
        return redirect("acolhidos:detalhe", pk=self.acolhido.pk)


class _VinculoMixin:
    template_name = "acolhidos/vinculo_form.html"
    perfis_permitidos = EQUIPE_TECNICA

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"acolhido": self.acolhido}

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"acolhido": self.acolhido}

    def form_valid(self, form):
        resposta = super().form_valid(form)
        _registrar_alteracao(self.request.user, self.acolhido)
        return resposta

    def get_success_url(self):
        return reverse("acolhidos:detalhe", args=[self.acolhido.pk])


class VinculoCreateView(_VinculoMixin, BaseCreateView):
    model = VinculoFamiliar
    form_class = VinculoForm
    mensagem_sucesso = "Vínculo familiar registrado."

    def dispatch(self, request, *args, **kwargs):
        self.acolhido = get_object_or_404(Acolhido, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)


class VinculoUpdateView(_VinculoMixin, BaseUpdateView):
    model = VinculoFamiliar
    form_class = VinculoForm
    mensagem_sucesso = "Vínculo familiar atualizado."

    def dispatch(self, request, *args, **kwargs):
        self.acolhido = get_object_or_404(VinculoFamiliar, pk=kwargs["pk"]).acolhido
        return super().dispatch(request, *args, **kwargs)


class _MedicacaoMixin:
    """Cadastro de medicacao: escrita so para a equipe tecnica (spec 5.1)."""

    model = Medicacao
    form_class = MedicacaoForm
    template_name = "acolhidos/medicacao_form.html"
    perfis_permitidos = EQUIPE_TECNICA

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"acolhido": self.acolhido}

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"acolhido": self.acolhido}

    def form_valid(self, form):
        resposta = super().form_valid(form)
        _registrar_alteracao(self.request.user, self.acolhido)
        return resposta

    def get_success_url(self):
        return reverse("acolhidos:detalhe", args=[self.acolhido.pk])


class MedicacaoCreateView(_MedicacaoMixin, BaseCreateView):
    mensagem_sucesso = "Medicação registrada."

    def dispatch(self, request, *args, **kwargs):
        self.acolhido = get_object_or_404(Acolhido, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)


class MedicacaoUpdateView(_MedicacaoMixin, BaseUpdateView):
    mensagem_sucesso = "Medicação atualizada."

    def dispatch(self, request, *args, **kwargs):
        self.acolhido = get_object_or_404(Medicacao, pk=kwargs["pk"]).acolhido
        return super().dispatch(request, *args, **kwargs)


class MedicacaoRemoverView(PerfilRequiredMixin, View):
    """Remocao de lancamento errado, em pagina propria e por POST.

    A exclusao e logica: o historico de medicacao de uma crianca nao pode ter
    lacuna, mesmo quando a linha saiu da tela.
    """

    template_name = "acolhidos/medicacao_remover.html"
    perfis_permitidos = EQUIPE_TECNICA

    def dispatch(self, request, *args, **kwargs):
        self.medicacao = get_object_or_404(Medicacao, pk=kwargs["pk"])
        self.acolhido = self.medicacao.acolhido
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {"medicacao": self.medicacao, "acolhido": self.acolhido},
        )

    def post(self, request, *args, **kwargs):
        self.medicacao.delete()
        _registrar_alteracao(request.user, self.acolhido)
        messages.success(request, f"{self.medicacao.nome} removido da ficha.")
        return redirect("acolhidos:detalhe", pk=self.acolhido.pk)


SITUACOES_MEDICACAO = [
    ("EM_USO", "Em uso hoje"),
    ("ENCERRADAS", "Encerradas"),
    ("TODAS", "Todas"),
]


class MedicacaoListView(BaseListView):
    """Medicacoes da casa inteira, para o plantao consultar de uma vez.

    Aberta a toda a equipe: e a lista de quem administra o remedio. Mostra
    apenas crianca, medicamento, dose, horario e datas — nada da ficha
    sigilosa (spec 5.1).
    """

    model = Medicacao
    template_name = "acolhidos/medicacao_list.html"
    context_object_name = "medicacoes"
    campos_busca = ["nome", "acolhido__nome", "acolhido__nome_social"]
    perfis_permitidos = TODOS_OS_PERFIS
    paginate_by = 50

    def _situacao(self) -> str:
        situacao = self.request.GET.get("situacao", "EM_USO")
        return situacao if situacao in dict(SITUACOES_MEDICACAO) else "EM_USO"

    def _da_casa(self):
        """Somente quem esta acolhido hoje: desligado nao entra no plantao."""
        return Medicacao.objects.filter(
            acolhido__status=StatusAcolhido.ACOLHIDO, acolhido__deleted_at__isnull=True
        )

    def _em_uso(self):
        return self._da_casa().filter(pk__in=Medicacao.em_vigor.values("pk"))

    def get_queryset(self):
        # A busca por crianca ou medicamento ja vem da BaseListView.
        qs = (
            super()
            .get_queryset()
            .filter(acolhido__status=StatusAcolhido.ACOLHIDO, acolhido__deleted_at__isnull=True)
        )
        situacao = self._situacao()
        if situacao == "EM_USO":
            qs = qs.filter(pk__in=Medicacao.em_vigor.values("pk"))
        elif situacao == "ENCERRADAS":
            qs = qs.exclude(pk__in=Medicacao.em_vigor.values("pk"))
        return qs.select_related("acolhido").order_by("acolhido__nome", "nome", "pk")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        em_uso = self._em_uso()

        # Quantas criancas tomam cada medicamento hoje. A mesma crianca com dois
        # horarios do mesmo remedio conta uma vez.
        contexto["resumo"] = [
            {"nome": linha["nome"], "criancas": linha["criancas"]}
            for linha in em_uso.values("nome")
            .annotate(criancas=Count("acolhido", distinct=True))
            .order_by("-criancas", "nome")
        ]
        contexto["total_criancas"] = em_uso.values("acolhido").distinct().count()
        contexto["total_medicamentos"] = em_uso.values("nome").distinct().count()
        contexto["situacao"] = self._situacao()
        contexto["situacoes"] = SITUACOES_MEDICACAO
        return contexto
