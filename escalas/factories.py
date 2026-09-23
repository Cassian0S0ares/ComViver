from datetime import date, time, timedelta

import factory

from escalas.models import Alocacao, Atividade, Escala, Turno
from voluntarios.factories import VoluntarioFactory


class AtividadeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Atividade

    nome = factory.Sequence(lambda n: f"Atividade {n}")


class EscalaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Escala

    titulo = factory.Sequence(lambda n: f"Escala {n}")
    data_inicio = factory.LazyFunction(date.today)
    data_fim = factory.LazyFunction(lambda: date.today() + timedelta(days=6))


class TurnoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Turno

    escala = factory.SubFactory(EscalaFactory)
    data = factory.LazyFunction(date.today)
    hora_inicio = time(8, 0)
    hora_fim = time(12, 0)
    atividade = factory.SubFactory(AtividadeFactory)
    vagas = 1


class AlocacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Alocacao

    turno = factory.SubFactory(TurnoFactory)
    voluntario = factory.SubFactory(VoluntarioFactory)
