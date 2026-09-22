import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestPaginasDeErro:
    def test_403_usa_template_proprio(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("accounts:usuario_list"))
        assert resposta.status_code == 403
        assert "Seu perfil não tem acesso" in resposta.content.decode()

    def test_404_usa_template_proprio(self, client, usuario_admin, settings):
        settings.DEBUG = False
        client.force_login(usuario_admin)
        resposta = client.get("/rota-que-nao-existe/")
        assert resposta.status_code == 404
        assert "Página não encontrada" in resposta.content.decode()
