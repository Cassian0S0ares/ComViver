from decimal import Decimal

from django.db.models import Count, Exists, OuterRef, Q, QuerySet, Sum

from doacoes.models import Doacao, TipoDoacao, rotulo_do_tipo


def totais_por_tipo(consulta: QuerySet[Doacao] | None = None) -> list[dict]:
    """Agrupa doacoes por tipo, com contagem e soma monetaria.

    Reaproveitado pela listagem, pelo painel e pelos relatorios da Fase 5.
    """
    base = consulta if consulta is not None else Doacao.objects.all()
    linhas = (
        base.values("tipo", "categoria__nome")
        .annotate(quantidade=Count("id"), soma=Sum("valor", filter=Q(tipo=TipoDoacao.DINHEIRO)))
        .order_by("tipo", "categoria__nome")
    )
    return [
        {
            "tipo": linha["tipo"],
            "rotulo": linha["categoria__nome"] or rotulo_do_tipo(linha["tipo"], None),
            "quantidade": linha["quantidade"],
            "soma": linha["soma"] or Decimal("0"),
        }
        for linha in linhas
    ]


def total_arrecadado(consulta: QuerySet[Doacao] | None = None) -> Decimal:
    base = consulta if consulta is not None else Doacao.objects.all()
    total = base.filter(tipo=TipoDoacao.DINHEIRO).aggregate(soma=Sum("valor"))["soma"]
    return total or Decimal("0")


def doadores_recorrentes_inativos(dias: int = 60):
    """Doadores marcados como recorrentes sem doacao no periodo.

    Alimenta o cartao do painel do Admin: e a lista de quem vale a pena
    procurar antes que o vinculo esfrie.
    """
    from datetime import date, timedelta

    from doacoes.models import Doador

    corte = date.today() - timedelta(days=dias)
    recentes = Doacao.objects.filter(doador_id=OuterRef("pk"), data_recebimento__gte=corte)
    return Doador.objects.filter(recorrente=True).filter(~Exists(recentes))
