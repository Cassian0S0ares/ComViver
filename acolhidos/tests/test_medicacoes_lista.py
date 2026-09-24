from datetime import date, time, timedelta

import pytest
from django.urls import reverse

from acolhidos.factories import AcolhidoFactory, MedicacaoFactory
from acolhidos.models import StatusAcolhido

pytestmark = pytest.mark.django_db

HOJE = date.today()
URL = "/medicacoes/"


@pytest.fixture
def remedios():
    ana = AcolhidoFactory(nome="Ana Clara Souza")
    bruno = AcolhidoFactory(nome="Bruno Lima")
    MedicacaoFactory(acolhido=ana, nome="Vitamina D", observacoes="1 gota", horarios=[time(8)])
    MedicacaoFactory(acolhido=bruno, nome="Vitamina D", observacoes="2 gotas", horarios=[time(8)])
    MedicacaoFactory(acolhido=ana, nome="Dipirona", horarios=[time(8), time(20)])
    MedicacaoFactory(
        acolhido=bruno,
        nome="Amoxicilina",
        inicio=HOJE - timedelta(days=30),
        fim=HOJE - timedelta(days=10),
    )
    return ana, bruno


class TestAcesso:
    @pytest.mark.parametrize(
        "fixture_usuario", ["usuario_admin", "usuario_tecnico", "usuario_operacional"]
    )
    def test_toda_a_equipe_abre(self, client, request, fixture_usuario):
        client.force_login(request.getfixturevalue(fixture_usuario))
        assert client.get(reverse("acolhidos:medicacoes")).status_code == 200

    def test_anonimo_vai_para_o_login(self, client):
        resposta = client.get(reverse("acolhidos:medicacoes"))
        assert resposta.status_code == 302
        assert "/entrar/" in resposta.url

    def test_nao_mostra_dado_sigiloso(self, client, usuario_operacional, remedios):
        """A tela e de plantao: nome, remedio e horario, nada da ficha."""
        from acolhidos.factories import FichaAcolhimentoFactory

        ana, _ = remedios
        FichaAcolhimentoFactory(acolhido=ana, motivo="Negligência familiar grave")
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("acolhidos:medicacoes")).content.decode()
        assert "Negligência familiar grave" not in conteudo


class TestTabela:
    def test_lista_crianca_medicamento_e_datas(self, client, usuario_operacional, remedios):
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("acolhidos:medicacoes")).content.decode()
        assert "Ana Clara Souza" in conteudo
        assert "Vitamina D" in conteudo
        assert HOJE.strftime("%d/%m/%Y") in conteudo

    def test_padrao_traz_apenas_o_que_esta_em_uso(self, client, usuario_operacional, remedios):
        client.force_login(usuario_operacional)
        lista = client.get(reverse("acolhidos:medicacoes")).context["object_list"]
        assert [m.nome for m in lista].count("Amoxicilina") == 0
        assert len(lista) == 3

    def test_filtro_traz_as_encerradas(self, client, usuario_operacional, remedios):
        client.force_login(usuario_operacional)
        lista = client.get(reverse("acolhidos:medicacoes") + "?situacao=ENCERRADAS").context[
            "object_list"
        ]
        assert [m.nome for m in lista] == ["Amoxicilina"]

    def test_busca_por_medicamento(self, client, usuario_operacional, remedios):
        client.force_login(usuario_operacional)
        lista = client.get(reverse("acolhidos:medicacoes") + "?q=dipirona").context["object_list"]
        assert [m.nome for m in lista] == ["Dipirona"]

    def test_busca_por_crianca(self, client, usuario_operacional, remedios):
        client.force_login(usuario_operacional)
        lista = client.get(reverse("acolhidos:medicacoes") + "?q=bruno").context["object_list"]
        assert {m.acolhido.nome for m in lista} == {"Bruno Lima"}

    def test_desligado_fica_de_fora(self, client, usuario_operacional):
        """Quem ja saiu da casa nao entra na lista do plantao."""
        desligado = AcolhidoFactory(nome="Isabela Duarte", status=StatusAcolhido.DESLIGADO)
        MedicacaoFactory(acolhido=desligado, nome="Vitamina D")
        client.force_login(usuario_operacional)
        assert list(client.get(reverse("acolhidos:medicacoes")).context["object_list"]) == []


class TestFiltroAutomatico:
    def test_sem_botao_filtrar_na_tela(self, client, usuario_operacional):
        """Mudar a situacao ja recarrega a lista; o botao so existe para quem
        esta sem JavaScript."""
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("acolhidos:medicacoes")).content.decode()
        assert "data-auto-filtrar" in conteudo
        antes_do_noscript = conteudo.split("<noscript>")[0]
        assert ">Filtrar<" not in antes_do_noscript
        assert "<noscript><button" in conteudo

    def test_marca_a_regiao_que_a_busca_atualiza(self, client, usuario_operacional, remedios):
        """A digitacao troca so a tabela; o servidor continua sendo quem filtra."""
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("acolhidos:medicacoes")).content.decode()
        assert conteudo.count("data-lista") == 1
        assert conteudo.count("data-contagem") == 1
        assert conteudo.count("<div data-lista") == conteudo.count("</div></section>")

    def test_resposta_da_busca_traz_a_mesma_regiao(self, client, usuario_operacional, remedios):
        """A tela busca a si mesma e recorta a tabela da resposta."""
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("acolhidos:medicacoes") + "?q=dipirona").content.decode()
        assert "data-lista" in conteudo
        assert "Dipirona" in conteudo
        assert "Amoxicilina" not in conteudo


class TestResumo:
    def test_conta_criancas_por_medicamento(self, client, usuario_operacional, remedios):
        client.force_login(usuario_operacional)
        resumo = client.get(reverse("acolhidos:medicacoes")).context["resumo"]
        por_nome = {linha["nome"]: linha["criancas"] for linha in resumo}
        assert por_nome == {"Vitamina D": 2, "Dipirona": 1}

    def test_resumo_ordena_do_mais_usado_para_o_menos(self, client, usuario_operacional, remedios):
        client.force_login(usuario_operacional)
        resumo = client.get(reverse("acolhidos:medicacoes")).context["resumo"]
        assert [linha["nome"] for linha in resumo] == ["Vitamina D", "Dipirona"]

    def test_totais_da_casa(self, client, usuario_operacional, remedios):
        client.force_login(usuario_operacional)
        contexto = client.get(reverse("acolhidos:medicacoes")).context
        assert contexto["total_criancas"] == 2
        assert contexto["total_medicamentos"] == 2

    def test_mesma_crianca_com_o_mesmo_remedio_conta_uma_vez(self, client, usuario_operacional):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(acolhido=acolhido, nome="Vitamina D", horarios=[time(8)])
        MedicacaoFactory(acolhido=acolhido, nome="Vitamina D", horarios=[time(20)])
        client.force_login(usuario_operacional)
        resumo = client.get(reverse("acolhidos:medicacoes")).context["resumo"]
        assert resumo[0]["criancas"] == 1


class TestAtalhos:
    def test_cartao_do_painel_leva_para_a_tela(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        cartoes = client.get(reverse("core:painel")).context["cartoes"]
        cartao = next(c for c in cartoes if c["titulo"] == "Medicações do dia")
        assert cartao["url"] == reverse("acolhidos:medicacoes")

    def test_menu_mostra_medicacoes_para_toda_a_equipe(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert reverse("acolhidos:medicacoes") in conteudo

    def test_so_a_equipe_tecnica_ve_o_link_de_editar(
        self, client, usuario_tecnico, usuario_operacional, remedios
    ):
        ana, _ = remedios
        medicacao = ana.medicacoes.first()
        url_edicao = reverse("acolhidos:medicacao_editar", args=[medicacao.pk])
        client.force_login(usuario_tecnico)
        assert url_edicao in client.get(reverse("acolhidos:medicacoes")).content.decode()
        client.force_login(usuario_operacional)
        assert url_edicao not in client.get(reverse("acolhidos:medicacoes")).content.decode()
