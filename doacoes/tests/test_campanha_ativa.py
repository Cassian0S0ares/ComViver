from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from doacoes.factories import CampanhaFactory, DoacaoFactory
from doacoes.models import Campanha, TipoDoacao

pytestmark = pytest.mark.django_db

HOJE = date.today()


def opcoes_de_campanha(client):
    resposta = client.get(reverse("doacoes:nova"))
    return list(resposta.context["form"].fields["campanha"].queryset)


class TestQuerysetAtivas:
    def test_encerrada_fica_de_fora(self):
        CampanhaFactory(nome="Natal 2025", encerrada_em=timezone.now())
        assert list(Campanha.objects.ativas()) == []

    def test_com_termino_no_passado_fica_de_fora(self):
        CampanhaFactory(data_inicio=HOJE - timedelta(days=60), data_fim=HOJE - timedelta(days=1))
        assert list(Campanha.objects.ativas()) == []

    def test_que_ainda_nao_comecou_fica_de_fora(self):
        CampanhaFactory(data_inicio=HOJE + timedelta(days=5))
        assert list(Campanha.objects.ativas()) == []

    def test_termina_hoje_ainda_vale(self):
        campanha = CampanhaFactory(data_inicio=HOJE - timedelta(days=10), data_fim=HOJE)
        assert list(Campanha.objects.ativas()) == [campanha]

    def test_sem_data_de_termino_vale(self):
        campanha = CampanhaFactory(data_inicio=HOJE - timedelta(days=10), data_fim=None)
        assert list(Campanha.objects.ativas()) == [campanha]

    def test_acompanha_a_propriedade_esta_ativa(self):
        ativa = CampanhaFactory(data_inicio=HOJE)
        encerrada = CampanhaFactory(data_fim=HOJE - timedelta(days=1))
        assert ativa.esta_ativa is True
        assert encerrada.esta_ativa is False
        assert list(Campanha.objects.ativas()) == [ativa]


class TestFormularioDeDoacao:
    def test_campanha_inativa_nao_aparece_para_doar(self, client, usuario_operacional):
        """Doar para campanha encerrada lanca dinheiro em arrecadacao que ja
        foi prestada como concluida."""
        CampanhaFactory(nome="Natal 2025", data_fim=HOJE - timedelta(days=30))
        client.force_login(usuario_operacional)
        assert opcoes_de_campanha(client) == []

    def test_campanha_ativa_aparece(self, client, usuario_operacional):
        campanha = CampanhaFactory(nome="Volta às aulas")
        client.force_login(usuario_operacional)
        assert opcoes_de_campanha(client) == [campanha]

    def test_post_em_campanha_inativa_e_recusado(self, client, usuario_operacional):
        encerrada = CampanhaFactory(nome="Natal 2025", data_fim=HOJE - timedelta(days=30))
        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("doacoes:nova"),
            {
                "doador": "",
                "campanha": str(encerrada.pk),
                "tipo": TipoDoacao.DINHEIRO,
                "descricao": "",
                "quantidade": "",
                "unidade": "",
                "valor": "500,00",
                "data_recebimento": HOJE.isoformat(),
                "observacoes": "",
            },
        )
        assert resposta.status_code == 200
        assert encerrada.doacoes.count() == 0

    def test_editar_doacao_antiga_mantem_a_campanha_dela(self, client, usuario_operacional):
        """A doacao de dezembro continua ligada a campanha de dezembro: corrigir
        o valor dela nao pode apagar esse vinculo."""
        encerrada = CampanhaFactory(nome="Natal 2025", data_fim=HOJE - timedelta(days=30))
        doacao = DoacaoFactory(campanha=encerrada, tipo=TipoDoacao.DINHEIRO, valor=100)
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("doacoes:editar", args=[doacao.pk]))
        assert encerrada in resposta.context["form"].fields["campanha"].queryset

        client.post(
            reverse("doacoes:editar", args=[doacao.pk]),
            {
                "doador": "",
                "campanha": str(encerrada.pk),
                "tipo": TipoDoacao.DINHEIRO,
                "descricao": "",
                "quantidade": "",
                "unidade": "",
                "valor": "150,00",
                "data_recebimento": doacao.data_recebimento.isoformat(),
                "observacoes": "",
            },
        )
        doacao.refresh_from_db()
        assert doacao.campanha == encerrada
        assert doacao.valor == 150
