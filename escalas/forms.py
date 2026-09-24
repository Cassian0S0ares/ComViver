from datetime import time, timedelta

from django import forms
from django.db import models
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.forms import FormularioAcessivelMixin
from accounts.models import Usuario
from escalas.models import Atividade, Escala, Turno
from voluntarios.models import StatusVoluntario, Voluntario

DIAS_NA_SEMANA = 7
FIM_DO_DIA = time(23, 59)
MEIAS_HORAS = [time(h, m) for h in range(24) for m in (0, 30)]


class HorarioSelect(forms.Select):
    """Lista fechada de horarios: o valor vem como "HH:MM", texto ou time."""

    def format_value(self, value):
        if isinstance(value, time):
            value = value.strftime("%H:%M")
        elif isinstance(value, str):
            value = value[:5]
        return super().format_value(value)


class ResponsaveisWidget(forms.SelectMultiple):
    """Um select por vaga. O JS acrescenta ou tira selects quando as vagas mudam;
    sem ele, aparece um select por pessoa ja escolhida (no minimo um)."""

    limite = None

    def render(self, name, value, attrs=None, renderer=None):
        attrs = self.build_attrs(self.attrs, attrs)
        base_id = attrs.pop("id", f"id_{name}")
        valores = [v for v in (value or []) if v] or [""]
        unico = forms.Select(choices=self.choices)
        selects = []
        for i, valor in enumerate(valores):
            extra = {"id": base_id} if i == 0 else {
                "id": f"{base_id}_{i}", "aria-label": f"Responsável {i + 1}"
            }
            selects.append(unico.render(name, valor, attrs | extra, renderer))
        return format_html(
            '<div class="responsaveis-lista" data-responsaveis data-limite="{}">{}</div>',
            self.limite or "", mark_safe("".join(selects)),
        )


def _opcoes(horarios):
    return [("", "Selecione")] + [
        (h.strftime("%H:%M"), "23:59 (fim do dia)" if h == FIM_DO_DIA else h.strftime("%H:%M"))
        for h in horarios
    ]


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


class EscalaForm(FormularioAcessivelMixin, forms.ModelForm):
    """A data escolhida identifica uma semana inteira, de domingo a sábado."""

    class Meta:
        model = Escala
        fields = ["titulo", "data_inicio", "data_fim", "observacoes"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_fim": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        del self.fields["data_fim"]
        self.fields["data_inicio"].label = "Semana de"
        self.fields["data_inicio"].help_text = (
            "Escolha um dia. A escala irá do domingo ao sábado dessa semana."
        )
        _aplicar_classes(self.fields)

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("data_inicio")
        if inicio:
            inicio -= timedelta(days=(inicio.weekday() + 1) % DIAS_NA_SEMANA)
            cleaned["data_inicio"] = inicio
            self.instance.data_fim = inicio + timedelta(days=DIAS_NA_SEMANA - 1)
        return cleaned


class TurnoForm(FormularioAcessivelMixin, forms.ModelForm):
    responsavel = forms.MultipleChoiceField(
        label="Responsáveis", required=False, widget=ResponsaveisWidget,
        help_text="Opcional. Aparece um campo por vaga; preencha só as que já têm pessoa.",
    )

    class Meta:
        model = Turno
        fields = ["data", "hora_inicio", "hora_fim", "atividade", "vagas", "observacoes"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": HorarioSelect(choices=_opcoes(MEIAS_HORAS)),
            "hora_fim": HorarioSelect(choices=_opcoes(MEIAS_HORAS[1:] + [FIM_DO_DIA])),
        }

    def __init__(self, *args, escala=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.escala = escala
        self.usuario = usuario
        self.fields["atividade"].queryset = Atividade.objects.filter(ativa=True)
        self.fields["responsavel"].choices = [
            ("", "Definir depois"),
            ("Usuários do sistema", [
                (f"usuario:{p.pk}", str(p)) for p in Usuario.objects.filter(is_active=True)
            ]),
            ("Voluntários", [
                (str(p.pk), p.nome) for p in Voluntario.objects.filter(
                    status=StatusVoluntario.ATIVO
                ).order_by("nome")
            ]),
        ]
        if usuario is not None and not usuario.e_admin:
            self.fields["responsavel"].choices = [
                ("", "Definir depois"), (f"usuario:{usuario.pk}", f"Eu ({usuario})"),
            ]
            self.fields["responsavel"].label = "Responsável"
            self.fields["responsavel"].widget.limite = 1
            self.fields["responsavel"].help_text = (
                "Opcional. Você pode se colocar como responsável; outras pessoas "
                "são adicionadas por um administrador."
            )
        self.order_fields([
            "data", "hora_inicio", "hora_fim", "atividade", "vagas", "responsavel", "observacoes"
        ])
        if self.instance.pk:
            # Na edicao, os responsaveis sao geridos no modal do turno.
            del self.fields["responsavel"]
            self.fields["atividade"].queryset = Atividade.objects.filter(
                models.Q(ativa=True) | models.Q(pk=self.instance.atividade_id)
            )
        _aplicar_classes(self.fields)

    def clean_responsavel(self):
        valores = [v for v in self.cleaned_data["responsavel"] if v]
        if len(set(valores)) != len(valores):
            raise forms.ValidationError("A mesma pessoa foi escolhida mais de uma vez.")
        pessoas = []
        for valor in valores:
            if valor.startswith("usuario:"):
                pessoa = Usuario.objects.filter(pk=valor.split(":")[1], is_active=True).first()
            else:
                pessoa = Voluntario.objects.filter(
                    pk=valor, status=StatusVoluntario.ATIVO
                ).first()
            if pessoa is None:
                raise forms.ValidationError("Selecione um responsável ativo.")
            pessoas.append(pessoa)
        return pessoas

    def clean(self):
        cleaned = super().clean()
        pessoas, vagas = cleaned.get("responsavel") or [], cleaned.get("vagas")
        if vagas is not None and len(pessoas) > vagas:
            self.add_error("responsavel", f"Há {len(pessoas)} responsáveis para {vagas} "
                                          f"vaga{'s' if vagas != 1 else ''}.")
        return cleaned

    def _meia_hora(self, campo, *extras):
        valor = self.cleaned_data[campo]
        if valor and valor not in MEIAS_HORAS and valor not in extras:
            raise forms.ValidationError("Escolha um horário em hora cheia ou meia hora.")
        return valor

    def clean_hora_inicio(self):
        return self._meia_hora("hora_inicio")

    def clean_hora_fim(self):
        return self._meia_hora("hora_fim", FIM_DO_DIA)

    def clean_data(self):
        data = self.cleaned_data["data"]
        if self.escala and not (self.escala.data_inicio <= data <= self.escala.data_fim):
            raise forms.ValidationError(
                f"A data precisa estar entre {self.escala.data_inicio:%d/%m/%Y} e "
                f"{self.escala.data_fim:%d/%m/%Y}."
            )
        return data
