import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from accounts.factories import UsuarioFactory
from accounts.forms import UsuarioCreationForm, UsuarioForm
from accounts.models import Perfil

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("form_class", [UsuarioCreationForm, UsuarioForm])
def test_formulario_recusa_operador_sem_permissao(form_class, usuario_operacional):
    with pytest.raises(PermissionDenied):
        form_class(actor=usuario_operacional)


@pytest.mark.parametrize("perfil", [Perfil.TECNICO, Perfil.OPERACIONAL])
@pytest.mark.parametrize("operacao", ["usuario_editar", "usuario_desativar"])
def test_post_forjado_nao_altera_usuario(client, perfil, operacao):
    actor = UsuarioFactory(perfil=perfil)
    alvo = UsuarioFactory(perfil=Perfil.ADMIN)
    client.force_login(actor)
    response = client.post(
        reverse(f"accounts:{operacao}", args=[alvo.pk]),
        {
            "username": alvo.username,
            "perfil": Perfil.OPERACIONAL,
        },
    )
    assert response.status_code == 403
    alvo.refresh_from_db()
    assert alvo.is_active and alvo.perfil == Perfil.ADMIN


def test_edicao_nao_desativa_proprio_admin(client, usuario_admin):
    client.force_login(usuario_admin)
    response = client.post(
        reverse("accounts:usuario_editar", args=[usuario_admin.pk]),
        {
            "username": usuario_admin.username,
            "perfil": Perfil.ADMIN,
        },
    )
    assert response.status_code == 200
    usuario_admin.refresh_from_db()
    assert usuario_admin.is_active
    assert "Você não pode desativar" in response.content.decode()


def test_edicao_nao_remove_proprio_perfil_admin(client, usuario_admin):
    client.force_login(usuario_admin)
    response = client.post(
        reverse("accounts:usuario_editar", args=[usuario_admin.pk]),
        {
            "username": usuario_admin.username,
            "perfil": Perfil.OPERACIONAL,
            "is_active": "on",
        },
    )
    assert response.status_code == 200
    usuario_admin.refresh_from_db()
    assert usuario_admin.perfil == Perfil.ADMIN


def test_admin_django_recusa_staff_sem_superusuario(client, usuario_admin):
    usuario_admin.is_staff = True
    usuario_admin.save()
    client.force_login(usuario_admin)
    assert client.get("/admin/").status_code == 302


def test_desativacao_exige_post(client, usuario_admin):
    alvo = UsuarioFactory()
    client.force_login(usuario_admin)
    response = client.get(reverse("accounts:usuario_desativar", args=[alvo.pk]))
    assert response.status_code == 200
    alvo.refresh_from_db()
    assert alvo.is_active


def test_sessao_de_usuario_desativado_perde_acesso(client, usuario_operacional):
    client.force_login(usuario_operacional)
    usuario_operacional.is_active = False
    usuario_operacional.save()
    assert client.get(reverse("core:painel")).status_code == 302


def test_filtros_e_paginacao_fora_do_intervalo(client, usuario_admin):
    UsuarioFactory(first_name="Teste específico", perfil=Perfil.TECNICO)
    UsuarioFactory(first_name="Teste específico", perfil=Perfil.OPERACIONAL)
    client.force_login(usuario_admin)
    response = client.get(
        reverse("accounts:usuario_list"),
        {
            "q": "Teste específico",
            "perfil": Perfil.TECNICO,
            "status": "ativo",
            "page": 99,
        },
    )
    assert response.status_code == 200
    assert response.context["paginator"].count == 1
    assert response.context["page_obj"].number == 1


def test_login_nao_redireciona_para_site_externo(client):
    UsuarioFactory(email="redirecionamento@exemplo.org", password="teste-senha-123")
    response = client.post(
        reverse("accounts:login"),
        {
            "username": "redirecionamento@exemplo.org",
            "password": "teste-senha-123",
            "next": "https://example.com/",
        },
    )
    assert response.url == reverse("core:painel")


def test_troca_obrigatoria_tambem_bloqueia_admin(client):
    usuario = UsuarioFactory(is_superuser=True, is_staff=True, precisa_trocar_senha=True)
    client.force_login(usuario)
    assert client.get("/admin/").url == reverse("accounts:trocar_senha")
