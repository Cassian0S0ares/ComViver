from django.db import migrations

CATEGORIAS = [
    ("Alimentos", True),
    ("Higiene pessoal", True),
    ("Limpeza", False),
    ("Vestuário", False),
    ("Material escolar", False),
    ("Utensílios", False),
    ("Outros", False),
]


def cadastrar_categorias(apps, schema_editor):
    CategoriaItem = apps.get_model("estoque", "CategoriaItem")
    for nome, tem_validade in CATEGORIAS:
        if not CategoriaItem.objects.filter(nome__iexact=nome).exists():
            CategoriaItem.objects.create(nome=nome, tem_validade=tem_validade)


class Migration(migrations.Migration):
    dependencies = [("estoque", "0001_initial")]

    operations = [migrations.RunPython(cadastrar_categorias, migrations.RunPython.noop)]
