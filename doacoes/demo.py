"""Dados fictícios, chamados somente pelo comando explícito seed_demo."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from doacoes.models import Campanha, Doacao, Doador, TipoDoacao

MARCADOR = "Demonstração ComViver: dados fictícios."


def criar_doacoes_demo():
    hoje = timezone.localdate()
    campanha, _ = Campanha.objects.get_or_create(
        nome="Campanha de demonstração — Casa acolhedora",
        defaults={
            "descricao": MARCADOR,
            "data_inicio": hoje - timedelta(days=120),
            "data_fim": hoje + timedelta(days=30),
            "meta_valor": Decimal("5000.00"),
        },
    )
    nomes = [
        "Padaria Exemplo",
        "Mercado Demonstração",
        "Pessoa Exemplo 1",
        "Pessoa Exemplo 2",
        "Parceiro Exemplo",
    ]
    doadores = []
    for indice, nome in enumerate(nomes):
        doador, _ = Doador.objects.get_or_create(
            nome=nome,
            observacoes=MARCADOR,
            defaults={"tipo": "PJ" if indice < 2 else "PF", "recorrente": indice % 2 == 0},
        )
        doadores.append(doador)
    from estoque.models import CategoriaItem

    alimentos, _ = CategoriaItem.objects.get_or_create(
        nome="Alimentos", defaults={"tem_validade": True}
    )
    for indice, tipo in enumerate(TipoDoacao.values):
        Doacao.objects.get_or_create(
            observacoes=MARCADOR,
            tipo=tipo,
            campanha=campanha,
            defaults={
                "categoria": alimentos if tipo == TipoDoacao.ITEM else None,
                "doador": doadores[indice] if indice < 5 else None,
                "descricao": f"Contribuição fictícia de {dict(TipoDoacao.choices)[tipo]}",
                "valor": Decimal("450.00") if tipo == TipoDoacao.DINHEIRO else None,
                "quantidade": None if tipo == TipoDoacao.DINHEIRO else Decimal("10"),
                "unidade": "unidades" if tipo != TipoDoacao.DINHEIRO else "",
                "data_recebimento": hoje - timedelta(days=90 if indice == 4 else indice),
            },
        )
