from datetime import date, time, timedelta

import pytest

from escalas.factories import AlocacaoFactory, EscalaFactory, TurnoFactory
from escalas.models import StatusEscala

pytestmark = pytest.mark.django_db


class TestEscala:
    def test_escala_nasce_como_rascunho(self):
        assert EscalaFactory().status == StatusEscala.RASCUNHO

    def test_total_de_turnos(self):
        escala = EscalaFactory()
        TurnoFactory.create_batch(3, escala=escala)
        assert escala.total_turnos == 3

    def test_conta_turnos_descobertos(self):
        escala = EscalaFactory()
        coberto = TurnoFactory(escala=escala, vagas=1)
        AlocacaoFactory(turno=coberto)
        TurnoFactory(escala=escala, vagas=2)  # descoberto
        assert escala.turnos_descobertos == 1

    def test_periodo_invalido_e_recusado(self):
        from django.core.exceptions import ValidationError

        escala = EscalaFactory.build(
            data_inicio=date.today(), data_fim=date.today() - timedelta(days=1)
        )
        with pytest.raises(ValidationError):
            escala.full_clean()


class TestTurno:
    def test_vagas_ocupadas_conta_alocacoes(self):
        turno = TurnoFactory(vagas=3)
        AlocacaoFactory.create_batch(2, turno=turno)
        assert turno.vagas_ocupadas == 2

    def test_turno_sem_ninguem_esta_descoberto(self):
        assert TurnoFactory(vagas=2).esta_descoberto is True

    def test_turno_parcialmente_preenchido_ainda_esta_descoberto(self):
        """Duas vagas com uma pessoa e um buraco, e o coordenador precisa ver."""
        turno = TurnoFactory(vagas=2)
        AlocacaoFactory(turno=turno)
        assert turno.esta_descoberto is True

    def test_turno_completo_nao_esta_descoberto(self):
        turno = TurnoFactory(vagas=2)
        AlocacaoFactory.create_batch(2, turno=turno)
        assert turno.esta_descoberto is False

    def test_turno_do_dia_pela_hora_de_inicio(self):
        assert TurnoFactory(hora_inicio=time(8, 0)).turno_do_dia == "MANHA"
        assert TurnoFactory(hora_inicio=time(14, 0)).turno_do_dia == "TARDE"
        assert TurnoFactory(hora_inicio=time(19, 0)).turno_do_dia == "NOITE"

    def test_hora_fim_antes_do_inicio_e_recusada(self):
        from django.core.exceptions import ValidationError

        turno = TurnoFactory.build(hora_inicio=time(14, 0), hora_fim=time(10, 0))
        with pytest.raises(ValidationError):
            turno.full_clean()
