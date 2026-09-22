from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.shortcuts import redirect
from django.views.generic import DetailView
from formtools.wizard.views import SessionWizardView

from accounts.models import Perfil
from acolhidos.forms import (
    EtapaAcolhimentoForm,
    EtapaIdentificacaoForm,
    EtapaResponsavelForm,
    EtapaSaudeEscolaForm,
)
from acolhidos.models import (
    Acolhido,
    Escolaridade,
    Medicacao,
    Responsavel,
    StatusAcolhido,
    VinculoFamiliar,
)
from core.mixins import PerfilRequiredMixin, RegistraAcessoFichaMixin
from core.views import BaseListView

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


ETAPAS = [
    ("identificacao", EtapaIdentificacaoForm),
    ("acolhimento", EtapaAcolhimentoForm),
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
                ano_letivo=etapa_saude.cleaned_data["ano_letivo"],
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
