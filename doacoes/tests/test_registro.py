from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from doacoes.factories import CampanhaFactory, DoadorFactory
from doacoes.models import Doacao, TipoDoacao
from estoque.models import CategoriaItem

pytestmark = pytest.mark.django_db


def _dados(**extra):
    base = {
        "doador": "",
        "campanha": "",
        "tipo": TipoDoacao.ALIMENTO,
        "descricao": "Arroz 5kg",
        "quantidade": "20",
        "unidade": "unidades",
        "categoria_estoque": CategoriaItem.objects.get_or_create(nome="Alimentos")[0].pk,
        "item_nome": "Arroz 5kg",
        "valor": "",
        "data_recebimento": date.today().isoformat(),
        "observacoes": "",
    }
    return base | extra


class TestRegistroDeDoacao:
    def test_registrar_doacao_em_especie(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.post(reverse("doacoes:nova"), _dados())
        assert resposta.status_code == 302
        doacao = Doacao.objects.get(descricao="Arroz 5kg")
        assert doacao.quantidade == Decimal("20")

    def test_registra_quem_recebeu(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:nova"), _dados())
        assert Doacao.objects.get(descricao="Arroz 5kg").recebido_por == usuario_operacional

    def test_doacao_anonima(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:nova"), _dados())
        assert Doacao.objects.get(descricao="Arroz 5kg").doador is None

    def test_doacao_com_doador(self, client, usuario_operacional):
        doador = DoadorFactory(nome="Padaria Central")
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:nova"), _dados(doador=str(doador.pk)))
        assert Doacao.objects.get(descricao="Arroz 5kg").doador == doador

    def test_doacao_vinculada_a_campanha(self, client, usuario_operacional):
        campanha = CampanhaFactory(nome="Natal Solidário")
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:nova"), _dados(campanha=str(campanha.pk)))
        assert Doacao.objects.get(descricao="Arroz 5kg").campanha == campanha

    def test_dinheiro_sem_valor_mostra_erro(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("doacoes:nova"),
            _dados(tipo=TipoDoacao.DINHEIRO, valor="", descricao=""),
        )
        assert resposta.status_code == 200
        assert "Informe o valor da doação em dinheiro." in resposta.content.decode()
        assert Doacao.objects.count() == 0

    def test_salvar_e_novo_volta_ao_formulario(self, client, usuario_operacional):
        """Doacao chega em lote: voltar a listagem a cada item trava a fila."""
        client.force_login(usuario_operacional)
        resposta = client.post(reverse("doacoes:nova"), _dados(salvar_e_novo="1"))
        assert resposta.status_code == 302
        assert resposta.url.startswith(reverse("doacoes:nova"))

    def test_salvar_e_novo_preserva_data_e_doador(self, client, usuario_operacional):
        doador = DoadorFactory(nome="Padaria Central")
        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("doacoes:nova"), _dados(doador=str(doador.pk), salvar_e_novo="1")
        )
        assert f"doador={doador.pk}" in resposta.url
        assert f"data={date.today().isoformat()}" in resposta.url


class TestBuscaDeDoador:
    def test_busca_devolve_fragmento_com_o_doador(self, client, usuario_operacional):
        DoadorFactory(nome="Padaria Central")
        DoadorFactory(nome="Mercado do Bairro")
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("doacoes:buscar_doador") + "?termo=padar")
        conteudo = resposta.content.decode()
        assert "Padaria Central" in conteudo
        assert "Mercado do Bairro" not in conteudo

    def test_busca_com_menos_de_tres_letras_nao_consulta(self, client, usuario_operacional):
        DoadorFactory(nome="Padaria Central")
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("doacoes:buscar_doador") + "?termo=pa")
        assert "Padaria Central" not in resposta.content.decode()

    def test_tecnico_nao_usa_a_busca(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        resposta = client.get(reverse("doacoes:buscar_doador") + "?termo=padar")
        assert resposta.status_code == 403
