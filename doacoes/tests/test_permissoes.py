import pytest
from django.urls import reverse

from doacoes.factories import DoacaoFactory, DoadorFactory

pytestmark = pytest.mark.django_db

ROTAS_ESCRITA = [
    ("doacoes:nova", None),
    ("doacoes:doador_novo", None),
]


class TestLeitura:
    @pytest.mark.parametrize(
        "fixture_usuario", ["usuario_admin", "usuario_tecnico", "usuario_operacional"]
    )
    def test_todos_os_perfis_veem_a_lista(self, client, request, fixture_usuario):
        client.force_login(request.getfixturevalue(fixture_usuario))
        assert client.get(reverse("doacoes:lista")).status_code == 200


class TestEscrita:
    @pytest.mark.parametrize("rota,_", ROTAS_ESCRITA)
    def test_admin_escreve(self, client, usuario_admin, rota, _):
        client.force_login(usuario_admin)
        assert client.get(reverse(rota)).status_code == 200

    @pytest.mark.parametrize("rota,_", ROTAS_ESCRITA)
    def test_operacional_escreve(self, client, usuario_operacional, rota, _):
        client.force_login(usuario_operacional)
        assert client.get(reverse(rota)).status_code == 200

    @pytest.mark.parametrize("rota,_", ROTAS_ESCRITA)
    def test_tecnico_recebe_403(self, client, usuario_tecnico, rota, _):
        """Equipe tecnica cuida do acolhido, nao da portaria. Le, nao escreve."""
        client.force_login(usuario_tecnico)
        assert client.get(reverse(rota)).status_code == 403


class TestCampanhas:
    def test_so_admin_cria_campanha(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get(reverse("doacoes:campanha_nova")).status_code == 403

    def test_admin_cria_campanha(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("doacoes:campanha_nova")).status_code == 200
