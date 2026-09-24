from datetime import timedelta
from importlib import import_module

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from doacoes.factories import DoadorFactory
from doacoes.models import Doacao, TipoDoacao
from estoque.models import CategoriaItem, ItemEstoque, LoteEstoque, TipoMovimentacao
from estoque.services import dar_baixa, item_por_nome, perto_da_validade, registrar_entrada

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate


# Criadas aqui, e nao lidas da migracao: com --reuse-db, um teste transacional
# esvazia o banco e leva junto os dados semeados.
@pytest.fixture
def alimentos():
    return CategoriaItem.objects.get_or_create(nome="Alimentos", defaults={"tem_validade": True})[0]


@pytest.fixture
def limpeza():
    return CategoriaItem.objects.get_or_create(nome="Limpeza")[0]


def _entrada(categoria, nome, quantidade, usuario=None, validade=None):
    return registrar_entrada(item_por_nome(categoria, nome), quantidade, usuario, validade=validade)


# ------------------------------------------------------------------ servicos

def test_categorias_iniciais_nao_duplicam():
    from django.apps import apps

    cadastrar = import_module("estoque.migrations.0002_categorias_iniciais").cadastrar_categorias
    cadastrar(apps, None)
    cadastrar(apps, None)
    assert CategoriaItem.objects.filter(nome__iexact="alimentos").count() == 1
    assert CategoriaItem.objects.get(nome="Alimentos").tem_validade
    assert not CategoriaItem.objects.get(nome="Limpeza").tem_validade


def test_mesmo_nome_na_categoria_reaproveita_o_item(alimentos):
    assert item_por_nome(alimentos, "Arroz 5kg") == item_por_nome(alimentos, "  arroz   5KG ")
    assert ItemEstoque.objects.count() == 1


def test_baixa_tira_primeiro_o_que_vence_antes(alimentos, usuario_operacional):
    depois = _entrada(alimentos, "Leite", 5, validade=HOJE() + timedelta(days=20))
    antes = _entrada(alimentos, "Leite", 3, validade=HOJE() + timedelta(days=2))
    dar_baixa(antes.item, 4, usuario_operacional, "Café da manhã")
    antes.refresh_from_db()
    depois.refresh_from_db()
    assert (antes.saldo, depois.saldo) == (0, 4)
    saidas = antes.item.movimentacoes.filter(tipo=TipoMovimentacao.SAIDA)
    assert sorted(m.quantidade for m in saidas) == [1, 3]
    assert all(m.usuario == usuario_operacional for m in saidas)


def test_baixa_maior_que_o_disponivel_e_recusada(limpeza, usuario_operacional):
    lote = _entrada(limpeza, "Detergente", 2)
    with pytest.raises(ValidationError, match="Só há 2 unidades"):
        dar_baixa(lote.item, 3, usuario_operacional)
    lote.refresh_from_db()
    assert lote.saldo == 2


def test_perto_da_validade_inclui_vencidos_e_ignora_sem_saldo(alimentos):
    vencido = _entrada(alimentos, "Iogurte", 2, validade=HOJE() - timedelta(days=1))
    perto = _entrada(alimentos, "Pão", 2, validade=HOJE() + timedelta(days=3))
    _entrada(alimentos, "Feijão", 2, validade=HOJE() + timedelta(days=60))
    zerado = _entrada(alimentos, "Queijo", 1, validade=HOJE())
    zerado.saldo = 0
    zerado.save()
    assert list(perto_da_validade()) == [vencido, perto]


# ------------------------------------------------------------------ telas

def test_lista_e_visivel_para_todos_mas_so_admin_e_tecnico_adicionam(
    client, alimentos, usuario_admin, usuario_tecnico, usuario_operacional
):
    _entrada(alimentos, "Arroz 5kg", 10)
    for usuario, abastece in [(usuario_admin, True), (usuario_tecnico, True),
                              (usuario_operacional, False)]:
        client.force_login(usuario)
        html = client.get(reverse("estoque:lista")).content.decode()
        assert "Arroz 5kg" in html
        assert (reverse("estoque:entrada") in html) is abastece
        status = client.get(reverse("estoque:entrada")).status_code
        assert status == (200 if abastece else 403)


def test_lista_so_mostra_itens_disponiveis_e_filtra(client, alimentos, limpeza, usuario_operacional):
    _entrada(alimentos, "Arroz 5kg", 10)
    _entrada(limpeza, "Sabão em pó", 4)
    esgotado = _entrada(alimentos, "Macarrão", 1)
    dar_baixa(esgotado.item, 1, None)
    client.force_login(usuario_operacional)
    url = reverse("estoque:lista")
    html = client.get(url).content.decode()
    assert "Arroz 5kg" in html and "Sabão em pó" in html and "Macarrão" not in html
    html = client.get(url, {"categoria": limpeza.pk}).content.decode()
    assert "Sabão em pó" in html and "Arroz 5kg" not in html
    html = client.get(url, {"q": "arroz"}).content.decode()
    assert "Arroz 5kg" in html and "Sabão em pó" not in html


def test_entrada_manual_cria_item_e_lote(client, alimentos, usuario_tecnico):
    client.force_login(usuario_tecnico)
    validade = (HOJE() + timedelta(days=30)).isoformat()
    resposta = client.post(reverse("estoque:entrada"), {
        "categoria": alimentos.pk, "item_nome": "Óleo 900ml", "quantidade": 6,
        "validade": validade,
    })
    assert resposta.status_code == 302
    lote = LoteEstoque.objects.get()
    assert (lote.item.nome, lote.saldo, lote.validade.isoformat()) == ("Óleo 900ml", 6, validade)
    assert lote.criado_por == usuario_tecnico


def test_entrada_descarta_validade_de_categoria_que_nao_vence(client, limpeza, usuario_admin):
    client.force_login(usuario_admin)
    client.post(reverse("estoque:entrada"), {
        "categoria": limpeza.pk, "item_nome": "Vassoura", "quantidade": 2,
        "validade": (HOJE() + timedelta(days=5)).isoformat(),
    })
    assert LoteEstoque.objects.get().validade is None


def test_baixa_pela_tela_para_qualquer_perfil(client, limpeza, usuario_operacional):
    lote = _entrada(limpeza, "Detergente", 5)
    client.force_login(usuario_operacional)
    url = reverse("estoque:baixa", args=[lote.item.pk])
    resposta = client.post(url, {"quantidade": 2, "observacao": "Cozinha"}, follow=True)
    assert "Baixa de 2 unidade(s) de Detergente registrada." in resposta.content.decode()
    resposta = client.post(url, {"quantidade": 9}, follow=True)
    assert "Só há 3 unidades de Detergente no estoque." in resposta.content.decode()
    lote.refresh_from_db()
    assert lote.saldo == 3


def test_baixa_nao_redireciona_para_fora(client, limpeza, usuario_operacional):
    lote = _entrada(limpeza, "Detergente", 5)
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("estoque:baixa", args=[lote.item.pk]),
                           {"quantidade": 1, "proximo": "https://exemplo.com/"})
    assert resposta.url == reverse("estoque:lista")


def test_categoria_nova_so_para_admin_e_tecnico(client, usuario_tecnico, usuario_operacional):
    client.force_login(usuario_operacional)
    assert client.get(reverse("estoque:categoria_nova")).status_code == 403
    client.force_login(usuario_tecnico)
    client.post(reverse("estoque:categoria_nova"), {"nome": "Brinquedos"})
    assert CategoriaItem.objects.filter(nome="Brinquedos", tem_validade=False).exists()
    resposta = client.post(reverse("estoque:categoria_nova"), {"nome": "brinquedos"})
    assert "Já existe uma categoria com este nome." in resposta.content.decode()


def test_painel_mostra_alimentos_perto_da_validade(client, alimentos, usuario_operacional):
    _entrada(alimentos, "Iogurte", 3, validade=HOJE() + timedelta(days=2))
    _entrada(alimentos, "Feijão", 3, validade=HOJE() + timedelta(days=90))
    client.force_login(usuario_operacional)
    html = client.get(reverse("core:painel")).content.decode()
    assert "Alimentos perto da data de validade" in html
    assert "Iogurte" in html and "Em 2 dias" in html
    assert "Feijão" not in html


def test_menu_tem_estoque(client, usuario_operacional):
    client.force_login(usuario_operacional)
    assert reverse("estoque:lista") in client.get(reverse("core:painel")).content.decode()


# ------------------------------------------------------------------ doacao

def _doacao(**extra):
    return {"doador": DoadorFactory().pk, "tipo": TipoDoacao.ALIMENTO, "quantidade": 12,
            "data_recebimento": HOJE().isoformat()} | extra


def test_doacao_de_item_entra_no_estoque(client, alimentos, usuario_operacional):
    client.force_login(usuario_operacional)
    validade = (HOJE() + timedelta(days=10)).isoformat()
    resposta = client.post(reverse("doacoes:nova"), _doacao(
        categoria_estoque=alimentos.pk, item_nome="Arroz 5kg", validade=validade,
        unidade="horas",
    ))
    assert resposta.status_code == 302
    doacao = Doacao.objects.get()
    assert (doacao.unidade, doacao.descricao) == ("unidades", "Arroz 5kg")
    lote = doacao.lote_estoque
    assert (lote.item.nome, lote.saldo, lote.validade.isoformat()) == ("Arroz 5kg", 12, validade)


def test_doacao_de_item_exige_categoria_e_item(client, usuario_operacional):
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("doacoes:nova"), _doacao())
    erros = resposta.context["form"].errors
    assert "categoria_estoque" in erros and "item_nome" in erros
    assert not Doacao.objects.exists()


def test_doacao_em_dinheiro_e_servico_nao_vao_para_o_estoque(client, alimentos, usuario_operacional):
    client.force_login(usuario_operacional)
    client.post(reverse("doacoes:nova"), _doacao(
        tipo=TipoDoacao.SERVICO, descricao="Corte de cabelo", quantidade=3, unidade="horas",
        categoria_estoque=alimentos.pk, item_nome="Arroz",
    ))
    doacao = Doacao.objects.get()
    assert doacao.unidade == "horas"
    assert not LoteEstoque.objects.exists()


def test_editar_doacao_ajusta_o_lote(client, alimentos, usuario_operacional):
    client.force_login(usuario_operacional)
    client.post(reverse("doacoes:nova"), _doacao(categoria_estoque=alimentos.pk, item_nome="Arroz"))
    doacao = Doacao.objects.get()
    dar_baixa(doacao.lote_estoque.item, 5, usuario_operacional)
    url = reverse("doacoes:editar", args=[doacao.pk])
    dados = _doacao(doador=doacao.doador_id, categoria_estoque=alimentos.pk, item_nome="Arroz")
    resposta = client.post(url, dados | {"quantidade": 4})
    assert "Já saíram 5 unidades" in resposta.content.decode()
    resposta = client.post(url, dados | {"quantidade": 20})
    assert resposta.status_code == 302
    lote = LoteEstoque.objects.get()
    assert (lote.quantidade_inicial, lote.saldo) == (20, 15)
