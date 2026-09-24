from datetime import date, timedelta
from urllib.parse import urlparse

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from accounts.models import Perfil, Usuario
from core.mixins import PerfilRequiredMixin
from core.views import BaseCreateView
from escalas.forms import EscalaForm, TurnoForm
from escalas.models import Alocacao, Escala, StatusAlocacao, StatusEscala, Turno
from escalas.services import (
    agenda_do_dia, grade_da_escala, usuarios_disponiveis, voluntarios_disponiveis,
)
from voluntarios.models import StatusVoluntario, Voluntario

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
QUEM_MONTA = [Perfil.ADMIN, Perfil.OPERACIONAL]


class EscalaCalendarioView(PerfilRequiredMixin, TemplateView):
    """O menu Escalas abre diretamente o calendário da equipe."""

    template_name = "escalas/escala_grade.html"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        try:
            inicio = date.fromisoformat(self.request.GET.get("semana", ""))
            if not 1900 <= inicio.year <= 9998:
                inicio = None
        except ValueError:
            inicio = None
        contexto |= grade_da_escala(inicio=inicio)
        contexto["pode_montar"] = self.request.user.perfil in QUEM_MONTA
        contexto["turno_novo_url"] = reverse("escalas:calendario_turno_novo")
        contexto["form"] = TurnoForm(usuario=self.request.user)
        return contexto


class EscalaCreateView(BaseCreateView):
    model = Escala
    form_class = EscalaForm
    template_name = "escalas/escala_form.html"
    mensagem_sucesso = "Escala criada. Agora adicione os turnos."
    perfis_permitidos = QUEM_MONTA

    def get_success_url(self):
        return reverse("escalas:grade", args=[self.object.pk])


class EscalaGradeView(PerfilRequiredMixin, DetailView):
    """Cronograma de domingo a sábado, com horários clicáveis."""

    model = Escala
    template_name = "escalas/escala_grade.html"
    context_object_name = "escala"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        try:
            inicio = date.fromisoformat(self.request.GET.get("semana", ""))
        except ValueError:
            inicio = None
        contexto |= grade_da_escala(self.object, inicio)
        contexto["pode_montar"] = self.request.user.perfil in QUEM_MONTA
        contexto["turno_novo_url"] = reverse("escalas:turno_novo", args=[self.object.pk])
        contexto["form"] = TurnoForm(escala=self.object, usuario=self.request.user)
        return contexto


class TurnoCreateView(BaseCreateView):
    model = Turno
    form_class = TurnoForm
    template_name = "escalas/turno_form.html"
    mensagem_sucesso = "Turno adicionado à escala."
    perfis_permitidos = QUEM_MONTA

    def dispatch(self, request, *args, **kwargs):
        self.escala = get_object_or_404(Escala, pk=kwargs["pk"]) if "pk" in kwargs else None
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"escala": self.escala}

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            "data": self.request.GET.get(
                "data", self.escala.data_inicio if self.escala else timezone.localdate()
            ),
            "hora_inicio": self.request.GET.get("hora_inicio", "08:00"),
            "hora_fim": self.request.GET.get("hora_fim", "09:00"),
        })
        return initial

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "escala": self.escala,
            "voltar_url": reverse("escalas:grade", args=[self.escala.pk])
            if self.escala else reverse("escalas:lista")
            + "?semana=" + str(self.get_initial()["data"]),
        }

    def form_valid(self, form):
        pessoas = form.cleaned_data.get("responsavel") or []
        try:
            with transaction.atomic():
                bloqueadas = []
                for pessoa in pessoas:
                    pessoa = type(pessoa).objects.select_for_update().get(pk=pessoa.pk)
                    ativo = (pessoa.is_active if isinstance(pessoa, Usuario)
                             else pessoa.status == StatusVoluntario.ATIVO)
                    if not ativo:
                        raise ValidationError("Selecione um responsável ativo.")
                    bloqueadas.append(pessoa)
                escala = self.escala
                if not escala:
                    data = form.cleaned_data["data"]
                    inicio = data - timedelta(days=(data.weekday() + 1) % 7)
                    escala = Escala.objects.filter(
                        data_inicio=inicio, data_fim=inicio + timedelta(days=6)
                    ).order_by("pk").first()
                    if not escala:
                        escala = Escala.objects.create(
                            titulo=f"Semana de {inicio:%d/%m/%Y}", data_inicio=inicio,
                            data_fim=inicio + timedelta(days=6), criado_por=self.request.user,
                        )
                form.instance.escala = escala
                form.instance.criado_por = self.request.user
                self.object = form.save()
                for pessoa in bloqueadas:
                    campo = "usuario" if isinstance(pessoa, Usuario) else "voluntario"
                    alocacao = Alocacao(turno=self.object, **{campo: pessoa})
                    alocacao.full_clean()
                    alocacao.save()
        except ValidationError as erro:
            form.instance.pk = None
            form.add_error("responsavel", erro.messages)
            return self.form_invalid(form)
        messages.success(self.request, self.mensagem_sucesso)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return (
            (reverse("escalas:grade", args=[self.escala.pk])
             if self.escala else reverse("escalas:lista"))
            + f"?semana={self.object.data.isoformat()}&hora={self.object.hora_inicio.hour}"
        )


def _e_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _voltar_para_grade(request, turno) -> str:
    """Volta para a tela de onde o modal foi aberto, na semana do turno."""
    grade = reverse("escalas:grade", args=[turno.escala_id])
    atual = urlparse(request.headers.get("HX-Current-URL", "")).path
    destino = atual if atual in {grade, reverse("escalas:lista")} else grade
    return f"{destino}?semana={turno.data.isoformat()}&hora={turno.hora_inicio.hour}"


def _redirecionar(request, url):
    """Com HTMX, o navegador inteiro troca de pagina; sem ele, um 302 comum."""
    if _e_htmx(request):
        return HttpResponse(status=204, headers={"HX-Redirect": url})
    return redirect(url)


def _alocacoes_em_ordem(turno):
    return turno.alocacoes.select_related("usuario", "voluntario").order_by("criado_em", "pk")


def _pode_remover(usuario, alocacao) -> bool:
    return usuario.e_admin or alocacao.usuario_id == usuario.pk


def _contexto_detalhe(request, turno, **extra) -> dict:
    alocacoes = list(_alocacoes_em_ordem(turno))
    return {
        "turno": turno,
        "pode_gerenciar": turno.pode_ser_gerenciado_por(request.user),
        "responsaveis": [(a, _pode_remover(request.user, a)) for a in alocacoes],
        "ja_escalado": any(a.usuario_id == request.user.pk for a in alocacoes),
    } | extra


def _responder_detalhe(request, turno, erro=None):
    """Modal atualizado e, fora da banda, o bloco do turno na grade."""
    return render(request, "escalas/partials/_turno_detalhe.html",
                  _contexto_detalhe(request, turno, erro=erro, atualizar_celula=True))


class TurnoDetalheView(PerfilRequiredMixin, DetailView):
    """Detalhes do turno, exibidos somente no modal do cronograma."""

    model = Turno
    context_object_name = "turno"
    template_name = "escalas/partials/_turno_detalhe.html"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        return Turno.objects.select_related("atividade", "escala", "criado_por")

    def get(self, request, *args, **kwargs):
        if not _e_htmx(request):
            return redirect(_voltar_para_grade(request, self.get_object()))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | _contexto_detalhe(self.request, self.object)


class _GerenciarTurnoMixin(PerfilRequiredMixin):
    """Somente quem criou o turno ou um administrador altera ou exclui."""

    perfis_permitidos = TODOS_OS_PERFIS

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.turno = get_object_or_404(Turno, pk=kwargs["pk"])
        if not self.turno.pode_ser_gerenciado_por(request.user):
            raise PermissionDenied("Apenas quem criou o turno ou um administrador pode alterá-lo.")
        return super().dispatch(request, *args, **kwargs)


class TurnoUpdateView(_GerenciarTurnoMixin, View):
    def _responder(self, form):
        if not _e_htmx(self.request):
            messages.error(self.request, "Não foi possível salvar. Revise o turno e tente de novo.")
            return redirect(_voltar_para_grade(self.request, self.turno))
        return render(self.request, "escalas/partials/_turno_editar.html",
                      {"form": form, "turno": self.turno})

    def _form(self, data=None):
        # IDs proprios: o modal de edicao divide a pagina com o de criacao.
        return TurnoForm(data, instance=self.turno, escala=self.turno.escala,
                         usuario=self.request.user, auto_id="editar_%s")

    def get(self, request, pk):
        if not _e_htmx(request):
            return redirect(_voltar_para_grade(request, self.turno))
        return self._responder(self._form())

    def post(self, request, pk):
        form = self._form(request.POST)
        if not form.is_valid():
            return self._responder(form)
        try:
            with transaction.atomic():
                turno = form.save()
                # Menos vagas que pessoas: ficam as mais antigas no turno.
                excedentes = list(_alocacoes_em_ordem(turno)[turno.vagas:])
                for alocacao in excedentes:
                    alocacao.delete()
                # Mudar o horario pode encavalar quem ja estava escalado.
                for alocacao in turno.alocacoes.select_related("usuario", "voluntario"):
                    alocacao.full_clean()
        except ValidationError as erro:
            self.turno.refresh_from_db()
            form.add_error(None, erro.messages)
            return self._responder(form)
        if excedentes:
            nomes = ", ".join(a.nome_responsavel for a in excedentes)
            messages.warning(request, f"Com menos vagas, saíram do turno os mais recentes: {nomes}.")
        messages.success(request, "Turno atualizado.")
        return _redirecionar(request, _voltar_para_grade(request, turno))


class TurnoExcluirView(_GerenciarTurnoMixin, View):
    def get(self, request, pk):
        if not _e_htmx(request):
            return redirect(_voltar_para_grade(request, self.turno))
        return render(request, "escalas/partials/_turno_excluir.html", {"turno": self.turno})

    def post(self, request, pk):
        voltar = _voltar_para_grade(request, self.turno)
        with transaction.atomic():
            # Exclusao logica nao cascateia: sem isto, a pessoa continuaria
            # "ocupada" no horario de um turno que nao existe mais.
            for alocacao in self.turno.alocacoes.all():
                alocacao.delete()
            self.turno.delete()
        messages.success(request, "Turno excluído.")
        return _redirecionar(request, voltar)


class DisponiveisView(PerfilRequiredMixin, View):
    """Fragmento HTMX: quem o administrador pode colocar neste turno."""

    perfis_permitidos = [Perfil.ADMIN]

    def get(self, request, pk):
        turno = get_object_or_404(Turno, pk=pk)
        return render(
            request,
            "escalas/partials/_lista_disponiveis.html",
            {"turno": turno, "voluntarios": voluntarios_disponiveis(turno),
             "usuarios": usuarios_disponiveis(turno)},
        )


class AlocarView(PerfilRequiredMixin, View):
    """Coloca alguem no turno e devolve o modal atualizado.

    Administrador escolhe qualquer pessoa; os demais so podem se colocar.
    """

    perfis_permitidos = TODOS_OS_PERFIS

    def post(self, request, pk):
        turno = get_object_or_404(Turno, pk=pk)

        if not request.user.e_admin:
            outra_pessoa = request.POST.get("voluntario") or (
                request.POST.get("usuario") not in (None, "", str(request.user.pk))
            )
            if outra_pessoa:
                raise PermissionDenied("Você só pode adicionar a si mesmo ao turno.")
            alocacao = Alocacao(turno=turno, usuario=request.user)
        elif request.POST.get("usuario"):
            pessoa = get_object_or_404(Usuario, pk=request.POST["usuario"], is_active=True)
            alocacao = Alocacao(turno=turno, usuario=pessoa)
        else:
            pessoa = get_object_or_404(
                Voluntario, pk=request.POST.get("voluntario"), status=StatusVoluntario.ATIVO
            )
            alocacao = Alocacao(turno=turno, voluntario=pessoa)

        try:
            with transaction.atomic():
                # Trava o turno: dois cliques simultaneos nao estouram as vagas.
                turno = Turno.objects.select_for_update().get(pk=turno.pk)
                if turno.alocacoes.count() >= turno.vagas:
                    raise ValidationError(
                        f"O limite de {turno.vagas} vaga{'s' if turno.vagas != 1 else ''} "
                        "já foi atingido. Edite o turno para aumentar as vagas."
                    )
                alocacao.full_clean()
                alocacao.save()
        except ValidationError as erro:
            # A mensagem contem o nome da pessoa, que e dado de entrada: vai
            # pelo template, com escape, e nunca montada em HTML a mao.
            return _responder_detalhe(request, turno, erro=erro.messages)
        return _responder_detalhe(request, turno)


class DesalocarView(PerfilRequiredMixin, View):
    """Administrador tira qualquer pessoa; os demais so a si mesmos."""

    perfis_permitidos = TODOS_OS_PERFIS

    def post(self, request, pk):
        alocacao = get_object_or_404(Alocacao, pk=pk)
        if not _pode_remover(request.user, alocacao):
            raise PermissionDenied("Você só pode sair do turno, não tirar outra pessoa.")
        turno = alocacao.turno
        alocacao.delete()
        return _responder_detalhe(request, turno)


class ConcluirView(PerfilRequiredMixin, View):
    """Marca ou desmarca um item do to-do pessoal ("Meu dia", no painel).

    Feito vira CONFIRMADO ("Compareceu"): cada pessoa so marca o proprio
    turno e so a partir do dia dele.
    """

    perfis_permitidos = TODOS_OS_PERFIS

    def post(self, request, pk):
        item = get_object_or_404(
            Alocacao.objects.select_related("turno__atividade"),
            pk=pk, usuario=request.user, turno__deleted_at__isnull=True,
        )
        painel = f"{reverse('core:painel')}?dia={item.turno.data.isoformat()}"
        if item.turno.data > timezone.localdate():
            if _e_htmx(request):
                return HttpResponse("Este turno ainda não começou.", status=400)
            messages.error(request, "Só dá para marcar o turno a partir do dia dele.")
            return redirect(painel)
        item.status = (StatusAlocacao.PREVISTO if item.status == StatusAlocacao.CONFIRMADO
                       else StatusAlocacao.CONFIRMADO)
        item.save(update_fields=["status", "atualizado_em"])
        if not _e_htmx(request):
            return redirect(painel)
        agenda = agenda_do_dia(request.user, item.turno.data)
        item = next(a for a in agenda if a.pk == item.pk)
        return render(request, "escalas/partials/_agenda_item.html", {
            "item": item, "oob_progresso": True, "agenda": agenda,
            "agenda_feitos": sum(a.feito for a in agenda),
        })


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
