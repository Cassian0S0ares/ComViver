from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from doacoes.factories import DoacaoFactory
from doacoes.models import TipoDoacao

pytestmark = pytest.mark.django_db


def test_filtro_por_mes_considera_ano_e_atualiza_totais(client, usuario_operacional):
    primeira = DoacaoFactory(data_recebimento=date(2025, 1, 2), valor=Decimal("100"))
    segunda = DoacaoFactory(data_recebimento=date(2025, 1, 31), valor=Decimal("150"))
    DoacaoFactory(data_recebimento=date(2025, 2, 1))
    DoacaoFactory(data_recebimento=date(2024, 1, 15))
    client.force_login(usuario_operacional)

    resposta = client.get(reverse("doacoes:lista"), {"mes": "2025-01"})

    assert resposta.status_code == 200
    assert {doacao.pk for doacao in resposta.context["doacoes"]} == {primeira.pk, segunda.pk}
    assert resposta.context["paginator"].count == 2
    assert resposta.context["totais"][0]["soma"] == Decimal("250")
    assert resposta.context["mes_filtrado"] == "2025-01"
    html = resposta.content.decode()
    assert 'type="month"' not in html
    assert '<option value="2025-01" selected>Janeiro de 2025</option>' in html


def test_mes_combina_com_busca_tipo_e_paginacao(client, usuario_operacional):
    DoacaoFactory.create_batch(26, data_recebimento=date(2025, 3, 10), descricao="Almoço")
    DoacaoFactory(data_recebimento=date(2025, 4, 10), descricao="Almoço")
    client.force_login(usuario_operacional)

    resposta = client.get(
        reverse("doacoes:lista"),
        {"mes": "2025-03", "q": "Almoço", "tipo": TipoDoacao.DINHEIRO, "page": "2"},
    )

    assert resposta.context["paginator"].count == 26
    assert resposta.context["page_obj"].number == 2
    assert "mes=2025-03" in resposta.context["filtros_query"]
    assert "tipo=DINHEIRO" in resposta.context["filtros_query"]
    assert "q=Almo" in resposta.context["filtros_query"]


@pytest.mark.parametrize("mes", ["2025-00", "2025-13", "2025-1", "0000-01", "invalido"])
def test_mes_invalido_nao_quebra_a_lista(client, usuario_operacional, mes):
    DoacaoFactory(data_recebimento=date(2025, 1, 10))
    client.force_login(usuario_operacional)

    resposta = client.get(reverse("doacoes:lista"), {"mes": mes})

    assert resposta.status_code == 200
    assert resposta.context["paginator"].count == 1
    assert resposta.context["mes_filtrado"] == ""


def test_opcoes_de_mes_listam_apenas_meses_com_doacoes(client, usuario_operacional):
    DoacaoFactory(data_recebimento=date(2025, 3, 10))
    DoacaoFactory(data_recebimento=date(2025, 3, 20))
    DoacaoFactory(data_recebimento=date(2024, 12, 5))
    client.force_login(usuario_operacional)

    resposta = client.get(reverse("doacoes:lista"))

    assert resposta.context["meses_disponiveis"] == [
        ("2025-03", "Março de 2025"),
        ("2024-12", "Dezembro de 2024"),
    ]
    assert "Todos os meses" in resposta.content.decode()
