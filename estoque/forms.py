from django import forms
from django.utils import timezone

from accounts.forms import FormularioAcessivelMixin
from estoque.models import CategoriaItem, ItemEstoque

MAXIMO_POR_ENTRADA = 99_999


class CategoriaSelect(forms.Select):
    """Cada opcao diz se a categoria tem validade, para a tela mostrar o campo."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcao = super().create_option(name, value, label, selected, index, subindex, attrs)
        instancia = getattr(value, "instance", None)
        if instancia is not None:
            opcao["attrs"]["data-categoria"] = str(instancia.pk)
            opcao["attrs"]["data-validade"] = "1" if instancia.tem_validade else "0"
        return opcao


def aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.update({"class": "form-check-input"})
        elif isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


def campos_de_item(obrigatorios=True) -> dict:
    """Categoria, item e validade: os mesmos na entrada manual e na doacao."""
    return {
        "categoria": forms.ModelChoiceField(
            label="Categoria", queryset=CategoriaItem.objects.all(), required=obrigatorios,
            empty_label="Selecione a categoria", widget=CategoriaSelect(
                attrs={"data-categoria-estoque": ""}),
        ),
        "item_nome": forms.CharField(
            label="Item", max_length=120, required=obrigatorios,
            help_text="Digite para buscar nos itens já cadastrados. Se não existir, escolha Criar.",
            widget=forms.TextInput(attrs={"list": "itens-estoque", "autocomplete": "off",
                                          "data-item-estoque": ""}),
        ),
        "validade": forms.DateField(
            label="Validade", required=False,
            help_text="Opcional. Aparece nos alertas do painel quando estiver perto de vencer.",
            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        ),
    }


def limpar_item(form, dados, campo_categoria="categoria"):
    """Normaliza o nome e descarta validade de categoria que nao vence."""
    categoria = dados.get(campo_categoria)
    nome = " ".join((dados.get("item_nome") or "").split())
    dados["item_nome"] = nome
    if categoria and not categoria.tem_validade:
        dados["validade"] = None
    validade = dados.get("validade")
    if validade and validade < timezone.localdate() and not form.initial.get("validade"):
        form.add_error("validade", "Esta validade já passou.")
    return categoria, nome


def item_existente(categoria, nome):
    if not categoria or not nome:
        return None
    return ItemEstoque.objects.filter(categoria=categoria, nome__iexact=nome).first()


class EntradaForm(FormularioAcessivelMixin, forms.Form):
    quantidade = forms.IntegerField(
        label="Quantidade (unidades)", min_value=1, max_value=MAXIMO_POR_ENTRADA,
        widget=forms.NumberInput(attrs={"min": 1, "step": 1, "inputmode": "numeric"}),
    )
    observacao = forms.CharField(label="Observação", max_length=200, required=False,
                                 help_text="Opcional. Ex.: compra do mês, sobra do bazar.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campos = campos_de_item()
        self.fields = {"categoria": campos["categoria"], "item_nome": campos["item_nome"],
                       "quantidade": self.fields["quantidade"], "validade": campos["validade"],
                       "observacao": self.fields["observacao"]}
        aplicar_classes(self.fields)

    def clean(self):
        dados = super().clean()
        limpar_item(self, dados)
        return dados


class BaixaForm(FormularioAcessivelMixin, forms.Form):
    quantidade = forms.IntegerField(
        label="Quantidade a retirar", min_value=1, max_value=MAXIMO_POR_ENTRADA,
        widget=forms.NumberInput(attrs={"min": 1, "step": 1, "inputmode": "numeric"}),
    )
    observacao = forms.CharField(label="Motivo", max_length=200, required=False,
                                 help_text="Opcional. Ex.: almoço, kit de higiene, venceu.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_classes(self.fields)


class CategoriaForm(FormularioAcessivelMixin, forms.ModelForm):
    class Meta:
        model = CategoriaItem
        fields = ["nome", "tem_validade"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_classes(self.fields)

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if CategoriaItem.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe uma categoria com este nome.")
        return nome
