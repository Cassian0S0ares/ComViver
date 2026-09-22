import pytest
from django.urls import reverse

from acolhidos.factories import AcolhidoFactory, ResponsavelFactory, VinculoFamiliarFactory
from acolhidos.models import VinculoFamiliar

pytestmark = pytest.mark.django_db


class TestVinculos:
    def test_operacional_nao_cria_vinculo(self, client, usuario_operacional):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_operacional)
        url = reverse("acolhidos:vinculo_novo", args=[acolhido.pk])
        assert client.get(url).status_code == 403

    def test_tecnico_cria_vinculo_com_responsavel_novo(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:vinculo_novo", args=[acolhido.pk]),
            {
                "responsavel": "",
                "nome_novo": "Maria Souza",
                "telefone_novo": "35999990000",
                "parentesco": "Mãe",
                "autorizado_visita": "on",
            },
        )
        vinculo = VinculoFamiliar.objects.get(acolhido=acolhido)
        assert vinculo.responsavel.nome == "Maria Souza"
        assert vinculo.responsavel.criado_por == usuario_tecnico

    def test_tecnico_reaproveita_responsavel_existente(self, client, usuario_tecnico):
        """Irmaos acolhidos compartilham responsavel: cadastrar duas vezes
        criaria duplicata e telefone desatualizado em um dos registros."""
        mae = ResponsavelFactory(nome="Maria Souza")
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:vinculo_novo", args=[acolhido.pk]),
            {
                "responsavel": str(mae.pk),
                "nome_novo": "",
                "telefone_novo": "",
                "parentesco": "Mãe",
                "autorizado_visita": "on",
            },
        )
        assert VinculoFamiliar.objects.get(acolhido=acolhido).responsavel == mae

    def test_vinculo_duplicado_mostra_erro(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        mae = ResponsavelFactory()
        VinculoFamiliarFactory(acolhido=acolhido, responsavel=mae)
        client.force_login(usuario_tecnico)
        resposta = client.post(
            reverse("acolhidos:vinculo_novo", args=[acolhido.pk]),
            {
                "responsavel": str(mae.pk),
                "nome_novo": "",
                "telefone_novo": "",
                "parentesco": "Mãe",
                "autorizado_visita": "on",
            },
        )
        assert resposta.status_code == 200
        assert "já está vinculada" in resposta.content.decode()

    def test_formulario_exige_escolher_ou_cadastrar(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        resposta = client.post(
            reverse("acolhidos:vinculo_novo", args=[acolhido.pk]),
            {"responsavel": "", "nome_novo": "", "telefone_novo": "", "parentesco": "Mãe"},
        )
        assert "Escolha um responsável já cadastrado ou informe o nome" in resposta.content.decode()


class TestEditarVinculo:
    def test_tecnico_retira_a_autorizacao_de_retirada(self, client, usuario_tecnico):
        vinculo = VinculoFamiliarFactory(autorizado_retirar=True, parentesco="Tio")
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:vinculo_editar", args=[vinculo.pk]),
            {
                "responsavel": str(vinculo.responsavel.pk),
                "nome_novo": "",
                "telefone_novo": "",
                "parentesco": "Tio",
                "autorizado_visita": "on",
            },
        )
        vinculo.refresh_from_db()
        assert vinculo.autorizado_retirar is False

    def test_operacional_nao_edita(self, client, usuario_operacional):
        vinculo = VinculoFamiliarFactory()
        client.force_login(usuario_operacional)
        url = reverse("acolhidos:vinculo_editar", args=[vinculo.pk])
        assert client.get(url).status_code == 403
