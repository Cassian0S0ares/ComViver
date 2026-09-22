import pytest
from django.urls import reverse

from accounts.factories import UsuarioFactory
from accounts.models import Perfil, Usuario

pytestmark = pytest.mark.django_db


class TestAcessoAGestaoDeUsuarios:
    @pytest.mark.parametrize("rota", ["accounts:usuario_list", "accounts:usuario_novo"])
    def test_tecnico_recebe_403(self, client, usuario_tecnico, rota):
        client.force_login(usuario_tecnico)
        assert client.get(reverse(rota)).status_code == 403

    @pytest.mark.parametrize("rota", ["accounts:usuario_list", "accounts:usuario_novo"])
    def test_operacional_recebe_403(self, client, usuario_operacional, rota):
        client.force_login(usuario_operacional)
        assert client.get(reverse(rota)).status_code == 403

    def test_admin_acessa(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("accounts:usuario_list")).status_code == 200


class TestCriarUsuario:
    def test_admin_cria_usuario(self, client, usuario_admin):
        client.force_login(usuario_admin)
        resposta = client.post(
            reverse("accounts:usuario_novo"),
            {
                "first_name": "Joana",
                "last_name": "Pereira",
                "email": "joana@exemplo.org",
                "telefone": "35999990000",
                "perfil": Perfil.TECNICO,
                "password1": "senha-provisoria-789",
                "password2": "senha-provisoria-789",
            },
        )
        assert resposta.status_code == 302
        novo = Usuario.objects.get(email="joana@exemplo.org")
        assert novo.perfil == Perfil.TECNICO
        assert novo.precisa_trocar_senha is True
        assert novo.username == "joana@exemplo.org"

    def test_usuario_criado_entra_no_grupo_certo(self, client, usuario_admin):
        client.force_login(usuario_admin)
        client.post(
            reverse("accounts:usuario_novo"),
            {
                "first_name": "Joana",
                "last_name": "Pereira",
                "email": "joana@exemplo.org",
                "telefone": "",
                "perfil": Perfil.TECNICO,
                "password1": "senha-provisoria-789",
                "password2": "senha-provisoria-789",
            },
        )
        novo = Usuario.objects.get(email="joana@exemplo.org")
        assert novo.groups.filter(name="Técnico").exists()

    def test_email_repetido_mostra_erro(self, client, usuario_admin):
        UsuarioFactory(email="joana@exemplo.org")
        client.force_login(usuario_admin)
        resposta = client.post(
            reverse("accounts:usuario_novo"),
            {
                "first_name": "Joana",
                "last_name": "Pereira",
                "email": "Joana@Exemplo.org",
                "telefone": "",
                "perfil": Perfil.TECNICO,
                "password1": "senha-provisoria-789",
                "password2": "senha-provisoria-789",
            },
        )
        assert resposta.status_code == 200
        assert "Já existe um usuário com este e-mail." in resposta.content.decode()


class TestEmailObrigatorio:
    def test_criar_sem_email_mostra_erro(self, client, usuario_admin):
        client.force_login(usuario_admin)
        resposta = client.post(
            reverse("accounts:usuario_novo"),
            {
                "first_name": "Joana",
                "last_name": "Pereira",
                "email": "",
                "telefone": "",
                "perfil": Perfil.TECNICO,
                "password1": "senha-provisoria-789",
                "password2": "senha-provisoria-789",
            },
        )
        assert resposta.status_code == 200
        assert not Usuario.objects.filter(first_name="Joana").exists()


class TestEditarUsuario:
    def test_admin_troca_o_perfil(self, client, usuario_admin):
        alvo = UsuarioFactory(perfil=Perfil.OPERACIONAL)
        client.force_login(usuario_admin)
        client.post(
            reverse("accounts:usuario_editar", args=[alvo.pk]),
            {
                "first_name": alvo.first_name,
                "last_name": alvo.last_name,
                "email": alvo.email,
                "telefone": "",
                "perfil": Perfil.TECNICO,
                "is_active": "on",
            },
        )
        alvo.refresh_from_db()
        assert alvo.perfil == Perfil.TECNICO
        assert alvo.username == alvo.email
        assert alvo.groups.filter(name="Técnico").exists()


class TestDesativarUsuario:
    def test_desativar_nao_apaga_o_registro(self, client, usuario_admin):
        alvo = UsuarioFactory(perfil=Perfil.OPERACIONAL)
        client.force_login(usuario_admin)
        client.post(reverse("accounts:usuario_desativar", args=[alvo.pk]))
        alvo.refresh_from_db()
        assert alvo.is_active is False
        assert Usuario.objects.filter(pk=alvo.pk).exists()

    def test_admin_nao_desativa_a_si_mesmo(self, client, usuario_admin):
        client.force_login(usuario_admin)
        resposta = client.post(reverse("accounts:usuario_desativar", args=[usuario_admin.pk]))
        usuario_admin.refresh_from_db()
        assert usuario_admin.is_active is True
        assert resposta.status_code == 302
