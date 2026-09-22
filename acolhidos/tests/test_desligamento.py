from datetime import date, timedelta

import pytest
from django.urls import reverse

from accounts.models import AcaoFicha, LogAcessoFicha
from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory
from acolhidos.models import StatusAcolhido

pytestmark = pytest.mark.django_db


@pytest.fixture
def acolhido_com_ficha():
    acolhido = AcolhidoFactory()
    FichaAcolhimentoFactory(acolhido=acolhido, data_entrada=date.today() - timedelta(days=200))
    return acolhido


def desligar(client, acolhido, **dados):
    return client.post(
        reverse("acolhidos:desligar", args=[acolhido.pk]),
        {"data_desligamento": date.today().isoformat(), "destino": "REINTEGRACAO", "observacao": ""}
        | dados,
    )


class TestAcessoAoDesligamento:
    def test_operacional_recebe_403(self, client, usuario_operacional, acolhido_com_ficha):
        client.force_login(usuario_operacional)
        url = reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk])
        assert client.get(url).status_code == 403

    def test_tecnico_acessa(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        url = reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk])
        assert client.get(url).status_code == 200


class TestDesligamento:
    def test_desligar_muda_o_status(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        desligar(client, acolhido_com_ficha, observacao="Reintegração à família materna.")
        acolhido_com_ficha.refresh_from_db()
        assert acolhido_com_ficha.status == StatusAcolhido.DESLIGADO

    def test_desligar_preenche_a_ficha(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        desligar(client, acolhido_com_ficha, destino="ADOCAO", observacao="Guarda definitiva.")
        acolhido_com_ficha.ficha.refresh_from_db()
        assert acolhido_com_ficha.ficha.data_desligamento == date.today()
        assert acolhido_com_ficha.ficha.destino == "ADOCAO"
        assert acolhido_com_ficha.ficha.observacao_desligamento == "Guarda definitiva."

    def test_desligado_some_da_lista_padrao(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        desligar(client, acolhido_com_ficha, destino="MAIORIDADE")
        lista = client.get(reverse("acolhidos:lista")).context["object_list"]
        assert acolhido_com_ficha not in lista

    def test_desligado_aparece_no_filtro_de_desligados(
        self, client, usuario_tecnico, acolhido_com_ficha
    ):
        client.force_login(usuario_tecnico)
        desligar(client, acolhido_com_ficha, destino="MAIORIDADE")
        lista = client.get(reverse("acolhidos:lista") + "?situacao=DESLIGADO").context[
            "object_list"
        ]
        assert acolhido_com_ficha in lista

    def test_historico_e_preservado(self, client, usuario_tecnico, acolhido_com_ficha):
        """Desligamento nao apaga nada: o registro precisa continuar consultavel
        para prestacao de contas e para eventual retorno da crianca."""
        client.force_login(usuario_tecnico)
        desligar(client, acolhido_com_ficha)
        acolhido_com_ficha.refresh_from_db()
        assert acolhido_com_ficha.deleted_at is None
        assert acolhido_com_ficha.ficha.data_entrada is not None

    def test_data_de_desligamento_anterior_a_entrada_e_recusada(
        self, client, usuario_tecnico, acolhido_com_ficha
    ):
        client.force_login(usuario_tecnico)
        anterior = (acolhido_com_ficha.ficha.data_entrada - timedelta(days=1)).isoformat()
        resposta = desligar(client, acolhido_com_ficha, data_desligamento=anterior)
        assert resposta.status_code == 200
        assert "anterior à data de entrada" in resposta.content.decode()
        acolhido_com_ficha.refresh_from_db()
        assert acolhido_com_ficha.status == StatusAcolhido.ACOLHIDO

    def test_registra_a_alteracao_no_log(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        desligar(client, acolhido_com_ficha)
        assert LogAcessoFicha.objects.filter(
            acolhido=acolhido_com_ficha, acao=AcaoFicha.EDIT, usuario=usuario_tecnico
        ).exists()

    def test_nao_desliga_duas_vezes(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        desligar(client, acolhido_com_ficha, destino="ADOCAO")
        desligar(client, acolhido_com_ficha, destino="OUTRO")
        acolhido_com_ficha.ficha.refresh_from_db()
        assert acolhido_com_ficha.ficha.destino == "ADOCAO"

    def test_ficha_mostra_o_destino_por_extenso(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        desligar(client, acolhido_com_ficha, destino="ADOCAO")
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_com_ficha.pk])
        ).content.decode()
        assert "Adoção" in conteudo
