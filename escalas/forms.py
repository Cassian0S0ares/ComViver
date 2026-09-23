from datetime import timedelta

from django import forms

from accounts.forms import FormularioAcessivelMixin
from escalas.models import Atividade, Escala, Turno

DIAS_NA_SEMANA = 7


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


class EscalaForm(FormularioAcessivelMixin, forms.ModelForm):
    """A escala e sempre uma tabela de horario de uma semana inteira.

    O formulario so pede o inicio da semana; o termino e sempre calculado
    como 6 dias depois, e nao um campo digitavel — uma escala de duas
    semanas ou de um unico dia deixaria de ser a grade semanal que a tela
    de montagem foi desenhada para mostrar.
    """

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
        self.fields["data_inicio"].label = "Início da semana"
        self.fields["data_inicio"].help_text = (
            "A escala cobre sempre 7 dias corridos a partir desta data."
        )
        _aplicar_classes(self.fields)

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("data_inicio")
        if inicio:
            self.instance.data_fim = inicio + timedelta(days=DIAS_NA_SEMANA - 1)
        return cleaned


class TurnoForm(FormularioAcessivelMixin, forms.ModelForm):
    class Meta:
        model = Turno
        fields = ["data", "hora_inicio", "hora_fim", "atividade", "vagas", "observacoes"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, escala=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.escala = escala
        self.usuario = usuario
        self.fields["atividade"].queryset = Atividade.objects.filter(ativa=True)
        _aplicar_classes(self.fields)

    def clean_data(self):
        data = self.cleaned_data["data"]
        if self.escala and not (self.escala.data_inicio <= data <= self.escala.data_fim):
            raise forms.ValidationError(
                f"A data precisa estar entre {self.escala.data_inicio:%d/%m/%Y} e "
                f"{self.escala.data_fim:%d/%m/%Y}."
            )
        return data
