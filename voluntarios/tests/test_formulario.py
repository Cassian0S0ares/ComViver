import pytest
from django.urls import reverse

from voluntarios.factories import DisponibilidadeFactory, FuncaoFactory, VoluntarioFactory
from voluntarios.models import DiaSemana, Turno, Voluntario

pytestmark = pytest.mark.django_db


def _dados_minimos(**overrides):
    dados = {
        "nome": "Novo Voluntario",
        "cpf": "",
        "rg": "",
        "telefone": "",
        "email": "",
        "funcoes": [],
        "status": "ATIVO",
        "cep": "",
        "logradouro": "",
        "numero": "",
        "complemento": "",
        "bairro": "",
        "cidade": "",
        "uf": "",
        "observacoes": "",
    }
    dados.update(overrides)
    return dados


class TestCriarVoluntario:
    def test_cria_com_cpf_vazio_disponibilidade_e_funcao(self, client, usuario_operacional):
        """Regressao: Voluntario.cpf tem null=True, entao o ModelForm usa None
        (nao "") como valor vazio do campo. `clean_cpf` precisa lidar com isso
        sem estourar TypeError."""
        funcao = FuncaoFactory(nome="Cozinha")
        client.force_login(usuario_operacional)
        dados = _dados_minimos(**{"funcoes": [funcao.pk], "disp_1_TARDE": "on"})

        resposta = client.post(reverse("voluntarios:novo"), dados)

        voluntario = Voluntario.objects.get(nome="Novo Voluntario")
        assert resposta.status_code == 302
        assert resposta.url == reverse("voluntarios:detalhe", args=[voluntario.pk])
        assert voluntario.cpf is None
        assert list(voluntario.funcoes.all()) == [funcao]
        disponibilidades = list(voluntario.disponibilidades.all())
        assert len(disponibilidades) == 1
        assert disponibilidades[0].dia_semana == DiaSemana.TERCA
        assert disponibilidades[0].turno == Turno.TARDE

    def test_cpf_com_mascara_e_salvo_so_com_digitos(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        dados = _dados_minimos(cpf="123.456.789-01")

        client.post(reverse("voluntarios:novo"), dados)

        voluntario = Voluntario.objects.get(nome="Novo Voluntario")
        assert voluntario.cpf == "12345678901"

    def test_cpf_com_tamanho_errado_mostra_erro(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        dados = _dados_minimos(cpf="123")

        resposta = client.post(reverse("voluntarios:novo"), dados)

        assert resposta.status_code == 200
        assert "O CPF precisa ter 11 dígitos." in resposta.content.decode()
        assert not Voluntario.objects.filter(nome="Novo Voluntario").exists()

    def test_tecnico_nao_pode_postar_criacao(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)

        resposta = client.post(reverse("voluntarios:novo"), _dados_minimos())

        assert resposta.status_code == 403
        assert not Voluntario.objects.filter(nome="Novo Voluntario").exists()


class TestEditarVoluntario:
    def test_edicao_substitui_disponibilidade(self, client, usuario_operacional):
        voluntario = VoluntarioFactory(nome="Ana Souza")
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.SEGUNDA, turno=Turno.MANHA
        )
        client.force_login(usuario_operacional)
        dados = _dados_minimos(nome="Ana Souza", **{"disp_2_NOITE": "on"})

        resposta = client.post(reverse("voluntarios:editar", args=[voluntario.pk]), dados)

        assert resposta.status_code == 302
        disponibilidades = list(voluntario.disponibilidades.all())
        assert len(disponibilidades) == 1
        assert disponibilidades[0].dia_semana == DiaSemana.QUARTA
        assert disponibilidades[0].turno == Turno.NOITE
