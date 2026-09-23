import pytest
from django.urls import reverse

from acolhidos.factories import (
    AcolhidoFactory,
    FichaAcolhimentoFactory,
    MedicacaoFactory,
    VinculoFamiliarFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def acolhido_completo():
    acolhido = AcolhidoFactory(nome="Ana Clara Souza")
    FichaAcolhimentoFactory(
        acolhido=acolhido,
        motivo="Negligência familiar grave",
        processo_numero="0001234-56.2026.8.13.0301",
        vara="Vara da Infância e Juventude de Itajubá",
    )
    MedicacaoFactory(acolhido=acolhido, nome="Dipirona")
    VinculoFamiliarFactory(acolhido=acolhido, parentesco="Avó", autorizado_retirar=True)
    return acolhido


class TestListaDeAcolhidos:
    @pytest.mark.parametrize(
        "fixture_usuario",
        ["usuario_admin", "usuario_tecnico", "usuario_operacional"],
    )
    def test_todos_os_perfis_veem_a_lista(self, client, request, fixture_usuario):
        usuario = request.getfixturevalue(fixture_usuario)
        client.force_login(usuario)
        assert client.get(reverse("acolhidos:lista")).status_code == 200

    def test_lista_mostra_o_nome_e_a_situacao(self, client, usuario_operacional):
        AcolhidoFactory(nome="Ana Clara Souza")
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("acolhidos:lista")).content.decode()
        assert "Ana Clara Souza" in conteudo
        assert "Acolhido" in conteudo

    def test_lista_nao_mostra_motivo_para_ninguem(self, client, usuario_admin, acolhido_completo):
        """Motivo do acolhimento nao aparece em listagem, nem para o Admin:
        listagem e tela que fica aberta e visivel a quem passa pela sala."""
        client.force_login(usuario_admin)
        conteudo = client.get(reverse("acolhidos:lista")).content.decode()
        assert "Negligência familiar grave" not in conteudo

    def test_busca_encontra_por_parte_do_nome(self, client, usuario_operacional):
        AcolhidoFactory(nome="Ana Clara Souza")
        AcolhidoFactory(nome="Bruno Lima")
        client.force_login(usuario_operacional)
        resultado = client.get(reverse("acolhidos:lista") + "?q=clara")
        assert len(resultado.context["object_list"]) == 1


class TestFichaSigilosa:
    """Matriz da spec 5.1, linha a linha."""

    @pytest.mark.parametrize("fixture_usuario", ["usuario_admin", "usuario_tecnico"])
    def test_perfil_autorizado_ve_o_processo(
        self, client, request, fixture_usuario, acolhido_completo
    ):
        # O motivo saiu da ficha; o processo segue como dado sigiloso visivel
        # so para a equipe tecnica.
        client.force_login(request.getfixturevalue(fixture_usuario))
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "0001234-56.2026.8.13.0301" in conteudo

    def test_operacional_nao_ve_o_motivo(self, client, usuario_operacional, acolhido_completo):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Negligência familiar grave" not in conteudo

    def test_operacional_nao_ve_o_processo(self, client, usuario_operacional, acolhido_completo):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "0001234-56.2026.8.13.0301" not in conteudo

    def test_operacional_nao_ve_a_vara(self, client, usuario_operacional, acolhido_completo):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Vara da Infância" not in conteudo

    def test_contexto_marca_que_operacional_nao_pode_ver(
        self, client, usuario_operacional, acolhido_completo
    ):
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("acolhidos:detalhe", args=[acolhido_completo.pk]))
        assert resposta.context["pode_ver_ficha"] is False


class TestCuidadoDiario:
    """O que o Operacional precisa e pode ver."""

    def test_operacional_ve_a_medicacao_em_vigor(
        self, client, usuario_operacional, acolhido_completo
    ):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Dipirona" in conteudo

    def test_operacional_ve_quem_pode_retirar(self, client, usuario_operacional, acolhido_completo):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Avó" in conteudo

    def test_operacional_nao_ve_condicoes_de_saude(self, client, usuario_operacional):
        from acolhidos.factories import DadosSaudeFactory

        acolhido = AcolhidoFactory()
        DadosSaudeFactory(acolhido=acolhido, condicoes="Transtorno de ansiedade")
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("acolhidos:detalhe", args=[acolhido.pk])).content.decode()
        assert "Transtorno de ansiedade" not in conteudo


class TestMenuEPainel:
    def test_menu_tem_acolhidos_para_todos(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert reverse("acolhidos:lista") in conteudo

    def test_painel_conta_acolhidos_ativos(self, client, usuario_operacional):
        AcolhidoFactory.create_batch(3)
        client.force_login(usuario_operacional)
        cartoes = client.get(reverse("core:painel")).context["cartoes"]
        acolhidos = next(c for c in cartoes if c["titulo"] == "Acolhidos")
        assert acolhidos["valor"] == 3
        assert acolhidos["url"] == reverse("acolhidos:lista")
