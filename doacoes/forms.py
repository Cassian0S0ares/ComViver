from django import forms
from django.core.exceptions import PermissionDenied
from django.db import models

from accounts.forms import FormularioAcessivelMixin
from accounts.models import Perfil
from doacoes.models import Campanha, Doacao, Doador, TipoDoacao


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.update({"class": "form-check-input"})
        elif isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


class FormularioDoacoesMixin(FormularioAcessivelMixin):
    perfis_permitidos = (Perfil.ADMIN, Perfil.OPERACIONAL)

    def __init__(self, *args, usuario=None, **kwargs):
        if usuario is None or not usuario.is_active or usuario.perfil not in self.perfis_permitidos:
            raise PermissionDenied("Seu perfil não pode alterar este cadastro.")
        self.usuario = usuario
        super().__init__(*args, **kwargs)


class DoacaoForm(FormularioDoacoesMixin, forms.ModelForm):
    class Meta:
        model = Doacao
        fields = [
            "doador",
            "campanha",
            "tipo",
            "descricao",
            "quantidade",
            "unidade",
            "valor",
            "data_recebimento",
            "observacoes",
        ]
        widgets = {
            "data_recebimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, usuario=usuario, **kwargs)
        self.usuario = usuario
        self.fields["doador"].required = False
        self.fields["doador"].empty_label = "Anônimo"
        self.fields["campanha"].required = False
        # So campanha aberta aceita doacao nova. A campanha ja encerrada de uma
        # doacao antiga continua na lista, senao editar o valor dela apagaria o
        # vinculo com a arrecadacao daquele periodo.
        campanhas = Campanha.objects.ativas()
        if self.instance.pk and self.instance.campanha_id:
            campanhas = Campanha.objects.filter(
                models.Q(pk__in=campanhas.values("pk")) | models.Q(pk=self.instance.campanha_id)
            )
        self.fields["campanha"].queryset = campanhas
        self.fields["campanha"].empty_label = "Nenhuma"
        _aplicar_classes(self.fields)
        self.fields["quantidade"].required = False
        self.fields["unidade"].required = False
        self.fields["valor"].localize = True
        self.fields["valor"].widget = forms.TextInput(
            attrs={"class": "form-control", "inputmode": "decimal", "placeholder": "0,00"}
        )

    def clean(self):
        dados = super().clean()
        # Doacao em dinheiro nao tem quantidade nem unidade: a tela esconde os
        # dois campos, e aqui o valor enviado por engano — ou por POST forjado —
        # e descartado, para nao gravar "20 pacotes de dinheiro".
        if dados.get("tipo") == TipoDoacao.DINHEIRO:
            dados["quantidade"] = None
            dados["unidade"] = ""
            self.instance.quantidade = None
            self.instance.unidade = ""
        return dados


class DoadorForm(FormularioDoacoesMixin, forms.ModelForm):
    cpf_cnpj = forms.CharField(label="CPF ou CNPJ", max_length=18, required=False)

    class Meta:
        model = Doador
        fields = [
            "tipo",
            "nome",
            "cpf_cnpj",
            "telefone",
            "email",
            "recorrente",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "observacoes",
        ]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, usuario=usuario, **kwargs)
        self.usuario = usuario
        _aplicar_classes(self.fields)
        self.fields["cep"].widget.attrs.update({"inputmode": "numeric", "maxlength": 9, "autocomplete": "postal-code"})

    def clean_cpf_cnpj(self):
        numero = "".join(filter(str.isdigit, self.cleaned_data.get("cpf_cnpj", "")))
        tipo = self.cleaned_data.get("tipo")
        if numero and tipo == "PF" and len(numero) != 11:
            raise forms.ValidationError("CPF precisa ter 11 dígitos.")
        if numero and tipo == "PJ" and len(numero) != 14:
            raise forms.ValidationError("CNPJ precisa ter 14 dígitos.")
        return numero


class CampanhaForm(FormularioDoacoesMixin, forms.ModelForm):
    perfis_permitidos = (Perfil.ADMIN,)

    class Meta:
        model = Campanha
        fields = ["nome", "descricao", "data_inicio", "data_fim", "meta_valor"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_fim": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, usuario=usuario, **kwargs)
        self.usuario = usuario
        _aplicar_classes(self.fields)

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "O término não pode ser anterior ao início.")
        return dados
