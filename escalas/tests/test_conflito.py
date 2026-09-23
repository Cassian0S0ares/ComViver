from datetime import date, time, timedelta

import pytest
from django.core.exceptions import ValidationError

from escalas.factories import AlocacaoFactory, EscalaFactory, TurnoFactory
from voluntarios.factories import VoluntarioFactory

pytestmark = pytest.mark.django_db


def _turno(escala, dia, inicio, fim):
    return TurnoFactory(
        escala=escala, data=dia,
        hora_inicio=time(inicio, 0), hora_fim=time(fim, 0),
    )


class TestSobreposicaoDeTurno:
    def test_turnos_no_mesmo_horario_se_sobrepoem(self):
        escala = EscalaFactory()
        hoje = date.today()
        a = _turno(escala, hoje, 8, 12)
        b = _turno(escala, hoje, 8, 12)
        assert a.sobrepoe(b) is True

    def test_turnos_com_intersecao_parcial_se_sobrepoem(self):
        escala = EscalaFactory()
        hoje = date.today()
        a = _turno(escala, hoje, 8, 12)
        b = _turno(escala, hoje, 11, 15)
        assert a.sobrepoe(b) is True

    def test_turnos_encostados_nao_se_sobrepoem(self):
        """Terminar as 12h e comecar as 12h e troca de turno, nao conflito."""
        escala = EscalaFactory()
        hoje = date.today()
        a = _turno(escala, hoje, 8, 12)
        b = _turno(escala, hoje, 12, 16)
        assert a.sobrepoe(b) is False

    def test_turnos_em_dias_diferentes_nao_se_sobrepoem(self):
        escala = EscalaFactory()
        hoje = date.today()
        a = _turno(escala, hoje, 8, 12)
        b = _turno(escala, hoje + timedelta(days=1), 8, 12)
        assert a.sobrepoe(b) is False


class TestConflitoNaAlocacao:
    def test_alocar_em_turnos_sobrepostos_e_recusado(self):
        escala = EscalaFactory()
        hoje = date.today()
        voluntario = VoluntarioFactory(nome="Ana Souza")
        AlocacaoFactory(turno=_turno(escala, hoje, 8, 12), voluntario=voluntario)

        conflitante = AlocacaoFactory.build(
            turno=_turno(escala, hoje, 10, 14), voluntario=voluntario
        )
        with pytest.raises(ValidationError) as erro:
            conflitante.full_clean()
        assert "já está escalada" in str(erro.value)

    def test_mensagem_de_conflito_diz_qual_e_o_outro_turno(self):
        escala = EscalaFactory()
        hoje = date.today()
        voluntario = VoluntarioFactory(nome="Ana Souza")
        AlocacaoFactory(turno=_turno(escala, hoje, 8, 12), voluntario=voluntario)

        conflitante = AlocacaoFactory.build(
            turno=_turno(escala, hoje, 10, 14), voluntario=voluntario
        )
        with pytest.raises(ValidationError) as erro:
            conflitante.full_clean()
        assert "08:00" in str(erro.value)

    def test_alocar_em_turnos_encostados_e_permitido(self):
        escala = EscalaFactory()
        hoje = date.today()
        voluntario = VoluntarioFactory()
        AlocacaoFactory(turno=_turno(escala, hoje, 8, 12), voluntario=voluntario)
        seguinte = AlocacaoFactory.build(
            turno=_turno(escala, hoje, 12, 16), voluntario=voluntario
        )
        seguinte.full_clean()  # nao levanta

    def test_voluntarios_diferentes_no_mesmo_turno_e_permitido(self):
        escala = EscalaFactory()
        turno = _turno(escala, date.today(), 8, 12)
        AlocacaoFactory(turno=turno, voluntario=VoluntarioFactory())
        outra = AlocacaoFactory.build(turno=turno, voluntario=VoluntarioFactory())
        outra.full_clean()  # nao levanta

    def test_editar_a_propria_alocacao_nao_conflita_consigo(self):
        """Sem excluir a si mesma da checagem, salvar uma alocacao existente
        acusaria conflito com ela propria."""
        escala = EscalaFactory()
        alocacao = AlocacaoFactory(turno=_turno(escala, date.today(), 8, 12))
        alocacao.observacao = "Chega 15 minutos mais cedo."
        alocacao.full_clean()  # nao levanta

    def test_mesmo_voluntario_duas_vezes_no_mesmo_turno_e_recusado(self):
        from django.db import IntegrityError

        escala = EscalaFactory()
        turno = _turno(escala, date.today(), 8, 12)
        voluntario = VoluntarioFactory()
        AlocacaoFactory(turno=turno, voluntario=voluntario)
        with pytest.raises(IntegrityError):
            AlocacaoFactory(turno=turno, voluntario=voluntario)

    def test_conflito_atravessa_escalas_diferentes(self):
        """Duas escalas da mesma semana nao podem alocar a mesma pessoa no
        mesmo horario — a pessoa e uma so."""
        hoje = date.today()
        voluntario = VoluntarioFactory()
        AlocacaoFactory(turno=_turno(EscalaFactory(), hoje, 8, 12), voluntario=voluntario)
        outra = AlocacaoFactory.build(
            turno=_turno(EscalaFactory(), hoje, 9, 13), voluntario=voluntario
        )
        with pytest.raises(ValidationError):
            outra.full_clean()
