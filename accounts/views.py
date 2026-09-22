from django.contrib import messages
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from accounts.forms import (
    EsqueciSenhaForm,
    LoginForm,
    NovaSenhaForm,
    TrocaSenhaForm,
    UsuarioCreationForm,
    UsuarioForm,
)
from accounts.models import Perfil, Usuario
from core.mixins import PerfilRequiredMixin


class EntrarView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class SairView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class EsqueciSenhaView(PasswordResetView):
    template_name = "accounts/esqueci_senha.html"
    form_class = EsqueciSenhaForm
    email_template_name = "accounts/email/redefinir_senha.txt"
    subject_template_name = "accounts/email/redefinir_senha_assunto.txt"
    success_url = reverse_lazy("accounts:esqueci_senha_enviado")

    # Sem limite, qualquer pessoa na pagina publica poderia encher a caixa de
    # entrada de alguem da equipe com links de redefinicao.
    LIMITE_DE_PEDIDOS = 3
    JANELA_EM_SEGUNDOS = 15 * 60

    def form_valid(self, form):
        chave = f"esqueci-senha:{form.cleaned_data['email']}"
        cache.add(chave, 0, self.JANELA_EM_SEGUNDOS)
        if cache.incr(chave) > self.LIMITE_DE_PEDIDOS:
            # Mesma resposta de sucesso: o limite nao pode virar forma de
            # descobrir quais e-mails estao cadastrados.
            return redirect(self.success_url)
        return super().form_valid(form)


class EsqueciSenhaEnviadoView(PasswordResetDoneView):
    template_name = "accounts/esqueci_senha_enviado.html"


class RedefinirSenhaView(PasswordResetConfirmView):
    template_name = "accounts/redefinir_senha.html"
    form_class = NovaSenhaForm
    success_url = reverse_lazy("accounts:redefinir_senha_concluido")


class RedefinirSenhaConcluidoView(PasswordResetCompleteView):
    template_name = "accounts/redefinir_senha_concluido.html"


class TrocarSenhaView(PasswordChangeView):
    template_name = "accounts/trocar_senha.html"
    form_class = TrocaSenhaForm
    success_url = reverse_lazy("core:painel")

    def form_valid(self, form):
        resposta = super().form_valid(form)
        self.request.user.precisa_trocar_senha = False
        self.request.user.save(update_fields=["precisa_trocar_senha"])
        return resposta


class UsuarioListView(PerfilRequiredMixin, ListView):
    model = Usuario
    template_name = "accounts/usuario_list.html"
    context_object_name = "usuarios"
    perfis_permitidos = [Perfil.ADMIN]
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        busca = self.request.GET.get("q", "").strip()
        if busca:
            qs = qs.filter(
                Q(first_name__icontains=busca)
                | Q(last_name__icontains=busca)
                | Q(email__icontains=busca)
            )
        perfil = self.request.GET.get("perfil", "")
        if perfil in Perfil.values:
            qs = qs.filter(perfil=perfil)
        status = self.request.GET.get("status", "")
        if status in {"ativo", "inativo"}:
            qs = qs.filter(is_active=status == "ativo")
        return qs.order_by("first_name", "last_name", "username", "pk")

    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get("page"))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["perfis"] = Perfil.choices
        context["total_ativos"] = Usuario.objects.filter(is_active=True).count()
        query = self.request.GET.copy()
        query.pop("page", None)
        context["filtros_url"] = query.urlencode()
        return context


class UsuarioFormViewMixin:
    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "actor": self.request.user}


class UsuarioCreateView(PerfilRequiredMixin, UsuarioFormViewMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreationForm
    template_name = "accounts/usuario_form.html"
    success_url = reverse_lazy("accounts:usuario_list")
    perfis_permitidos = [Perfil.ADMIN]

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(
            self.request,
            f"Usuário {self.object.get_full_name()} criado. "
            "Informe a senha provisória; ele deverá trocá-la no primeiro acesso.",
        )
        return resposta


class UsuarioUpdateView(PerfilRequiredMixin, UsuarioFormViewMixin, UpdateView):
    model = Usuario
    form_class = UsuarioForm
    template_name = "accounts/usuario_form.html"
    success_url = reverse_lazy("accounts:usuario_list")
    perfis_permitidos = [Perfil.ADMIN]

    def form_valid(self, form):
        messages.success(self.request, "Dados do usuário atualizados.")
        return super().form_valid(form)


class UsuarioDesativarView(PerfilRequiredMixin, View):
    """Desativa o acesso. Nunca apaga o registro: o historico de quem
    cadastrou cada doacao e ficha precisa continuar resolvivel."""

    perfis_permitidos = [Perfil.ADMIN]

    def get(self, request, pk):
        return render(
            request,
            "accounts/usuario_confirmar_desativacao.html",
            {
                "alvo": get_object_or_404(Usuario, pk=pk),
            },
        )

    def post(self, request, pk):
        alvo = get_object_or_404(Usuario, pk=pk)
        if alvo.pk == request.user.pk:
            messages.error(request, "Você não pode desativar o seu próprio acesso.")
        else:
            alvo.is_active = False
            alvo.save(update_fields=["is_active"])
            messages.success(request, f"Acesso de {alvo.get_full_name()} desativado.")
        return redirect("accounts:usuario_list")
