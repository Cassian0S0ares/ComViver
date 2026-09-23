import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestPermissoes:
    @pytest.mark.parametrize(
        "fixture_usuario", ["usuario_admin", "usuario_tecnico", "usuario_operacional"]
    )
    def test_todos_veem_a_lista(self, client, request, fixture_usuario):
        client.force_login(request.getfixturevalue(fixture_usuario))
        assert client.get(reverse("voluntarios:lista")).status_code == 200

    def test_tecnico_nao_cadastra_voluntario(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        assert client.get(reverse("voluntarios:novo")).status_code == 403

    def test_operacional_cadastra_voluntario(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get(reverse("voluntarios:novo")).status_code == 200

    def test_so_admin_cadastra_funcao(self, client, usuario_operacional):
        """Tabela de apoio: aberta a todos, vira lista de duplicatas com
        grafias diferentes."""
        client.force_login(usuario_operacional)
        assert client.get(reverse("voluntarios:funcao_nova")).status_code == 403

    def test_admin_cadastra_funcao(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("voluntarios:funcao_nova")).status_code == 200
