from datetime import date

import pytest
from django.urls import reverse

from doacoes.factories import DoacaoFactory
from doacoes.models import Doacao, TipoDoacao
from estoque.models import CategoriaItem

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


def _item():
    return {"tipo": f"c{CategoriaItem.objects.get_or_create(nome='Alimentos')[0].pk}",
            "item_nome": "Arroz"}


class TestDinheiroSemQuantidade:
    def test_quantidade_e_unidade_nao_sao_gravadas(self, client, usuario_operacional):
        """'R$ 500' nao tem quantidade nem unidade; o campo enviado por engano
        (ou por POST forjado) nao pode virar '20 pacotes de dinheiro'."""
        client.force_login(usuario_operacional)
        resposta = client.post(reverse("doacoes:nova"), _dados(quantidade="20", unidade="unidades"))
        assert resposta.status_code == 302
        doacao = Doacao.objects.get(valor=500)
        assert doacao.quantidade is None
        assert doacao.unidade == ""

    def test_editar_para_dinheiro_limpa_o_que_ja_existia(self, client, usuario_operacional):
        doacao = DoacaoFactory(
            tipo=TipoDoacao.ITEM, descricao="Arroz", quantidade=20, unidade="unidades"
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
                descricao="Arroz 5kg",
                quantidade="20",
                unidade="unidades",
                valor="",
                **_item(),
            ),
        )
        doacao = Doacao.objects.get(descricao="Arroz 5kg")
        assert doacao.quantidade == 20
        assert doacao.unidade == "unidades"

    def test_dinheiro_sem_valor_continua_sendo_recusado(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.post(reverse("doacoes:nova"), _dados(valor=""))
        assert resposta.status_code == 200
        assert "Informe o valor da doação em dinheiro" in resposta.content.decode()

    def test_trocar_dinheiro_por_item_descarta_valor_enviado(self, client, usuario_operacional):
        doacao = DoacaoFactory()
        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("doacoes:editar", args=[doacao.pk]),
            _dados(
                descricao="Arroz",
                quantidade="1",
                unidade="unidades",
                valor="500,00",
                **_item(),
            ),
        )
        assert resposta.status_code == 302
        doacao.refresh_from_db()
        assert doacao.tipo == TipoDoacao.ITEM
        assert doacao.valor is None

class TestCamposEscondidos:
    def test_formulario_marca_os_campos_de_especie(self, client, usuario_operacional):
        """A tela esconde quantidade e unidade quando o tipo e dinheiro; a
        marcacao e o que o JavaScript usa para achar o bloco."""
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("doacoes:nova")).content.decode()
        assert 'data-campo="quantidade"' in conteudo
        assert 'data-campo="unidade"' in conteudo
