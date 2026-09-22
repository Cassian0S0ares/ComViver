from datetime import date
from decimal import Decimal

import factory

from doacoes.models import Campanha, Doacao, Doador, TipoDoacao, TipoPessoa


class DoadorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Doador

    tipo = TipoPessoa.PF
    nome = factory.Faker("name", locale="pt_BR")
    cpf_cnpj = ""
    telefone = factory.Faker("cellphone_number", locale="pt_BR")
    cidade = "Itajubá"
    uf = "MG"


class CampanhaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Campanha

    nome = factory.Sequence(lambda n: f"Campanha {n}")
    data_inicio = factory.LazyFunction(date.today)
    meta_valor = Decimal("1000.00")


class DoacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Doacao

    doador = factory.SubFactory(DoadorFactory)
    tipo = TipoDoacao.DINHEIRO
    valor = Decimal("100.00")
    descricao = "Doação em dinheiro"
    data_recebimento = factory.LazyFunction(date.today)
