from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from doacoes.factories import CampanhaFactory, DoacaoFactory
from doacoes.models import Campanha, MetaItemCampanha, TipoDoacao

pytestmark = pytest.mark.django_db


def dados_campanha(**extra):
    return {
        "nome": "Campanha de inverno",
        "descricao": "Roupas e alimentos",
        "data_inicio": timezone.localdate().isoformat(),
        "data_fim": "",
        "meta_valor": "500",
        "metas-TOTAL_FORMS": "2",
        "metas-INITIAL_FORMS": "0",
        "metas-MIN_NUM_FORMS": "0",
        "metas-MAX_NUM_FORMS": "1000",
        "metas-0-tipo": TipoDoacao.VESTUARIO,
        "metas-0-quantidade": "30",
        "metas-0-unidade": "unidades",
        "metas-1-tipo": TipoDoacao.ALIMENTO,
        "metas-1-quantidade": "10",
        "metas-1-unidade": "unidades",
    } | extra


def test_formulario_oferece_campos_para_varias_metas(client, usuario_admin):
    client.force_login(usuario_admin)
    resposta = client.get(reverse("doacoes:campanha_nova"))
    assert resposta.status_code == 200
    assert resposta.context["metas_formset"].total_form_count() == 2
    conteudo = resposta.content.decode()
    assert 'id="campaign-goals-title">Metas da campanha' in conteudo
    assert conteudo.count('name="meta_valor"') == 1
    assert conteudo.index('id="campaign-goals-title"') < conteudo.index('name="meta_valor"')
    assert 'data-money-goal' in conteudo
    assert 'data-add-money' in conteudo
    assert 'data-remove-meta' in conteudo
    assert 'data-add-meta' in conteudo
    assert 'name="metas-TOTAL_FORMS"' in conteudo
    assert 'name="metas-0-tipo"' in conteudo
    assert 'name="metas-1-tipo"' in conteudo

def test_cria_campanha_com_dinheiro_e_duas_metas_de_itens(client, usuario_admin):
    client.force_login(usuario_admin)
    resposta = client.post(reverse("doacoes:campanha_nova"), dados_campanha())
    assert resposta.status_code == 302
    campanha = Campanha.objects.get(nome="Campanha de inverno")
    assert campanha.meta_valor == Decimal("500")
    assert list(campanha.metas_itens.values_list("tipo", "quantidade", "unidade")) == [
        (TipoDoacao.VESTUARIO, 30, "unidades"),
        (TipoDoacao.ALIMENTO, 10, "unidades"),
    ]


def test_campanha_so_com_meta_em_reais_aceita_linha_vazia(client, usuario_admin):
    client.force_login(usuario_admin)
    resposta = client.post(
        reverse("doacoes:campanha_nova"),
        dados_campanha(**{
            "metas-TOTAL_FORMS": "1",
            "metas-0-tipo": "",
            "metas-0-quantidade": "",
            "metas-0-unidade": "",
        }),
    )
    assert resposta.status_code == 302
    campanha = Campanha.objects.get(nome="Campanha de inverno")
    assert campanha.meta_valor == Decimal("500")
    assert campanha.metas_itens.count() == 0

def test_meta_de_item_sem_meta_financeira(client, usuario_admin):
    client.force_login(usuario_admin)
    resposta = client.post(
        reverse("doacoes:campanha_nova"),
        dados_campanha(meta_valor="", **{"metas-TOTAL_FORMS": "1"}),
    )
    assert resposta.status_code == 302
    campanha = Campanha.objects.get(nome="Campanha de inverno")
    assert campanha.meta_valor is None
    assert campanha.metas_itens.count() == 1


def test_metas_de_itens_somam_apenas_tipo_e_campanha_corretos():
    campanha = CampanhaFactory(meta_valor=Decimal("500"))
    MetaItemCampanha.objects.create(
        campanha=campanha, tipo=TipoDoacao.VESTUARIO, quantidade=30, unidade="unidades"
    )
    DoacaoFactory(campanha=campanha, tipo=TipoDoacao.DINHEIRO, valor=200)
    DoacaoFactory(
        campanha=campanha, tipo=TipoDoacao.VESTUARIO, quantidade=12, unidade="unidades", valor=None
    )
    DoacaoFactory(
        campanha=campanha, tipo=TipoDoacao.VESTUARIO, quantidade=4, unidade="unidades", valor=None
    )
    DoacaoFactory(
        campanha=campanha, tipo=TipoDoacao.ALIMENTO, quantidade=5, unidade="unidades", valor=None
    )
    DoacaoFactory(
        campanha=CampanhaFactory(), tipo=TipoDoacao.VESTUARIO, quantidade=9,
        unidade="unidades", valor=None
    )
    dinheiro, roupas = campanha.metas_com_progresso
    assert dinheiro["recebido"] == Decimal("200")
    assert dinheiro["percentual"] == 40
    assert roupas["recebido"] == Decimal("16")
    assert roupas["percentual"] == 53


def test_metas_duplicadas_nao_salvam_campanha(client, usuario_admin):
    client.force_login(usuario_admin)
    resposta = client.post(
        reverse("doacoes:campanha_nova"),
        dados_campanha(**{"metas-1-tipo": TipoDoacao.VESTUARIO,
                         "metas-1-unidade": "unidades"}),
    )
    assert resposta.status_code == 200
    assert Campanha.objects.filter(nome="Campanha de inverno").count() == 0
    assert "apenas uma meta" in resposta.content.decode()


def test_edicao_altera_e_remove_metas(client, usuario_admin):
    campanha = CampanhaFactory(meta_valor=Decimal("500"))
    primeira = MetaItemCampanha.objects.create(
        campanha=campanha, tipo=TipoDoacao.VESTUARIO, quantidade=30, unidade="unidades"
    )
    segunda = MetaItemCampanha.objects.create(
        campanha=campanha, tipo=TipoDoacao.ALIMENTO, quantidade=10, unidade="unidades"
    )
    client.force_login(usuario_admin)
    resposta = client.post(
        reverse("doacoes:campanha_editar", args=[campanha.pk]),
        dados_campanha(**{
            "metas-INITIAL_FORMS": "2",
            "metas-0-id": str(primeira.pk),
            "metas-0-quantidade": "40",
            "metas-1-id": str(segunda.pk),
            "metas-1-DELETE": "on",
        }),
    )
    assert resposta.status_code == 302
    assert list(campanha.metas_itens.values_list("tipo", "quantidade")) == [
        (TipoDoacao.VESTUARIO, 40)
    ]


def test_unidade_incompativel_nao_salva_campanha(client, usuario_admin):
    client.force_login(usuario_admin)
    resposta = client.post(
        reverse("doacoes:campanha_nova"),
        dados_campanha(**{"metas-0-unidade": "horas"}),
    )
    assert resposta.status_code == 200
    assert "não é compatível" in resposta.content.decode()
    assert not Campanha.objects.filter(nome="Campanha de inverno").exists()


def test_pode_substituir_meta_removida_pela_mesma_combinacao(client, usuario_admin):
    campanha = CampanhaFactory(meta_valor=None)
    antiga = MetaItemCampanha.objects.create(
        campanha=campanha, tipo=TipoDoacao.ALIMENTO, quantidade=10, unidade="unidades"
    )
    client.force_login(usuario_admin)
    resposta = client.post(
        reverse("doacoes:campanha_editar", args=[campanha.pk]),
        dados_campanha(**{
            "metas-INITIAL_FORMS": "1",
            "metas-0-id": str(antiga.pk),
            "metas-0-tipo": TipoDoacao.ALIMENTO,
            "metas-0-quantidade": "10",
            "metas-0-unidade": "unidades",
            "metas-0-DELETE": "on",
            "metas-1-tipo": TipoDoacao.ALIMENTO,
            "metas-1-quantidade": "20",
            "metas-1-unidade": "unidades",
        }),
    )
    assert resposta.status_code == 302
    assert list(campanha.metas_itens.values_list("quantidade", flat=True)) == [20]

def test_lista_e_detalhe_mostram_todas_as_metas(client, usuario_admin):
    campanha = CampanhaFactory(meta_valor=Decimal("500"))
    MetaItemCampanha.objects.create(
        campanha=campanha, tipo=TipoDoacao.VESTUARIO, quantidade=30, unidade="unidades"
    )
    client.force_login(usuario_admin)
    for rota in ("doacoes:campanha_lista", "doacoes:campanha_detalhe"):
        args = [campanha.pk] if rota.endswith("detalhe") else []
        conteudo = client.get(reverse(rota, args=args)).content.decode()
        assert "Metas da campanha" in conteudo
        assert "30 unidades" in conteudo
        assert "R$ 500" in conteudo
