import pytest

from accounts.models import Perfil, Usuario

pytestmark = pytest.mark.django_db


class TestUsuario:
    def test_cria_usuario_com_perfil(self):
        usuario = Usuario.objects.create_user(
            username="maria", password="senha-forte-123", perfil=Perfil.TECNICO
        )
        assert usuario.perfil == Perfil.TECNICO

    def test_perfil_padrao_e_operacional(self):
        usuario = Usuario.objects.create_user(username="joao", password="senha-forte-123")
        assert usuario.perfil == Perfil.OPERACIONAL

    def test_str_mostra_nome_e_perfil(self):
        usuario = Usuario.objects.create_user(
            username="maria",
            first_name="Maria",
            last_name="Silva",
            password="senha-forte-123",
            perfil=Perfil.ADMIN,
        )
        assert str(usuario) == "Maria Silva (Administrador)"

    def test_str_usa_username_quando_sem_nome(self):
        usuario = Usuario.objects.create_user(
            username="maria", password="senha-forte-123", perfil=Perfil.ADMIN
        )
        assert str(usuario) == "maria (Administrador)"

    @pytest.mark.parametrize(
        "perfil,e_admin,e_tecnico,e_operacional",
        [
            (Perfil.ADMIN, True, False, False),
            (Perfil.TECNICO, False, True, False),
            (Perfil.OPERACIONAL, False, False, True),
        ],
    )
    def test_propriedades_de_perfil(self, perfil, e_admin, e_tecnico, e_operacional):
        usuario = Usuario.objects.create_user(
            username="teste", password="senha-forte-123", perfil=perfil
        )
        assert usuario.e_admin is e_admin
        assert usuario.e_tecnico is e_tecnico
        assert usuario.e_operacional is e_operacional

    @pytest.mark.parametrize(
        "perfil,esperado",
        [(Perfil.ADMIN, True), (Perfil.TECNICO, True), (Perfil.OPERACIONAL, False)],
    )
    def test_pode_ver_ficha_completa(self, perfil, esperado):
        """Sigilo do art. 143 do ECA: Operacional nao acessa ficha completa."""
        usuario = Usuario.objects.create_user(
            username="teste", password="senha-forte-123", perfil=perfil
        )
        assert usuario.pode_ver_ficha_completa() is esperado

    def test_usuario_novo_precisa_trocar_senha(self):
        usuario = Usuario.objects.create_user(username="novo", password="senha-forte-123")
        assert usuario.precisa_trocar_senha is True

    def test_superusuario_nao_precisa_trocar_senha(self):
        usuario = Usuario.objects.create_superuser(username="root", password="senha-forte-123")
        assert usuario.precisa_trocar_senha is False
        assert usuario.perfil == Perfil.ADMIN
