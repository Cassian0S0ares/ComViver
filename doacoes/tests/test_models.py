from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from doacoes.factories import CampanhaFactory, DoacaoFactory, DoadorFactory
from doacoes.models import Doacao, TipoDoacao, TipoPessoa

pytestmark = pytest.mark.django_db


class TestDoador:
    def test_documento_formatado_de_pessoa_fisica(self):
        doador = DoadorFactory(tipo=TipoPessoa.PF, cpf_cnpj="12345678901")
        assert doador.documento_formatado == "123.456.789-01"

    def test_documento_formatado_de_pessoa_juridica(self):
        doador = DoadorFactory(tipo=TipoPessoa.PJ, cpf_cnpj="12345678000190")
        assert doador.documento_formatado == "12.345.678/0001-90"

    def test_documento_vazio_devolve_traco(self):
        assert DoadorFactory(cpf_cnpj="").documento_formatado == "—"

    def test_total_doado_soma_apenas_dinheiro(self):
        doador = DoadorFactory()
        DoacaoFactory(doador=doador, tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(doador=doador, tipo=TipoDoacao.DINHEIRO, valor=Decimal("50.50"))
        DoacaoFactory(doador=doador, tipo=TipoDoacao.ALIMENTO, valor=None, quantidade=20)
        assert doador.total_doado == Decimal("150.50")

    def test_total_doado_zero_sem_doacao_em_dinheiro(self):
        doador = DoadorFactory()
        DoacaoFactory(doador=doador, tipo=TipoDoacao.ALIMENTO, valor=None)
        assert doador.total_doado == Decimal("0")


class TestDoacao:
    def test_doacao_anonima_e_permitida(self):
        """Doacao anonima e frequente e nao pode travar o registro."""
        doacao = DoacaoFactory(doador=None, tipo=TipoDoacao.ALIMENTO)
        assert doacao.doador is None
        assert Doacao.objects.filter(pk=doacao.pk).exists()

    def test_dinheiro_sem_valor_e_recusado(self):
        doacao = DoacaoFactory.build(tipo=TipoDoacao.DINHEIRO, valor=None)
        with pytest.raises(ValidationError) as erro:
            doacao.full_clean()
        assert "valor" in erro.value.message_dict

    def test_dinheiro_com_valor_negativo_e_recusado(self):
        doacao = DoacaoFactory.build(tipo=TipoDoacao.DINHEIRO, valor=Decimal("-10.00"))
        with pytest.raises(ValidationError):
            doacao.full_clean()

    def test_data_futura_e_recusada(self):
        doacao = DoacaoFactory.build(
            data_recebimento=date.today() + timedelta(days=1), tipo=TipoDoacao.ALIMENTO
        )
        with pytest.raises(ValidationError) as erro:
            doacao.full_clean()
        assert "data_recebimento" in erro.value.message_dict

    def test_descricao_quantidade_de_item_contavel(self):
        doacao = DoacaoFactory(
            tipo=TipoDoacao.ALIMENTO, descricao="Arroz 5kg",
            quantidade=20, unidade="pacotes", valor=None,
        )
        assert doacao.descricao_quantidade == "20 pacotes"

    def test_descricao_quantidade_de_dinheiro(self):
        doacao = DoacaoFactory(
            tipo=TipoDoacao.DINHEIRO, valor=Decimal("250.00"), quantidade=None
        )
        assert doacao.descricao_quantidade == "R$ 250,00"

    def test_exclusao_e_logica(self):
        doacao = DoacaoFactory()
        pk = doacao.pk
        doacao.delete()
        assert not Doacao.objects.filter(pk=pk).exists()
        assert Doacao.todos.filter(pk=pk).exists()


class TestCampanha:
    def test_campanha_no_periodo_esta_ativa(self):
        campanha = CampanhaFactory(
            data_inicio=date.today() - timedelta(days=5),
            data_fim=date.today() + timedelta(days=5),
        )
        assert campanha.esta_ativa is True

    def test_campanha_encerrada_nao_esta_ativa(self):
        campanha = CampanhaFactory(
            data_inicio=date.today() - timedelta(days=30),
            data_fim=date.today() - timedelta(days=1),
        )
        assert campanha.esta_ativa is False

    def test_arrecadado_soma_as_doacoes_da_campanha(self):
        campanha = CampanhaFactory(meta_valor=Decimal("1000.00"))
        DoacaoFactory(campanha=campanha, tipo=TipoDoacao.DINHEIRO, valor=Decimal("300.00"))
        DoacaoFactory(campanha=campanha, tipo=TipoDoacao.DINHEIRO, valor=Decimal("200.00"))
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("999.00"))  # outra campanha
        assert campanha.arrecadado == Decimal("500.00")

    def test_percentual_da_meta(self):
        campanha = CampanhaFactory(meta_valor=Decimal("1000.00"))
        DoacaoFactory(campanha=campanha, tipo=TipoDoacao.DINHEIRO, valor=Decimal("250.00"))
        assert campanha.percentual_da_meta == 25

    def test_percentual_zero_quando_sem_meta(self):
        campanha = CampanhaFactory(meta_valor=None)
        assert campanha.percentual_da_meta == 0
