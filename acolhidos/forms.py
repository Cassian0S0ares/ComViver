from django import forms
from django.core.validators import MaxLengthValidator
from django.utils import timezone

from accounts.forms import FormularioAcessivelMixin
from acolhidos.models import (
    Acolhido,
    DadosSaude,
    Destino,
    FichaAcolhimento,
    Responsavel,
    Turno,
    VinculoFamiliar,
)


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
        foto = self.fields["foto"]
        # FileInput no lugar do widget padrao: o padrao imprime o caminho do
        # arquivo e uma caixa "Limpar" que confundem. Sem arquivo novo, o
        # formulario mantem a foto que ja existe.
        foto.widget = forms.FileInput(
            attrs={
                "class": "input-arquivo",
                "accept": "image/jpeg,image/png,image/webp",
            }
        )
        foto.label = "Trocar a foto" if self.instance.pk and self.instance.foto else "Foto"
        foto.help_text = "JPG, PNG ou WEBP, até 10 MB."

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

    class Meta:
        model = DadosSaude
        fields = ["tipo_sanguineo", "alergias", "condicoes", "plano_saude"]

    def clean(self):
        dados = super().clean()
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


class DesligamentoForm(FormularioAcolhidos, forms.Form):
    """Desligamento e acao explicita, nao edicao de campo.

    Muda o status, preenche a ficha e preserva todo o historico.
    """

    data_desligamento = forms.DateField(label="Data do desligamento")
    destino = forms.ChoiceField(label="Destino", choices=[("", "—"), *Destino.choices])
    observacao = forms.CharField(label="Observação", required=False, widget=forms.Textarea)

    def __init__(self, *args, acolhido=None, **kwargs):
        self.acolhido = acolhido
        super().__init__(*args, **kwargs)

    def clean_data_desligamento(self):
        data = self.cleaned_data["data_desligamento"]
        if data > timezone.localdate():
            raise forms.ValidationError("A data de desligamento não pode ser no futuro.")
        ficha = getattr(self.acolhido, "ficha", None)
        if ficha and data < ficha.data_entrada:
            raise forms.ValidationError(
                "A data de desligamento não pode ser anterior à data de entrada "
                f"({ficha.data_entrada:%d/%m/%Y})."
            )
        return data


class VinculoForm(FormularioAcolhidos, forms.ModelForm):
    """Vincula um responsavel ao acolhido.

    Permite escolher alguem ja cadastrado — irmaos acolhidos compartilham
    responsavel, e duplicar o cadastro deixaria telefone desatualizado em um
    dos registros.
    """

    nome_novo = forms.CharField(label="Ou cadastre um novo", max_length=150, required=False)
    telefone_novo = forms.CharField(
        label="Telefone do novo responsável", max_length=20, required=False
    )

    class Meta:
        model = VinculoFamiliar
        fields = [
            "responsavel",
            "nome_novo",
            "telefone_novo",
            "parentesco",
            "e_guardiao",
            "autorizado_visita",
            "autorizado_retirar",
            "observacoes",
        ]
        labels = {"responsavel": "Responsável já cadastrado"}

    def __init__(self, *args, acolhido=None, usuario=None, **kwargs):
        self.acolhido = acolhido
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        self.fields["responsavel"].required = False
        self.fields["responsavel"].queryset = Responsavel.objects.all()
        self.fields["responsavel"].empty_label = "Escolha na lista"

    def validate_unique(self):
        # A unicidade do par e conferida em clean(), com mensagem em portugues
        # e considerando tambem o responsavel novo.
        pass

    def clean(self):
        dados = super().clean()
        responsavel = dados.get("responsavel")
        nome_novo = (dados.get("nome_novo") or "").strip()

        if not responsavel and not nome_novo:
            raise forms.ValidationError(
                "Escolha um responsável já cadastrado ou informe o nome de um novo."
            )

        if responsavel and self.acolhido:
            ja_existe = (
                VinculoFamiliar.objects.filter(acolhido=self.acolhido, responsavel=responsavel)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if ja_existe:
                raise forms.ValidationError(
                    f"{responsavel.nome} já está vinculada a este acolhido."
                )

        return dados

    def save(self, commit=True):
        vinculo = super().save(commit=False)
        if not vinculo.responsavel_id:
            vinculo.responsavel = Responsavel.objects.create(
                nome=self.cleaned_data["nome_novo"].strip(),
                telefone=self.cleaned_data.get("telefone_novo", ""),
                criado_por=self.usuario,
            )
        vinculo.acolhido = self.acolhido
        if commit:
            vinculo.save()
        return vinculo
