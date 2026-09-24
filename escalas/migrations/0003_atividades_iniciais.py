from django.db import migrations


def cadastrar_atividades(apps, schema_editor):
    atividade = apps.get_model("escalas", "Atividade")
    for nome in (
        "Acompanhamento escolar", "Recreação", "Cozinha e alimentação",
        "Limpeza e organização", "Portaria e recepção", "Apoio à rotina",
        "Atendimento técnico", "Reunião de equipe",
    ):
        atividade.objects.using(schema_editor.connection.alias).get_or_create(nome=nome)


class Migration(migrations.Migration):
    dependencies = [("escalas", "0002_alocacao_usuario_alter_alocacao_voluntario_and_more")]

    operations = [migrations.RunPython(cadastrar_atividades, migrations.RunPython.noop)]
