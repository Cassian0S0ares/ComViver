from datetime import date

import pytest
from django.urls import reverse

from doacoes.factories import DoacaoFactory
from doacoes.models import Doacao, TipoDoacao

pytestmark = pytest.mark.django_db


def _dados(**extra):
    base = {
        "doador": "",
        "campanha": "",
        "tipo": TipoDoacao.DINHEIRO,
        "descricao": "",
        "quantidade": "",
        "unidade": "",
        "valor": "500,00",
        "data_recebimento": date.today().isoformat(),
        "observacoes": "",
    }
    return base | extra


class TestDinheiroSemQuantidade:
    def test_quantidade_e_unidade_nao_sao_gravadas(self, client, usuario_operacional):
        """'R$ 500' nao tem quantidade nem unidade; o campo enviado por engano
        (ou por POST forjado) nao pode virar '20 pacotes de dinheiro'."""
        client.force_login(usuario_operacional)
        resposta = client.post(reverse("doacoes:nova"), _dados(quantidade="20", unidade="pacotes"))
        assert resposta.status_code == 302
        doacao = Doacao.objects.get(valor=500)
        assert doacao.quantidade is None
        assert doacao.unidade == ""

    def test_editar_para_dinheiro_limpa_o_que_ja_existia(self, client, usuario_operacional):
        doacao = DoacaoFactory(
            tipo=TipoDoacao.ALIMENTO, descricao="Arroz", quantidade=20, unidade="pacotes"
        )
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:editar", args=[doacao.pk]), _dados())
        doacao.refresh_from_db()
        assert doacao.tipo == TipoDoacao.DINHEIRO
        assert doacao.quantidade is None
        assert doacao.unidade == ""

    def test_doacao_em_especie_continua_guardando_quantidade(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        client.post(
            reverse("doacoes:nova"),
            _dados(
                tipo=TipoDoacao.ALIMENTO,
                descricao="Arroz 5kg",
                quantidade="20",
                unidade="pacotes",
                valor="",
            ),
        )
        doacao = Doacao.objects.get(descricao="Arroz 5kg")
        assert doacao.quantidade == 20
        assert doacao.unidade == "pacotes"

    def test_dinheiro_sem_valor_continua_sendo_recusado(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.post(reverse("doacoes:nova"), _dados(valor=""))
        assert resposta.status_code == 200
        assert "Informe o valor da doação em dinheiro" in resposta.content.decode()


class TestCamposEscondidos:
    def test_formulario_marca_os_campos_de_especie(self, client, usuario_operacional):
        """A tela esconde quantidade e unidade quando o tipo e dinheiro; a
        marcacao e o que o JavaScript usa para achar o bloco."""
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("doacoes:nova")).content.decode()
        assert 'data-campo="quantidade"' in conteudo
        assert 'data-campo="unidade"' in conteudo
