"""Frequencia em texto livre vira lista de horarios; dosagem vai para observacoes.

Os dados ainda sao de teste. A frequencia e lida no melhor esforco: "8h e 20h"
vira 08:00 e 20:00; manha, tarde e noite viram 08:00, 14:00 e 20:00; o que nao
der para ler fica 08:00, para ninguem ficar sem horario na lista do plantao.
"""

import re
from datetime import time

import django.contrib.postgres.fields
from django.db import migrations, models

PERIODOS = {"madrugada": 4, "manha": 8, "manhã": 8, "tarde": 14, "noite": 20}


def ler_frequencia(texto):
    texto = (texto or "").lower()
    horas = {int(h) for h in re.findall(r"\b(\d{1,2})\s*(?:h|:\d{2})", texto) if int(h) < 24}
    horas |= {hora for nome, hora in PERIODOS.items() if nome in texto}
    return [time(h) for h in sorted(horas)] or [time(8)]


def converter(apps, schema_editor):
    Medicacao = apps.get_model("acolhidos", "Medicacao")
    for medicacao in Medicacao._base_manager.all():
        partes = [medicacao.dosagem.strip(), " ".join(medicacao.observacoes.split())]
        medicacao.observacoes = " · ".join(p for p in partes if p)[:200]
        medicacao.horarios = ler_frequencia(medicacao.frequencia)
        medicacao.save(update_fields=["observacoes", "horarios"])


class Migration(migrations.Migration):

    dependencies = [
        ('acolhidos', '0006_escolaridade_turno_integral'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicacao',
            name='horarios',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.TimeField(), default=list, size=None, verbose_name='horários'),
        ),
        migrations.RunPython(converter, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='medicacao',
            name='dosagem',
        ),
        migrations.RemoveField(
            model_name='medicacao',
            name='frequencia',
        ),
        migrations.AlterField(
            model_name='medicacao',
            name='observacoes',
            field=models.CharField(blank=True, max_length=200, verbose_name='observações'),
        ),
    ]
