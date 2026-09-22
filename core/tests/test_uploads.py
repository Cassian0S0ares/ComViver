import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from core.uploads import caminho_opaco, validar_documento, validar_imagem


class TestCaminhoOpaco:
    def test_descarta_o_nome_original(self):
        """O nome do arquivo vira parte da URL. 'ana-clara-souza.jpg'
        identificaria a crianca sem ninguem abrir a ficha — o que o art. 143
        do ECA veda."""
        gerar = caminho_opaco("acolhidos/fotos")
        caminho = gerar(None, "ana-clara-souza.jpg")
        assert "ana" not in caminho.lower()
        assert caminho.startswith("acolhidos/fotos/")
        assert caminho.endswith(".jpg")

    def test_dois_envios_geram_caminhos_diferentes(self):
        gerar = caminho_opaco("acolhidos/fotos")
        assert gerar(None, "foto.jpg") != gerar(None, "foto.jpg")

    def test_extensao_e_normalizada(self):
        gerar = caminho_opaco("acolhidos/fotos")
        assert gerar(None, "FOTO.JPEG").endswith(".jpeg")

    def test_extensao_perigosa_nao_sobrevive(self):
        gerar = caminho_opaco("acolhidos/documentos")
        caminho = gerar(None, "malicioso.php")
        assert not caminho.endswith(".php")
        assert caminho.endswith(".bin")


class TestValidadores:
    def test_imagem_aceita_jpg(self):
        validar_imagem(SimpleUploadedFile("foto.jpg", b"x" * 100, "image/jpeg"))

    def test_imagem_recusa_svg(self):
        """SVG e XML executavel: aceito, viraria XSS armazenado."""
        arquivo = SimpleUploadedFile("mapa.svg", b"<svg/>", "image/svg+xml")
        with pytest.raises(ValidationError):
            validar_imagem(arquivo)

    def test_imagem_recusa_html(self):
        arquivo = SimpleUploadedFile("pagina.html", b"<html>", "text/html")
        with pytest.raises(ValidationError):
            validar_imagem(arquivo)

    def test_documento_aceita_pdf(self):
        validar_documento(SimpleUploadedFile("doc.pdf", b"%PDF", "application/pdf"))

    def test_documento_recusa_executavel(self):
        arquivo = SimpleUploadedFile("programa.exe", b"MZ", "application/octet-stream")
        with pytest.raises(ValidationError):
            validar_documento(arquivo)

    def test_recusa_arquivo_grande_demais(self):
        from core.uploads import TAMANHO_MAXIMO_MB

        grande = SimpleUploadedFile(
            "foto.jpg", b"x" * (TAMANHO_MAXIMO_MB * 1024 * 1024 + 1), "image/jpeg"
        )
        with pytest.raises(ValidationError) as erro:
            validar_imagem(grande)
        assert "MB" in str(erro.value)

    def test_mensagem_de_erro_em_portugues(self):
        arquivo = SimpleUploadedFile("mapa.svg", b"<svg/>", "image/svg+xml")
        with pytest.raises(ValidationError) as erro:
            validar_imagem(arquivo)
        assert "não é aceito" in str(erro.value)
