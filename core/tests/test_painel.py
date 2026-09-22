import pytest
from django.urls import reverse

from accounts.factories import UsuarioFactory
from accounts.models import Perfil

pytestmark = pytest.mark.django_db


class TestPainel:
    def test_admin_ve_o_cartao_de_usuarios_ativos(self, client, usuario_admin):
        UsuarioFactory.create_batch(3, perfil=Perfil.OPERACIONAL)
        client.force_login(usuario_admin)
        cartoes = client.get(reverse("core:painel")).context["cartoes"]
        titulos = [c["titulo"] for c in cartoes]
        assert "Usuários ativos" in titulos

    def test_cartao_conta_apenas_usuarios_ativos(self, client, usuario_admin):
        UsuarioFactory.create_batch(2, perfil=Perfil.OPERACIONAL)
        UsuarioFactory(perfil=Perfil.OPERACIONAL, is_active=False)
        client.force_login(usuario_admin)
        cartoes = client.get(reverse("core:painel")).context["cartoes"]
        cartao = next(c for c in cartoes if c["titulo"] == "Usuários ativos")
        assert cartao["valor"] == 3  # os 2 criados + o proprio admin

    def test_operacional_nao_ve_o_cartao_de_usuarios(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        cartoes = client.get(reverse("core:painel")).context["cartoes"]
        assert "Usuários ativos" not in [c["titulo"] for c in cartoes]

    def test_painel_sauda_o_usuario_pelo_nome(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert usuario_tecnico.first_name in conteudo
