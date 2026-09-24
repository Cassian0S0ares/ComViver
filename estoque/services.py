from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Min, Q, Sum
from django.utils import timezone

from estoque.models import ItemEstoque, LoteEstoque, MovimentacaoEstoque, TipoMovimentacao

DIAS_ALERTA_VALIDADE = 7


def item_por_nome(categoria, nome: str) -> ItemEstoque:
    """Reaproveita o item de mesmo nome na categoria, sem diferenciar maiusculas."""
    nome = " ".join(nome.split())
    item = ItemEstoque.objects.filter(categoria=categoria, nome__iexact=nome).first()
    return item or ItemEstoque.objects.create(categoria=categoria, nome=nome)


def itens_disponiveis(busca: str = "", categoria=None, ordenar_validade: str = ""):
    """Itens com saldo, com a quantidade total e a validade mais proxima.

    `ordenar_validade` em "asc" poe quem vence primeiro no topo; "desc" poe
    quem vence por ultimo. Quem nao tem validade fica sempre por ultimo.
    """
    com_saldo = Q(lotes__saldo__gt=0)
    qs = (
        ItemEstoque.objects.select_related("categoria")
        .annotate(
            disponivel=Sum("lotes__saldo", filter=com_saldo),
            proxima_validade=Min("lotes__validade", filter=com_saldo),
        )
        .filter(disponivel__gt=0)
    )
    if busca:
        qs = qs.filter(nome__icontains=busca.strip())
    if categoria:
        qs = qs.filter(categoria=categoria)
    if ordenar_validade == "asc":
        return qs.order_by(F("proxima_validade").asc(nulls_last=True), "categoria__nome", "nome")
    if ordenar_validade == "desc":
        return qs.order_by(F("proxima_validade").desc(nulls_last=True), "categoria__nome", "nome")
    return qs.order_by("categoria__nome", "nome")


def registrar_entrada(item, quantidade: int, usuario, validade=None, doacao=None,
                      observacao="") -> LoteEstoque:
    lote = LoteEstoque(item=item, quantidade_inicial=quantidade, saldo=quantidade,
                       validade=validade, doacao=doacao, criado_por=usuario)
    lote.full_clean()
    lote.save()
    MovimentacaoEstoque.objects.create(
        item=item, lote=lote, tipo=TipoMovimentacao.ENTRADA, quantidade=quantidade,
        usuario=usuario, observacao=observacao or ("Doação recebida" if doacao else ""),
    )
    return lote


@transaction.atomic
def dar_baixa(item, quantidade: int, usuario, observacao: str = "") -> list:
    """Tira do estoque pelos lotes que vencem primeiro (e, sem validade, os mais antigos)."""
    if quantidade < 1:
        raise ValidationError("Informe uma quantidade maior que zero.")
    lotes = list(LoteEstoque.objects.select_for_update().filter(item=item, saldo__gt=0))
    disponivel = sum(lote.saldo for lote in lotes)
    if quantidade > disponivel:
        raise ValidationError(
            f"Só há {disponivel} unidade{'s' if disponivel != 1 else ''} de {item.nome} no estoque."
        )
    restante, usados = quantidade, []
    for lote in lotes:
        if not restante:
            break
        tirar = min(lote.saldo, restante)
        lote.saldo -= tirar
        lote.save(update_fields=["saldo", "atualizado_em"])
        MovimentacaoEstoque.objects.create(
            item=item, lote=lote, tipo=TipoMovimentacao.SAIDA, quantidade=tirar,
            usuario=usuario, observacao=observacao,
        )
        restante -= tirar
        usados.append(lote)
    return usados


def conferir_edicao_da_doacao(doacao, item, quantidade) -> None:
    """O que ja saiu do estoque nao volta: a doacao editada precisa cobrir isso."""
    lote = LoteEstoque.objects.filter(doacao=doacao).first() if doacao.pk else None
    if not lote or not lote.consumido:
        return
    saiu = f"Já saíram {lote.consumido} unidade{'s' if lote.consumido != 1 else ''} desta doação do estoque"
    if item is None or item.pk != lote.item_id:
        raise ValidationError(f"{saiu}; não dá para trocar o item.")
    if quantidade is None or quantidade < lote.consumido:
        raise ValidationError(f"{saiu}; a quantidade não pode ser menor que isso.")


@transaction.atomic
def sincronizar_doacao(doacao, item, validade, usuario) -> LoteEstoque | None:
    """Mantem o lote da doacao igual ao que foi registrado nela.

    Chame depois de `conferir_edicao_da_doacao`, que ja recusou o que nao cabe.
    """
    lote = LoteEstoque.objects.select_for_update().filter(doacao=doacao).first()
    if item is None:
        if lote:
            MovimentacaoEstoque.objects.create(
                item=lote.item, lote=lote, tipo=TipoMovimentacao.AJUSTE,
                quantidade=-lote.saldo, usuario=usuario, observacao="Doação deixou de ser item",
            )
            lote.saldo = lote.quantidade_inicial = 0
            lote.doacao = None
            lote.save()
        return None
    quantidade = int(doacao.quantidade)
    if lote is None:
        return registrar_entrada(item, quantidade, usuario, validade=validade, doacao=doacao)
    diferenca = quantidade - lote.quantidade_inicial
    if item.pk != lote.item_id or diferenca or validade != lote.validade:
        lote.item, lote.validade = item, validade
        lote.saldo = quantidade - lote.consumido
        lote.quantidade_inicial = quantidade
        lote.save()
        MovimentacaoEstoque.objects.create(
            item=item, lote=lote, tipo=TipoMovimentacao.AJUSTE, quantidade=diferenca,
            usuario=usuario, observacao="Doação editada",
        )
    return lote


def perto_da_validade(dias: int = DIAS_ALERTA_VALIDADE):
    """Lotes com saldo que vencem em ate `dias` dias, inclusive os ja vencidos."""
    limite = timezone.localdate() + timedelta(days=dias)
    return (
        LoteEstoque.objects.filter(saldo__gt=0, validade__isnull=False, validade__lte=limite,
                                   item__deleted_at__isnull=True)
        .select_related("item__categoria").order_by("validade", "item__nome")
    )
