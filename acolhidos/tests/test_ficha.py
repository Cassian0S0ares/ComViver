from datetime import date, timedelta

import pytest

from acolhidos.factories import (
    AcolhidoFactory,
    DadosSaudeFactory,
    FichaAcolhimentoFactory,
    MedicacaoFactory,
)
from acolhidos.models import Medicacao

pytestmark = pytest.mark.django_db


class TestFichaAcolhimento:
    def test_tempo_acolhimento_conta_da_entrada_ate_hoje(self):
        acolhido = AcolhidoFactory()
        FichaAcolhimentoFactory(acolhido=acolhido, data_entrada=date.today() - timedelta(days=45))
        acolhido.refresh_from_db()
        assert acolhido.tempo_acolhimento == 45

    def test_tempo_acolhimento_para_no_desligamento(self):
        acolhido = AcolhidoFactory()
        FichaAcolhimentoFactory(
            acolhido=acolhido,
            data_entrada=date.today() - timedelta(days=100),
            data_desligamento=date.today() - timedelta(days=30),
        )
        acolhido.refresh_from_db()
        assert acolhido.tempo_acolhimento == 70

    def test_tempo_acolhimento_none_sem_ficha(self):
        assert AcolhidoFactory().tempo_acolhimento is None

    def test_ficha_incompleta_sem_orgao_requisitante(self):
        ficha = FichaAcolhimentoFactory(orgao_requisitante="")
        assert ficha.esta_completa() is False

    def test_ficha_completa_com_os_campos_obrigatorios(self):
        ficha = FichaAcolhimentoFactory(
            motivo="Negligência",
            orgao_requisitante="Vara da Infância",
            processo_numero="0001234-56.2026.8.13.0301",
        )
        assert ficha.esta_completa() is True


class TestDadosSaude:
    def test_um_acolhido_tem_uma_unica_ficha_de_saude(self):
        from django.db import IntegrityError

        acolhido = AcolhidoFactory()
        DadosSaudeFactory(acolhido=acolhido)
        with pytest.raises(IntegrityError):
            DadosSaudeFactory(acolhido=acolhido)


class TestMedicacao:
    def test_em_vigor_inclui_medicacao_sem_data_fim(self):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(acolhido=acolhido, inicio=date.today(), fim=None)
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 1

    def test_em_vigor_exclui_medicacao_encerrada(self):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(
            acolhido=acolhido,
            inicio=date.today() - timedelta(days=30),
            fim=date.today() - timedelta(days=1),
        )
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 0

    def test_em_vigor_exclui_medicacao_que_ainda_nao_comecou(self):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(acolhido=acolhido, inicio=date.today() + timedelta(days=5), fim=None)
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 0

    def test_em_vigor_inclui_medicacao_no_intervalo(self):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(
            acolhido=acolhido,
            inicio=date.today() - timedelta(days=5),
            fim=date.today() + timedelta(days=5),
        )
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 1

    def test_em_vigor_exclui_medicacao_excluida(self):
        """Medicacao apagada por engano ou por ter sido suspensa nao pode
        continuar na lista de quem administra o remedio."""
        acolhido = AcolhidoFactory()
        MedicacaoFactory(acolhido=acolhido).delete()
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 0
        assert Medicacao.objects.filter(acolhido=acolhido).count() == 0
