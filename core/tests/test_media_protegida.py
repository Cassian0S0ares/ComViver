import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from acolhidos.factories import AcolhidoFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_temporaria(settings, tmp_path):
    """Os arquivos enviados nos testes nao podem cair na pasta media/ real."""
    settings.MEDIA_ROOT = tmp_path


def _acolhido_com_foto():
    imagem = SimpleUploadedFile("foto.jpg", b"conteudo-falso-de-imagem", "image/jpeg")
    return AcolhidoFactory(foto=imagem)


class TestMediaProtegida:
    def test_anonimo_nao_baixa_a_foto(self, client):
        acolhido = _acolhido_com_foto()
        resposta = client.get(reverse("media_protegida", args=[acolhido.foto.name]))
        assert resposta.status_code == 302
        assert "/entrar/" in resposta.url

    def test_usuario_autenticado_baixa_a_foto(self, client, usuario_operacional):
        acolhido = _acolhido_com_foto()
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("media_protegida", args=[acolhido.foto.name]))
        assert resposta.status_code == 200

    def test_operacional_nao_baixa_documento_sigiloso(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.get(
            reverse("media_protegida", args=["acolhidos/documentos/processo.pdf"])
        )
        assert resposta.status_code == 403

    def test_tecnico_pode_tentar_baixar_documento(self, client, usuario_tecnico):
        """Perfil autorizado passa pela checagem; 404 porque o arquivo nao existe."""
        client.force_login(usuario_tecnico)
        resposta = client.get(
            reverse("media_protegida", args=["acolhidos/documentos/processo.pdf"])
        )
        assert resposta.status_code == 404

    def test_caminho_com_travessia_e_recusado(self, client, usuario_admin):
        client.force_login(usuario_admin)
        resposta = client.get("/media/../comviver/settings/base.py")
        assert resposta.status_code in (400, 403, 404)

    def test_travessia_nao_escapa_do_prefixo_sigiloso(self, client, usuario_operacional):
        """`acolhidos/fotos/../documentos/x.pdf` comeca com um prefixo livre mas
        aponta para documento sigiloso: a checagem precisa olhar o destino."""
        client.force_login(usuario_operacional)
        resposta = client.get("/media/acolhidos/fotos/../documentos/processo.pdf")
        assert resposta.status_code == 403
