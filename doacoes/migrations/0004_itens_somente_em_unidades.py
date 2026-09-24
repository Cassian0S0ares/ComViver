"""Itens passam a ser contados so em unidades; servico continua em horas.

Os dados existentes ainda sao de teste: quilos, caixas etc. viram unidades
mantendo o numero. Metas que colidirem depois da troca ficam so com a primeira.
"""

from django.db import migrations


def converter(apps, schema_editor):
    Doacao = apps.get_model("doacoes", "Doacao")
    Meta = apps.get_model("doacoes", "MetaItemCampanha")
    Doacao.objects.exclude(tipo__in=["DINHEIRO", "SERVICO"]).exclude(unidade="unidades").update(
        unidade="unidades"
    )
    Doacao.objects.filter(tipo="SERVICO").exclude(unidade__in=["unidades", "horas"]).update(
        unidade="unidades"
    )
    vistas = set()
    for meta in Meta.objects.order_by("pk"):
        unidade = meta.unidade if meta.tipo == "SERVICO" and meta.unidade == "horas" else "unidades"
        chave = (meta.campanha_id, meta.tipo, unidade)
        if chave in vistas:
            meta.delete()
            continue
        vistas.add(chave)
        if meta.unidade != unidade:
            meta.unidade = unidade
            meta.save(update_fields=["unidade"])


class Migration(migrations.Migration):
    dependencies = [("doacoes", "0003_metaitemcampanha")]

    operations = [migrations.RunPython(converter, migrations.RunPython.noop)]
