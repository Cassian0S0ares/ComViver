from datetime import date

import pytest
from django.urls import reverse

from accounts.models import AcaoFicha, LogAcessoFicha
from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory
from acolhidos.models import FichaAcolhimento

pytestmark = pytest.mark.django_db


class TestEditarAcolhido:
    @pytest.mark.parametrize("rota", ["acolhidos:editar", "acolhidos:editar_ficha"])
    def test_operacional_recebe_403(self, client, usuario_operacional, rota):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_operacional)
        assert client.get(reverse(rota, args=[acolhido.pk])).status_code == 403

    def test_tecnico_corrige_o_nome(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory(nome="Ana Clara Sousa")
        client.force_login(usuario_tecnico)
        resposta = client.post(
            reverse("acolhidos:editar", args=[acolhido.pk]),
            {
                "nome": "Ana Clara Souza",
                "nome_social": "",
                "nascimento": acolhido.nascimento.isoformat(),
                "sexo": "F",
                "naturalidade": "",
                "cpf": "",
                "rg": "",
                "certidao_nascimento": "",
                "cartao_sus": "",
            },
        )
        assert resposta.url == reverse("acolhidos:detalhe", args=[acolhido.pk])
        acolhido.refresh_from_db()
        assert acolhido.nome == "Ana Clara Souza"
        assert LogAcessoFicha.objects.filter(acolhido=acolhido, acao=AcaoFicha.EDIT).exists()


class TestEditarFicha:
    def test_abrir_a_ficha_vazia_nao_grava_nada(self, client, usuario_tecnico):
        """Consultar a tela nao pode criar uma ficha com data de entrada inventada."""
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        assert client.get(reverse("acolhidos:editar_ficha", args=[acolhido.pk])).status_code == 200
        assert not FichaAcolhimento.objects.filter(acolhido=acolhido).exists()

    def test_preencher_ficha_inexistente(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:editar_ficha", args=[acolhido.pk]),
            {
                "data_entrada": "2026-08-01",
                "motivo": "Negligência",
                "orgao_requisitante": "Conselho Tutelar",
                "processo_numero": "123",
                "vara": "",
            },
        )
        assert acolhido.ficha.data_entrada == date(2026, 8, 1)

    def test_editar_ficha_registra_no_log(self, client, usuario_tecnico):
        ficha = FichaAcolhimentoFactory(data_entrada=date(2026, 8, 1))
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:editar_ficha", args=[ficha.acolhido.pk]),
            {
                "data_entrada": "2026-08-01",
                "motivo": "Outro motivo",
                "orgao_requisitante": "Conselho Tutelar",
                "processo_numero": "123",
                "vara": "",
            },
        )
        ficha.refresh_from_db()
        assert ficha.motivo == "Outro motivo"
        assert LogAcessoFicha.objects.filter(acolhido=ficha.acolhido, acao=AcaoFicha.EDIT).exists()

    def test_ficha_mostra_os_botoes_de_edicao_so_para_a_equipe_tecnica(
        self, client, usuario_tecnico, usuario_operacional
    ):
        acolhido = AcolhidoFactory()
        url_edicao = reverse("acolhidos:editar", args=[acolhido.pk])
        client.force_login(usuario_tecnico)
        assert (
            url_edicao
            in client.get(reverse("acolhidos:detalhe", args=[acolhido.pk])).content.decode()
        )
        client.force_login(usuario_operacional)
        assert (
            url_edicao
            not in client.get(reverse("acolhidos:detalhe", args=[acolhido.pk])).content.decode()
        )
