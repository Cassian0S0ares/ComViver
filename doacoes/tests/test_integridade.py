from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from core.pdf import buscar_recurso_local
from doacoes.demo import criar_doacoes_demo
from doacoes.factories import CampanhaFactory, DoacaoFactory, DoadorFactory
from doacoes.forms import CampanhaForm, DoacaoForm, DoadorForm
from doacoes.models import Campanha, Doacao, Doador, TipoDoacao
from doacoes.services import doadores_recorrentes_inativos, totais_por_tipo

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("form_class", [CampanhaForm, DoacaoForm, DoadorForm])
def test_formulario_exige_perfil_autorizado(form_class, usuario_tecnico):
    with pytest.raises(PermissionDenied):
        form_class(usuario=usuario_tecnico)
    with pytest.raises(PermissionDenied):
        form_class()


def test_documento_formatado_aceito(usuario_operacional):
    form = DoadorForm(
        data={"tipo": "PJ", "nome": "Exemplo", "cpf_cnpj": "12.345.678/0001-90"},
        usuario=usuario_operacional,
    )
    assert form.is_valid(), form.errors
    assert form.save().cpf_cnpj == "12345678000190"


def test_dinheiro_com_virgula_e_decimal_exato(usuario_operacional):
    form = DoacaoForm(
        data={
            "tipo": "DINHEIRO",
            "valor": "1234,56",
            "data_recebimento": timezone.localdate().isoformat(),
        },
        usuario=usuario_operacional,
    )
    assert form.is_valid(), form.errors
    assert form.save().valor == Decimal("1234.56")


def test_exclusao_nao_altera_totais_nem_oculta_recorrente():
    doador = DoadorFactory(recorrente=True)
    campanha = CampanhaFactory()
    doacao = DoacaoFactory(doador=doador, campanha=campanha)
    doacao.delete()
    assert doador.total_doado == campanha.arrecadado == 0
    assert doador in doadores_recorrentes_inativos()


def test_estimativa_de_item_nao_entra_em_soma_monetaria():
    DoacaoFactory(tipo=TipoDoacao.ITEM, valor=Decimal("999.00"))
    assert totais_por_tipo()[0]["soma"] == 0


def test_validacao_campanha_no_modelo():
    campanha = CampanhaFactory.build(
        data_fim=timezone.localdate() - timedelta(days=1), meta_valor=Decimal("-1")
    )
    with pytest.raises(ValidationError) as erro:
        campanha.full_clean()
    assert {"data_fim", "meta_valor"} <= erro.value.message_dict.keys()


@pytest.mark.parametrize(
    "rota", ["doacoes:editar", "doacoes:recibo", "doacoes:doador_editar", "doacoes:campanha_editar"]
)
def test_tecnico_nao_altera_por_post(client, usuario_tecnico, rota):
    objeto = (
        CampanhaFactory()
        if "campanha" in rota
        else DoadorFactory()
        if "doador" in rota
        else DoacaoFactory()
    )
    client.force_login(usuario_tecnico)
    assert client.post(reverse(rota, args=[objeto.pk]), {}).status_code == 403


def test_limite_busca_e_paginacao_preserva_filtro(client, usuario_operacional):
    DoadorFactory.create_batch(30, nome="Parceiro Exemplo")
    client.force_login(usuario_operacional)
    result = client.get(reverse("doacoes:buscar_doador"), {"termo": "Parceiro"})
    assert len(result.context["doadores"]) == 8
    result = client.get(reverse("doacoes:doador_lista"), {"q": "Parceiro", "page": "999"})
    assert result.status_code == 200
    assert result.context["page_obj"].number == 2
    assert "q=Parceiro" in result.context["filtros_query"]


def test_edicao_preserva_autor_e_cria_historico(client, usuario_operacional, usuario_admin):
    doacao = DoacaoFactory(recebido_por=usuario_operacional, criado_por=usuario_operacional)
    client.force_login(usuario_admin)
    result = client.post(
        reverse("doacoes:editar", args=[doacao.pk]),
        {
            "tipo": "DINHEIRO",
            "valor": "120,50",
            "data_recebimento": timezone.localdate(),
        },
    )
    assert result.status_code == 302
    doacao.refresh_from_db()
    assert doacao.valor == Decimal("120.50")
    assert doacao.recebido_por == doacao.criado_por == usuario_operacional
    assert doacao.history.first().history_user == usuario_admin


def test_entrega_recibo_idempotente(client, usuario_operacional):
    doacao = DoacaoFactory()
    client.force_login(usuario_operacional)
    url = reverse("doacoes:recibo", args=[doacao.pk])
    client.post(url)
    quantidade = doacao.history.count()
    client.post(url)
    assert doacao.history.count() == quantidade


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Windows/win.ini",
        "https://example.com/a",
        "http://127.0.0.1/",
        "https://comviver.invalid/static/../.env",
        "https://comviver.invalid/static/%2e%2e/.env",
        "https://comviver.invalid/media/foto.png",
        "data:text/html,secret",
    ],
)
def test_pdf_bloqueia_recursos_externos(url):
    with pytest.raises(ValueError):
        buscar_recurso_local(url)


def test_demo_repetivel_nao_apaga_dados():
    original = DoacaoFactory()
    criar_doacoes_demo()
    criar_doacoes_demo()
    assert Doacao.objects.count() == 1 + len(TipoDoacao.values)
    assert Doador.objects.count() == 6
    assert Campanha.objects.count() == 1
    assert Doacao.objects.filter(pk=original.pk).exists()
