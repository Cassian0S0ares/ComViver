import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestMenuPorPerfil:
    def test_admin_ve_o_item_de_usuarios(self, client, usuario_admin):
        client.force_login(usuario_admin)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert "Usuários" in conteudo

    def test_tecnico_nao_ve_o_item_de_usuarios(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert "Usuários" not in conteudo

    def test_operacional_nao_ve_o_item_de_usuarios(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert "Usuários" not in conteudo

    def test_todos_veem_o_painel(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert "Painel" in conteudo

    def test_nome_do_usuario_aparece_no_cabecalho(self, client, usuario_admin):
        client.force_login(usuario_admin)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert usuario_admin.get_full_name() in conteudo
