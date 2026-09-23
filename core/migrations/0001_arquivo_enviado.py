from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ArquivoEnviado",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("nome", models.CharField(max_length=255, unique=True)),
                ("conteudo", models.BinaryField(editable=False)),
                ("tamanho", models.PositiveIntegerField()),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "arquivo enviado",
                "verbose_name_plural": "arquivos enviados",
            },
        ),
    ]
