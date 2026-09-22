import pytest
from django.urls import include, path

from accounts.models import Perfil
from core.forms import FormularioPorPerfilMixin
from core.views import BaseCreateView, BaseListView
from tests.testapp.models import ModeloPesquisavel


class ListaTeste(BaseListView):
    model = ModeloPesquisavel
    template_name = "testapp/lista.html"
    campos_busca = ["nome", "apelido"]
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]


class FormularioTeste(FormularioPorPerfilMixin):
    campos_restritos = {Perfil.OPERACIONAL: ["segredo"]}

    class Meta:
        model = ModeloPesquisavel
        fields = ["nome", "apelido", "segredo"]


class CriarTeste(BaseCreateView):
    model = ModeloPesquisavel
    form_class = FormularioTeste
    template_name = "testapp/form.html"
    mensagem_sucesso = "Registro salvo."
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]


urlpatterns = [
    path("lista/", ListaTeste.as_view(), name="lista"),
    path("criar/", CriarTeste.as_view(), name="criar"),
    # O layout base monta o menu com as rotas reais do sistema.
    path("", include("comviver.urls")),
]

pytestmark = [pytest.mark.django_db, pytest.mark.urls(__name__)]


class TestBaseListView:
    def test_lista_sem_busca_traz_tudo(self, client, usuario_admin):
        ModeloPesquisavel.objects.create(nome="Ana")
        ModeloPesquisavel.objects.create(nome="Bruno")
        client.force_login(usuario_admin)
        assert len(client.get("/lista/").context["object_list"]) == 2

    def test_busca_filtra_por_qualquer_campo_declarado(self, client, usuario_admin):
        ModeloPesquisavel.objects.create(nome="Ana", apelido="Aninha")
        ModeloPesquisavel.objects.create(nome="Bruno", apelido="Bru")
        client.force_login(usuario_admin)
        resultado = client.get("/lista/?q=aninha").context["object_list"]
        assert [o.nome for o in resultado] == ["Ana"]

    def test_busca_ignora_maiusculas_e_minusculas(self, client, usuario_admin):
        ModeloPesquisavel.objects.create(nome="Ana")
        client.force_login(usuario_admin)
        assert len(client.get("/lista/?q=ANA").context["object_list"]) == 1

    def test_excluido_logicamente_nao_aparece(self, client, usuario_admin):
        obj = ModeloPesquisavel.objects.create(nome="Ana")
        obj.delete()
        client.force_login(usuario_admin)
        assert len(client.get("/lista/").context["object_list"]) == 0


class TestBaseCreateView:
    def test_registra_quem_criou(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        client.post("/criar/", {"nome": "Ana", "apelido": "", "segredo": ""})
        assert ModeloPesquisavel.objects.get(nome="Ana").criado_por == usuario_tecnico

    def test_mostra_mensagem_de_sucesso(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        resposta = client.post(
            "/criar/", {"nome": "Ana", "apelido": "", "segredo": ""}, follow=True
        )
        assert "Registro salvo." in [m.message for m in resposta.context["messages"]]


class TestFormularioPorPerfilMixin:
    def test_operacional_nao_recebe_o_campo_restrito(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        form = client.get("/criar/").context["form"]
        assert "segredo" not in form.fields

    def test_tecnico_recebe_o_campo_restrito(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        form = client.get("/criar/").context["form"]
        assert "segredo" in form.fields

    def test_post_forjado_nao_grava_campo_restrito(self, client, usuario_operacional):
        """Camada 2 da protecao: o campo nao existe no formulario, entao
        enviar o valor direto no POST nao tem efeito."""
        client.force_login(usuario_operacional)
        client.post("/criar/", {"nome": "Ana", "apelido": "", "segredo": "vazou"})
        assert ModeloPesquisavel.objects.get(nome="Ana").segredo == ""
