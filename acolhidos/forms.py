from django import forms
from django.core.validators import MaxLengthValidator
from django.utils import timezone

from accounts.forms import FormularioAcessivelMixin
from acolhidos.models import Acolhido, DadosSaude, FichaAcolhimento, Turno


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo, forms.DateField):
            campo.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.update({"class": "form-check-input"})
        elif isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})
        if isinstance(campo.widget, forms.Textarea):
            campo.widget.attrs.setdefault("rows", 3)


def _somente_digitos(valor: str) -> str:
    return "".join(filter(str.isdigit, valor or ""))


class FormularioAcolhidos(FormularioAcessivelMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self.fields)


class EtapaIdentificacaoForm(FormularioAcolhidos, forms.ModelForm):
    class Meta:
        model = Acolhido
        fields = [
            "nome",
            "nome_social",
            "nascimento",
            "sexo",
            "naturalidade",
            "foto",
            "cpf",
            "rg",
            "certidao_nascimento",
            "cartao_sus",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O CPF chega com ou sem mascara; a limpeza guarda so os 11 digitos.
        cpf = self.fields["cpf"]
        cpf.max_length = 14
        cpf.validators = [v for v in cpf.validators if not isinstance(v, MaxLengthValidator)]
        cpf.widget.attrs.update({"maxlength": 14, "inputmode": "numeric"})
        self.fields["foto"].help_text = "JPG, PNG ou WEBP, até 10 MB."

    def clean_nascimento(self):
        nascimento = self.cleaned_data["nascimento"]
        hoje = timezone.localdate()
        if nascimento > hoje:
            raise forms.ValidationError("A data de nascimento não pode ser no futuro.")
        if hoje.year - nascimento.year > 21:
            raise forms.ValidationError(
                "Idade acima de 21 anos. Confira a data — o acolhimento é de "
                "crianças e adolescentes."
            )
        return nascimento

    def clean_cpf(self):
        cpf = _somente_digitos(self.cleaned_data.get("cpf"))
        if cpf and len(cpf) != 11:
            raise forms.ValidationError("O CPF precisa ter 11 dígitos.")
        return cpf


class EtapaAcolhimentoForm(FormularioAcolhidos, forms.ModelForm):
    class Meta:
        model = FichaAcolhimento
        fields = [
            "data_entrada",
            "motivo",
            "orgao_requisitante",
            "processo_numero",
            "vara",
            "medida_protetiva",
        ]

    def clean_data_entrada(self):
        entrada = self.cleaned_data["data_entrada"]
        if entrada > timezone.localdate():
            raise forms.ValidationError("A data de entrada não pode ser no futuro.")
        return entrada


class EtapaSaudeEscolaForm(FormularioAcolhidos, forms.ModelForm):
    escola = forms.CharField(label="Escola", max_length=150, required=False)
    serie = forms.CharField(label="Série", max_length=50, required=False)
    turno = forms.ChoiceField(label="Turno", required=False, choices=[("", "—"), *Turno.choices])
    ano_letivo = forms.IntegerField(label="Ano letivo", required=False, min_value=2000)

    class Meta:
        model = DadosSaude
        fields = ["tipo_sanguineo", "alergias", "condicoes", "plano_saude"]

    def clean(self):
        dados = super().clean()
        if dados.get("escola") and not dados.get("ano_letivo"):
            self.add_error("ano_letivo", "Informe o ano letivo da escola.")
        if dados.get("escola") and not dados.get("serie"):
            self.add_error("serie", "Informe a série da escola.")
        return dados


class EtapaResponsavelForm(FormularioAcolhidos, forms.Form):
    nome = forms.CharField(label="Nome do responsável", max_length=150)
    cpf = forms.CharField(label="CPF", max_length=14, required=False)
    telefone = forms.CharField(label="Telefone", max_length=20, required=False)
    parentesco = forms.CharField(label="Parentesco", max_length=50)
    e_guardiao = forms.BooleanField(label="É guardião legal", required=False)
    autorizado_visita = forms.BooleanField(
        label="Autorizado a visitar", required=False, initial=True
    )
    autorizado_retirar = forms.BooleanField(label="Autorizado a retirar", required=False)

    def clean_cpf(self):
        cpf = _somente_digitos(self.cleaned_data.get("cpf"))
        if cpf and len(cpf) != 11:
            raise forms.ValidationError("O CPF precisa ter 11 dígitos.")
        return cpf
