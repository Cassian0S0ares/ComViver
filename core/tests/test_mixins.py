import pytest
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import View

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin


class ViewSoTecnico(PerfilRequiredMixin, View):
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO]

    def get(self, request):
        return HttpResponse("ok")


urlpatterns = [
    path("so-tecnico/", ViewSoTecnico.as_view(), name="so-tecnico"),
    path("", include("comviver.urls")),
]

pytestmark = [pytest.mark.django_db, pytest.mark.urls(__name__)]


class TestPerfilRequiredMixin:
    def test_anonimo_vai_para_o_login(self, client):
        resposta = client.get("/so-tecnico/")
        assert resposta.status_code == 302
        assert "/entrar/" in resposta.url

    def test_admin_entra(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get("/so-tecnico/").status_code == 200

    def test_tecnico_entra(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        assert client.get("/so-tecnico/").status_code == 200

    def test_operacional_recebe_403(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get("/so-tecnico/").status_code == 403

    def test_view_sem_perfis_declarados_falha_ao_ser_usada(self, usuario_admin):
        """Esquecer de declarar perfis_permitidos nao pode liberar acesso."""
        from django.core.exceptions import ImproperlyConfigured
        from django.test import RequestFactory

        class ViewSemDeclaracao(PerfilRequiredMixin, View):
            def get(self, request):
                return HttpResponse("ok")

        requisicao = RequestFactory().get("/qualquer/")
        requisicao.user = usuario_admin

        with pytest.raises(ImproperlyConfigured):
            ViewSemDeclaracao.as_view()(requisicao)
