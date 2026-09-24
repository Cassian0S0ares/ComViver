from datetime import date, timedelta
from decimal import Decimal

import pytest

from doacoes.factories import DoacaoFactory, DoadorFactory
from doacoes.models import TipoDoacao
from doacoes.services import (
    doadores_recorrentes_inativos,
    totais_por_tipo,
    total_arrecadado,
)

pytestmark = pytest.mark.django_db


class TestTotaisPorTipo:
    def test_agrupa_e_conta(self):
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("50.00"))
        DoacaoFactory(tipo=TipoDoacao.ITEM, valor=None, descricao="Arroz")
        resultado = {linha["tipo"]: linha for linha in totais_por_tipo()}
        assert resultado["DINHEIRO"]["quantidade"] == 2
        assert resultado["DINHEIRO"]["soma"] == Decimal("150.00")
        assert resultado["ITEM"]["quantidade"] == 1
        assert resultado["ITEM"]["soma"] == Decimal("0")

    def test_respeita_a_consulta_recebida(self):
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(
            tipo=TipoDoacao.DINHEIRO,
            valor=Decimal("50.00"),
            data_recebimento=date.today() - timedelta(days=365),
        )
        from doacoes.models import Doacao

        deste_ano = Doacao.objects.filter(data_recebimento__year=date.today().year)
        resultado = {linha["tipo"]: linha for linha in totais_por_tipo(deste_ano)}
        assert resultado["DINHEIRO"]["soma"] == Decimal("100.00")

    def test_ignora_doacao_excluida_logicamente(self):
        doacao = DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        doacao.delete()
        assert totais_por_tipo() == []


class TestTotalArrecadado:
    def test_soma_apenas_dinheiro(self):
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(tipo=TipoDoacao.ITEM, valor=None, descricao="Arroz")
        assert total_arrecadado() == Decimal("100.00")

    def test_zero_sem_doacao(self):
        assert total_arrecadado() == Decimal("0")


class TestDoadoresRecorrentesInativos:
    def test_recorrente_sem_doacao_recente_aparece(self):
        doador = DoadorFactory(recorrente=True)
        DoacaoFactory(doador=doador, data_recebimento=date.today() - timedelta(days=90))
        assert doador in doadores_recorrentes_inativos()

    def test_recorrente_com_doacao_recente_nao_aparece(self):
        doador = DoadorFactory(recorrente=True)
        DoacaoFactory(doador=doador, data_recebimento=date.today() - timedelta(days=10))
        assert doador not in doadores_recorrentes_inativos()

    def test_doador_nao_recorrente_nunca_aparece(self):
        doador = DoadorFactory(recorrente=False)
        DoacaoFactory(doador=doador, data_recebimento=date.today() - timedelta(days=200))
        assert doador not in doadores_recorrentes_inativos()

    def test_recorrente_que_nunca_doou_aparece(self):
        doador = DoadorFactory(recorrente=True)
        assert doador in doadores_recorrentes_inativos()
