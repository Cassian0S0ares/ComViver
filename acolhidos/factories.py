import factory

from acolhidos.models import Acolhido, Responsavel, Sexo, VinculoFamiliar


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
