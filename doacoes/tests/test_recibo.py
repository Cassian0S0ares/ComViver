from decimal import Decimal

import pytest
from django.urls import reverse

from doacoes.factories import DoacaoFactory, DoadorFactory
from doacoes.models import TipoDoacao

pytestmark = pytest.mark.django_db


class TestRecibo:
    def test_tecnico_nao_emite_recibo(self, client, usuario_tecnico):
        doacao = DoacaoFactory()
        client.force_login(usuario_tecnico)
        assert client.get(reverse("doacoes:recibo", args=[doacao.pk])).status_code == 403

    def test_operacional_emite_recibo(self, client, usuario_operacional):
        doacao = DoacaoFactory()
        client.force_login(usuario_operacional)
        assert client.get(reverse("doacoes:recibo", args=[doacao.pk])).status_code == 200

    def test_recibo_mostra_o_doador_e_o_valor(self, client, usuario_operacional):
        doador = DoadorFactory(nome="Padaria Central")
        doacao = DoacaoFactory(
            doador=doador, tipo=TipoDoacao.DINHEIRO, valor=Decimal("250.00")
        )
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("doacoes:recibo", args=[doacao.pk])).content.decode()
        assert "Padaria Central" in conteudo
        assert "250,00" in conteudo

    def test_recibo_de_doacao_anonima_informa_anonimo(self, client, usuario_operacional):
        doacao = DoacaoFactory(doador=None)
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("doacoes:recibo", args=[doacao.pk])).content.decode()
        assert "Anônimo" in conteudo

    def test_abrir_o_recibo_nao_altera_estado(self, client, usuario_operacional):
        """GET não muda estado: prefetch do navegador ou uma <img src> embutida
        em site externo marcariam recibos sem ninguém pedir."""
        doacao = DoacaoFactory(recibo_emitido=False)
        client.force_login(usuario_operacional)
        client.get(reverse("doacoes:recibo", args=[doacao.pk]))
        doacao.refresh_from_db()
        assert doacao.recibo_emitido is False

    def test_post_marca_como_entregue(self, client, usuario_operacional):
        doacao = DoacaoFactory(recibo_emitido=False)
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:recibo", args=[doacao.pk]))
        doacao.refresh_from_db()
        assert doacao.recibo_emitido is True

    def test_formato_pdf_devolve_pdf(self, client, usuario_operacional):
        doacao = DoacaoFactory()
        client.force_login(usuario_operacional)
        resposta = client.get(
            reverse("doacoes:recibo", args=[doacao.pk]) + "?formato=pdf"
        )
        assert resposta["Content-Type"] == "application/pdf"
        assert resposta.content[:4] == b"%PDF"

    def test_pdf_tem_nome_de_arquivo_legivel(self, client, usuario_operacional):
        doacao = DoacaoFactory()
        client.force_login(usuario_operacional)
        resposta = client.get(
            reverse("doacoes:recibo", args=[doacao.pk]) + "?formato=pdf"
        )
        assert f"recibo-{doacao.pk}.pdf" in resposta["Content-Disposition"]
