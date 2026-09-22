from datetime import date
from pathlib import Path

import pytest
from django.conf import settings

from acolhidos.factories import AcolhidoFactory
from acolhidos.models import Acolhido, FichaAcolhimento, VinculoFamiliar

pytestmark = pytest.mark.django_db

URL = "/acolhidos/novo/"

DADOS_IDENTIFICACAO = {
    "acolhimento_wizard-current_step": "identificacao",
    "identificacao-nome": "Ana Clara Souza",
    "identificacao-nome_social": "",
    "identificacao-nascimento": "2015-03-10",
    "identificacao-sexo": "F",
    "identificacao-naturalidade": "Itajubá",
    "identificacao-cpf": "",
    "identificacao-rg": "",
    "identificacao-certidao_nascimento": "",
    "identificacao-cartao_sus": "",
}

DADOS_ACOLHIMENTO = {
    "acolhimento_wizard-current_step": "acolhimento",
    "acolhimento-data_entrada": "2026-09-01",
    "acolhimento-motivo": "Negligência familiar",
    "acolhimento-orgao_requisitante": "Conselho Tutelar",
    "acolhimento-processo_numero": "0001234-56.2026.8.13.0301",
    "acolhimento-vara": "Vara da Infância",
}

DADOS_SAUDE = {
    "acolhimento_wizard-current_step": "saude",
    "saude-tipo_sanguineo": "O+",
    "saude-alergias": "Dipirona",
    "saude-condicoes": "",
    "saude-plano_saude": "",
    "saude-escola": "E.E. Dom Pedro",
    "saude-serie": "4º ano",
    "saude-turno": "MANHA",
}

DADOS_RESPONSAVEL = {
    "acolhimento_wizard-current_step": "responsavel",
    "responsavel-nome": "Maria Souza",
    "responsavel-cpf": "",
    "responsavel-telefone": "35999990000",
    "responsavel-parentesco": "Avó",
    "responsavel-e_guardiao": "on",
    "responsavel-autorizado_visita": "on",
    "responsavel-autorizado_retirar": "on",
}


def percorrer(client):
    client.post(URL, DADOS_IDENTIFICACAO)
    client.post(URL, DADOS_ACOLHIMENTO)
    client.post(URL, DADOS_SAUDE)
    return client.post(URL, DADOS_RESPONSAVEL)


class TestAcessoAoAssistente:
    def test_operacional_recebe_403(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get(URL).status_code == 403

    def test_tecnico_acessa(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        assert client.get(URL).status_code == 200

    def test_lista_mostra_o_botao_so_para_quem_pode_cadastrar(
        self, client, usuario_tecnico, usuario_operacional
    ):
        client.force_login(usuario_tecnico)
        assert URL in client.get("/acolhidos/").content.decode()
        client.force_login(usuario_operacional)
        assert URL not in client.get("/acolhidos/").content.decode()


class TestFluxoCompleto:
    def test_formulario_nao_exibe_campos_removidos(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        etapa_saude = client.get(URL, {"step": "saude"}).content.decode()
        detalhe = client.get(f"/acolhidos/{AcolhidoFactory().pk}/").content.decode()

        assert "Medida protetiva" not in etapa_saude
        assert "Ano letivo" not in etapa_saude
        assert "Medida protetiva" not in detalhe
        assert "Ano letivo" not in detalhe

    def test_percorrer_as_quatro_etapas_cria_o_acolhido(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        resposta = percorrer(client)

        assert resposta.status_code == 302
        acolhido = Acolhido.objects.get(nome="Ana Clara Souza")
        assert acolhido.idade >= 10
        assert resposta.url == f"/acolhidos/{acolhido.pk}/"

    def test_cria_a_ficha_de_acolhimento(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        percorrer(client)

        ficha = FichaAcolhimento.objects.get(acolhido__nome="Ana Clara Souza")
        assert ficha.data_entrada == date(2026, 9, 1)
        assert ficha.processo_numero == "0001234-56.2026.8.13.0301"

    def test_cria_o_vinculo_com_o_responsavel(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        percorrer(client)

        vinculo = VinculoFamiliar.objects.get(acolhido__nome="Ana Clara Souza")
        assert vinculo.responsavel.nome == "Maria Souza"
        assert vinculo.parentesco == "Avó"
        assert vinculo.e_guardiao is True

    def test_cria_saude_e_escola(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        percorrer(client)

        acolhido = Acolhido.objects.get(nome="Ana Clara Souza")
        assert acolhido.saude.alergias == "Dipirona"
        assert acolhido.escolaridades.get().escola == "E.E. Dom Pedro"

    def test_registra_quem_cadastrou(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        percorrer(client)

        assert Acolhido.objects.get(nome="Ana Clara Souza").criado_por == usuario_tecnico


class TestValidacaoNoMeioDoCaminho:
    def test_etapa_com_erro_nao_avanca(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        dados = DADOS_IDENTIFICACAO | {"identificacao-nome": ""}
        resposta = client.post(URL, dados)
        assert resposta.status_code == 200
        assert resposta.context["wizard"]["steps"].current == "identificacao"

    def test_nada_e_gravado_antes_da_ultima_etapa(self, client, usuario_tecnico):
        """O registro so nasce ao concluir: acolhido sem ficha nem responsavel
        seria pior que nenhum registro."""
        client.force_login(usuario_tecnico)
        client.post(URL, DADOS_IDENTIFICACAO)
        client.post(URL, DADOS_ACOLHIMENTO)
        assert Acolhido.objects.count() == 0

    def test_data_de_entrada_no_futuro_e_recusada(self, client, usuario_tecnico):
        from datetime import timedelta

        client.force_login(usuario_tecnico)
        client.post(URL, DADOS_IDENTIFICACAO)
        futuro = (date.today() + timedelta(days=10)).isoformat()
        resposta = client.post(URL, DADOS_ACOLHIMENTO | {"acolhimento-data_entrada": futuro})
        assert resposta.status_code == 200
        assert "não pode ser no futuro" in resposta.content.decode()


class TestRascunhoDeArquivos:
    def test_rascunho_fica_fora_da_pasta_servida(self):
        """A rota /media/ entrega qualquer arquivo de MEDIA_ROOT a quem esta
        logado. A foto do rascunho, ainda com o nome original, nao pode estar
        la dentro."""
        from acolhidos.views import AcolhimentoWizard

        rascunho = Path(AcolhimentoWizard.file_storage.location).resolve()
        media = Path(settings.MEDIA_ROOT).resolve()
        assert not rascunho.is_relative_to(media)
