from datetime import date

import pytest
from django.urls import reverse

from acolhidos import estatisticas
from acolhidos.factories import AcolhidoFactory, DadosSaudeFactory, FichaAcolhimentoFactory
from acolhidos.models import Acolhido, StatusAcolhido

pytestmark = pytest.mark.django_db

HOJE = date(2026, 9, 23)


def _linha(linhas, rotulo):
    return next(linha for linha in linhas if linha["rotulo"] == rotulo)


class TestCalcular:
    def test_faixas_etarias(self):
        hoje = date.today()
        for idade in [0, 8, 9, 12, 13, 17, 18]:
            AcolhidoFactory(nascimento=date(hoje.year - idade, 1, 1))
        e = estatisticas.calcular(Acolhido.objects.all())
        assert [linha["quantidade"] for linha in e["faixas_etarias"]] == [2, 2, 1, 1, 1]
        assert e["total"] == 7

    def test_alergias_contam_uma_vez_por_acolhido(self):
        DadosSaudeFactory(alergias="Dipirona\nLeite")
        DadosSaudeFactory(alergias="dipirona")
        DadosSaudeFactory(alergias="Nenhuma conhecida")
        AcolhidoFactory()
        e = estatisticas.calcular(Acolhido.objects.select_related("saude"), hoje=HOJE)
        assert _linha(e["alergias"], "Dipirona")["quantidade"] == 2
        assert _linha(e["alergias"], "Leite")["quantidade"] == 1
        assert e["com_alergia"] == 2
        assert e["sem_alergia"] == 2

    def test_ano_de_entrada_e_permanencia(self):
        FichaAcolhimentoFactory(data_entrada=date(2024, 1, 10))
        FichaAcolhimentoFactory(data_entrada=date(2026, 6, 1))
        AcolhidoFactory()
        e = estatisticas.calcular(Acolhido.objects.select_related("ficha"), hoje=HOJE)
        anos = [(linha["rotulo"], linha["quantidade"]) for linha in e["anos_entrada"]]
        assert anos == [(2024, 1), (2026, 1)]
        assert _linha(e["permanencia"], "Mais de 18 meses")["quantidade"] == 1
        assert _linha(e["permanencia"], "Até 6 meses")["quantidade"] == 1
        assert e["sem_ficha"] == 1

    def test_sem_acolhidos(self):
        e = estatisticas.calcular([], hoje=HOJE)
        assert e["total"] == 0
        assert e["idade_media"] is None


class TestTela:
    def test_operacional_recebe_403(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get(reverse("acolhidos:estatisticas")).status_code == 403

    def test_tecnico_ve_numeros_e_nenhum_nome(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory(nome="Maria Aparecida Teste")
        DadosSaudeFactory(acolhido=acolhido, alergias="Dipirona")
        FichaAcolhimentoFactory(acolhido=acolhido)
        client.force_login(usuario_tecnico)
        resposta = client.get(reverse("acolhidos:estatisticas"))
        assert resposta.status_code == 200
        html = resposta.content.decode()
        assert "Dipirona" in html
        assert "Maria Aparecida" not in html

    def test_filtra_por_situacao(self, client, usuario_tecnico):
        AcolhidoFactory()
        AcolhidoFactory(status=StatusAcolhido.DESLIGADO)
        client.force_login(usuario_tecnico)
        url = reverse("acolhidos:estatisticas")
        assert client.get(url).context["estatisticas"]["total"] == 1
        assert client.get(url, {"situacao": "TODOS"}).context["estatisticas"]["total"] == 2

    def test_lista_tem_botao_so_para_equipe_tecnica(
        self, client, usuario_tecnico, usuario_operacional
    ):
        url = reverse("acolhidos:estatisticas")
        client.force_login(usuario_tecnico)
        assert url in client.get(reverse("acolhidos:lista")).content.decode()
        client.force_login(usuario_operacional)
        assert url not in client.get(reverse("acolhidos:lista")).content.decode()
