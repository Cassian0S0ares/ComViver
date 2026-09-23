import pytest

from voluntarios.factories import DisponibilidadeFactory, VoluntarioFactory
from voluntarios.models import DiaSemana, Turno

pytestmark = pytest.mark.django_db


class TestDisponibilidade:
    def test_voluntario_disponivel_no_dia_e_turno_declarados(self):
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
        )
        assert voluntario.esta_disponivel(DiaSemana.TERCA, Turno.MANHA) is True

    def test_voluntario_indisponivel_em_outro_turno(self):
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
        )
        assert voluntario.esta_disponivel(DiaSemana.TERCA, Turno.TARDE) is False

    def test_voluntario_indisponivel_em_outro_dia(self):
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
        )
        assert voluntario.esta_disponivel(DiaSemana.QUARTA, Turno.MANHA) is False

    def test_nao_duplica_a_mesma_disponibilidade(self):
        from django.db import IntegrityError

        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
        )
        with pytest.raises(IntegrityError):
            DisponibilidadeFactory(
                voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
            )

    def test_resumo_agrupa_por_dia(self):
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.SEGUNDA, turno=Turno.MANHA
        )
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.SEGUNDA, turno=Turno.TARDE
        )
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.QUARTA, turno=Turno.MANHA
        )
        assert voluntario.resumo_disponibilidade == "Seg: manhã, tarde · Qua: manhã"

    def test_resumo_vazio_sem_disponibilidade(self):
        assert VoluntarioFactory().resumo_disponibilidade == "Não informada"
