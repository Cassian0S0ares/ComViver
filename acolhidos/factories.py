from datetime import date, time

import factory

from acolhidos.models import (
    Acolhido,
    DadosSaude,
    FichaAcolhimento,
    Medicacao,
    Responsavel,
    Sexo,
    VinculoFamiliar,
)


class AcolhidoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Acolhido

    nome = factory.Faker("name", locale="pt_BR")
    nome_social = ""
    nascimento = factory.Faker("date_of_birth", minimum_age=2, maximum_age=17)
    sexo = Sexo.FEMININO
    naturalidade = factory.Faker("city", locale="pt_BR")
    cpf = ""


class ResponsavelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Responsavel

    nome = factory.Faker("name", locale="pt_BR")
    telefone = factory.Faker("cellphone_number", locale="pt_BR")
    cidade = factory.Faker("city", locale="pt_BR")
    uf = "MG"


class VinculoFamiliarFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VinculoFamiliar

    acolhido = factory.SubFactory(AcolhidoFactory)
    responsavel = factory.SubFactory(ResponsavelFactory)
    parentesco = "Mãe"


class FichaAcolhimentoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FichaAcolhimento

    acolhido = factory.SubFactory(AcolhidoFactory)
    data_entrada = factory.LazyFunction(date.today)
    motivo = "Negligência familiar"
    orgao_requisitante = "Conselho Tutelar"
    processo_numero = factory.Sequence(lambda n: f"000{n}-56.2026.8.13.0301")


class DadosSaudeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DadosSaude

    acolhido = factory.SubFactory(AcolhidoFactory)
    tipo_sanguineo = "O+"


class MedicacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Medicacao

    acolhido = factory.SubFactory(AcolhidoFactory)
    nome = "Dipirona"
    horarios = factory.LazyFunction(lambda: [time(8), time(20)])
    observacoes = "500mg"
    inicio = factory.LazyFunction(date.today)
    fim = None
