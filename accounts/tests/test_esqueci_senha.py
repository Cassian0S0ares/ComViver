import re

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse

from accounts.factories import UsuarioFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def limpar_limite_de_pedidos():
    cache.clear()


def pedir_link(client, email):
    return client.post(reverse("accounts:esqueci_senha"), {"email": email})


def link_do_email():
    return re.search(r"http://testserver(/redefinir-senha/\S+/)", mail.outbox[0].body).group(1)


class TestPedirLink:
    def test_login_tem_link_para_esqueci_senha(self, client):
        html = client.get(reverse("accounts:login")).content.decode()
        assert reverse("accounts:esqueci_senha") in html

    def test_pagina_abre(self, client):
        assert client.get(reverse("accounts:esqueci_senha")).status_code == 200

    def test_usuario_cadastrado_recebe_o_link(self, client):
        UsuarioFactory(email="maria@exemplo.org")
        resposta = pedir_link(client, "Maria@Exemplo.org")
        assert resposta.status_code == 302
        assert resposta.url == reverse("accounts:esqueci_senha_enviado")
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["maria@exemplo.org"]
        assert "/redefinir-senha/" in mail.outbox[0].body

    def test_email_nao_cadastrado_nao_recebe_nada(self, client):
        resposta = pedir_link(client, "desconhecido@exemplo.org")
        # Mesma resposta de um e-mail cadastrado: a tela nao revela quem tem conta.
        assert resposta.status_code == 302
        assert resposta.url == reverse("accounts:esqueci_senha_enviado")
        assert mail.outbox == []

    def test_usuario_desativado_nao_recebe_nada(self, client):
        UsuarioFactory(email="maria@exemplo.org", is_active=False)
        pedir_link(client, "maria@exemplo.org")
        assert mail.outbox == []

    def test_limita_pedidos_repetidos(self, client):
        UsuarioFactory(email="maria@exemplo.org")
        for _ in range(5):
            pedir_link(client, "maria@exemplo.org")
        assert len(mail.outbox) == 3


class TestRedefinirSenha:
    def test_link_troca_a_senha_e_libera_o_login(self, client):
        usuario = UsuarioFactory(email="maria@exemplo.org", precisa_trocar_senha=True)
        pedir_link(client, "maria@exemplo.org")
        formulario = client.get(link_do_email(), follow=True)
        assert formulario.status_code == 200
        resposta = client.post(
            formulario.redirect_chain[-1][0],
            {"new_password1": "nova-senha-forte-456", "new_password2": "nova-senha-forte-456"},
        )
        assert resposta.url == reverse("accounts:redefinir_senha_concluido")
        usuario.refresh_from_db()
        assert usuario.check_password("nova-senha-forte-456")
        assert usuario.precisa_trocar_senha is False
        login = client.post(
            reverse("accounts:login"),
            {"username": "maria@exemplo.org", "password": "nova-senha-forte-456"},
        )
        assert login.status_code == 302

    def test_link_invalido_mostra_aviso(self, client):
        resposta = client.get(
            reverse("accounts:redefinir_senha", args=["MQ", "token-invalido"]), follow=True
        )
        assert resposta.status_code == 200
        assert "Este link não é mais válido" in resposta.content.decode()

    def test_link_so_funciona_uma_vez(self, client):
        UsuarioFactory(email="maria@exemplo.org")
        pedir_link(client, "maria@exemplo.org")
        link = link_do_email()
        formulario = client.get(link, follow=True)
        client.post(
            formulario.redirect_chain[-1][0],
            {"new_password1": "nova-senha-forte-456", "new_password2": "nova-senha-forte-456"},
        )
        segunda = client.get(link, follow=True)
        assert "Este link não é mais válido" in segunda.content.decode()


class TestEmailBonito:
    def test_email_tem_versao_html_com_link_e_logo(self, client):
        UsuarioFactory(email="maria@exemplo.org", first_name="Maria")
        pedir_link(client, "maria@exemplo.org")
        mensagem = mail.outbox[0]
        html, tipo = mensagem.alternatives[0]
        assert tipo == "text/html"
        assert link_do_email() in html
        assert "Maria" in html
        assert 'src="cid:logo-comviver"' in html
        logo = mensagem.attachments[0]
        assert logo["Content-ID"] == "<logo-comviver>"
        assert logo.get_content_type() == "image/png"
