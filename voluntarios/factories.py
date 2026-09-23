import factory

from voluntarios.models import DiaSemana, Disponibilidade, Funcao, Turno, Voluntario


class FuncaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Funcao

    nome = factory.Sequence(lambda n: f"Função {n}")


class VoluntarioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Voluntario

    nome = factory.Faker("name", locale="pt_BR")
    telefone = factory.Faker("cellphone_number", locale="pt_BR")
    email = factory.Faker("email")
    cidade = "Itajubá"
    uf = "MG"
    cpf = ""


class DisponibilidadeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Disponibilidade

    voluntario = factory.SubFactory(VoluntarioFactory)
    dia_semana = DiaSemana.SEGUNDA
    turno = Turno.MANHA
