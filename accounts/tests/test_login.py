import pytest
from django.urls import reverse

from accounts.factories import UsuarioFactory

pytestmark = pytest.mark.django_db


class TestLogin:
    def test_pagina_de_login_abre(self, client):
        assert client.get(reverse("accounts:login")).status_code == 200

    def test_login_com_credenciais_corretas_leva_ao_painel(self, client):
        UsuarioFactory(email="maria@exemplo.org", password="senha-de-teste-123")
        resposta = client.post(
            reverse("accounts:login"),
            {"username": "maria@exemplo.org", "password": "senha-de-teste-123"},
        )
        assert resposta.status_code == 302
        assert resposta.url == reverse("core:painel")

    def test_login_com_senha_errada_mostra_erro_em_portugues(self, client):
        UsuarioFactory(email="maria@exemplo.org", password="senha-de-teste-123")
        resposta = client.post(
            reverse("accounts:login"), {"username": "maria@exemplo.org", "password": "errada"}
        )
        assert resposta.status_code == 200
        assert "E-mail ou senha incorretos." in resposta.content.decode()

    def test_email_nao_diferencia_maiusculas(self, client):
        UsuarioFactory(email="maria@exemplo.org", password="senha-de-teste-123")
        resposta = client.post(
            reverse("accounts:login"),
            {"username": " Maria@Exemplo.ORG ", "password": "senha-de-teste-123"},
        )
        assert resposta.status_code == 302

    def test_nome_de_usuario_nao_serve_mais_para_entrar(self, client):
        UsuarioFactory(username="maria", email="maria@exemplo.org", password="senha-de-teste-123")
        resposta = client.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "senha-de-teste-123"},
        )
        assert resposta.status_code == 200

    def test_campo_de_login_pede_email(self, client):
        html = client.get(reverse("accounts:login")).content.decode()
        assert 'type="email"' in html
        assert "E-mail" in html

    def test_usuario_inativo_nao_entra(self, client):
        UsuarioFactory(email="maria@exemplo.org", password="senha-de-teste-123", is_active=False)
        resposta = client.post(
            reverse("accounts:login"),
            {"username": "maria@exemplo.org", "password": "senha-de-teste-123"},
        )
        assert resposta.status_code == 200

    def test_logout_encerra_a_sessao(self, client, usuario_admin):
        client.force_login(usuario_admin)
        client.post(reverse("accounts:logout"))
        assert client.get(reverse("core:painel")).status_code == 302


class TestTrocaSenhaObrigatoria:
    def test_usuario_novo_e_desviado_para_a_troca(self, client):
        usuario = UsuarioFactory(password="senha-de-teste-123", precisa_trocar_senha=True)
        client.force_login(usuario)
        resposta = client.get(reverse("core:painel"))
        assert resposta.status_code == 302
        assert resposta.url == reverse("accounts:trocar_senha")

    def test_pode_abrir_a_propria_pagina_de_troca(self, client):
        usuario = UsuarioFactory(password="senha-de-teste-123", precisa_trocar_senha=True)
        client.force_login(usuario)
        assert client.get(reverse("accounts:trocar_senha")).status_code == 200

    def test_trocar_a_senha_libera_o_sistema(self, client):
        usuario = UsuarioFactory(password="senha-de-teste-123", precisa_trocar_senha=True)
        client.force_login(usuario)
        client.post(
            reverse("accounts:trocar_senha"),
            {
                "old_password": "senha-de-teste-123",
                "new_password1": "outra-senha-forte-456",
                "new_password2": "outra-senha-forte-456",
            },
        )
        usuario.refresh_from_db()
        assert usuario.precisa_trocar_senha is False
        assert client.get(reverse("core:painel")).status_code == 200

    def test_quem_ja_trocou_nao_e_desviado(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("core:painel")).status_code == 200


class TestBloqueioPorTentativas:
    def test_bloqueia_apos_cinco_erros(self, client, settings):
        """Sem essa trava, senha fraca cai por forca bruta — e o acesso obtido
        alcanca a ficha de criancas acolhidas."""
        settings.AXES_ENABLED = True
        UsuarioFactory(email="maria@exemplo.org", password="senha-de-teste-123")

        for _ in range(5):
            client.post(
                reverse("accounts:login"), {"username": "maria@exemplo.org", "password": "errada"}
            )

        resposta = client.post(
            reverse("accounts:login"),
            {"username": "maria@exemplo.org", "password": "senha-de-teste-123"},
        )
        assert resposta.status_code in (403, 429)

    def _errar_cinco_vezes(self, client, email, ip):
        for _ in range(5):
            client.post(
                reverse("accounts:login"),
                {"username": email, "password": "errada"},
                REMOTE_ADDR=ip,
            )

    def test_mesma_conta_segue_acessivel_de_outro_ip(self, client, settings):
        """Quem erra a senha de alguem nao pode travar o acesso do dono."""
        settings.AXES_ENABLED = True
        UsuarioFactory(email="maria@exemplo.org", password="senha-de-teste-123")
        self._errar_cinco_vezes(client, "maria@exemplo.org", "10.0.0.1")

        resposta = client.post(
            reverse("accounts:login"),
            {"username": "maria@exemplo.org", "password": "senha-de-teste-123"},
            REMOTE_ADDR="10.0.0.2",
        )
        assert resposta.status_code == 302

    def test_ip_bloqueado_nao_entra_nem_em_outra_conta(self, client, settings):
        settings.AXES_ENABLED = True
        UsuarioFactory(email="joao@exemplo.org", password="senha-de-teste-123")
        self._errar_cinco_vezes(client, "maria@exemplo.org", "10.0.0.1")

        resposta = client.post(
            reverse("accounts:login"),
            {"username": "joao@exemplo.org", "password": "senha-de-teste-123"},
            REMOTE_ADDR="10.0.0.1",
        )
        assert resposta.status_code == 429
