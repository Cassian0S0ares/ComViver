from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("acolhidos", "0005_tipo_sanguineo_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="escolaridade",
            name="turno",
            field=models.CharField(
                "turno",
                max_length=10,
                blank=True,
                choices=[
                    ("MANHA", "Manhã"),
                    ("TARDE", "Tarde"),
                    ("NOITE", "Noite"),
                    ("INTEGRAL", "Integral"),
                ],
            ),
        ),
    ]
