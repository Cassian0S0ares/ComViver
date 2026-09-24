from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.forms import BaseInlineFormSet, inlineformset_factory

from accounts.forms import FormularioAcessivelMixin
from accounts.models import Perfil
from doacoes.models import (
    TIPOS_DE_ITEM,
    UNIDADES_DOACAO,
    UNIDADES_POR_TIPO,
    Campanha,
    Doacao,
    Doador,
    MetaItemCampanha,
    TipoDoacao,
)


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.update({"class": "form-check-input"})
        elif isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


class UnidadePorTipoSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcao = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            opcao["attrs"]["data-tipos"] = " ".join(
                tipo for tipo, unidades in UNIDADES_POR_TIPO.items() if str(value) in unidades
            )
        return opcao


class FormularioDoacoesMixin(FormularioAcessivelMixin):
    perfis_permitidos = (Perfil.ADMIN, Perfil.OPERACIONAL)

    def __init__(self, *args, usuario=None, **kwargs):
        if usuario is None or not usuario.is_active or usuario.perfil not in self.perfis_permitidos:
            raise PermissionDenied("Seu perfil não pode alterar este cadastro.")
        self.usuario = usuario
        super().__init__(*args, **kwargs)


class DoacaoForm(FormularioDoacoesMixin, forms.ModelForm):
    quantidade = forms.IntegerField(
        label="Quantidade",
        min_value=1,
        max_value=99_999_999,
        required=False,
        widget=forms.NumberInput(attrs={"min": 1, "step": 1, "inputmode": "numeric"}),
    )
    unidade = forms.ChoiceField(
        label="Unidade",
        choices=[("", "Selecione a unidade"), *UNIDADES_DOACAO],
        widget=UnidadePorTipoSelect,
        required=False,
    )

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
        from estoque.forms import campos_de_item

        super().__init__(*args, usuario=usuario, **kwargs)
        self.usuario = usuario
        # Item doado vai direto para o estoque: categoria, item e validade.
        campos = campos_de_item(obrigatorios=False)
        self.fields["categoria_estoque"] = campos["categoria"]
        self.fields["categoria_estoque"].label = "Categoria no estoque"
        self.fields["item_nome"] = campos["item_nome"]
        self.fields["validade"] = campos["validade"]
        lote = getattr(self.instance, "lote_estoque", None) if self.instance.pk else None
        if lote:
            self.initial.setdefault("categoria_estoque", lote.item.categoria_id)
            self.initial.setdefault("item_nome", lote.item.nome)
            self.initial.setdefault("validade", lote.validade)
        self.order_fields([
            "doador", "campanha", "tipo", "categoria_estoque", "item_nome", "descricao",
            "quantidade", "unidade", "validade", "valor", "data_recebimento", "observacoes",
        ])
        self.fields["descricao"].help_text = (
            "Para itens, é opcional: sem descrição, usa o nome do item."
        )
        self.fields["quantidade"].label = "Quantidade (unidades)"
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
        unidade_atual = self.instance.unidade if self.instance.pk else ""
        if unidade_atual and unidade_atual not in dict(UNIDADES_DOACAO):
            self.fields["unidade"].choices = [
                *self.fields["unidade"].choices,
                (unidade_atual, unidade_atual),
            ]
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
        tipo = dados.get("tipo")
        if tipo == TipoDoacao.DINHEIRO:
            dados["quantidade"] = None
            dados["unidade"] = ""
            self.instance.quantidade = None
            self.instance.unidade = ""
        else:
            dados["valor"] = None
            self.instance.valor = None
        self._limpar_estoque(dados, tipo)
        return dados

    def _limpar_estoque(self, dados, tipo):
        from estoque.forms import item_existente, limpar_item
        from estoque.services import conferir_edicao_da_doacao

        self.item_estoque = None
        if tipo not in TIPOS_DE_ITEM:
            dados.update(categoria_estoque=None, item_nome="", validade=None)
        else:
            # Item e sempre contado em unidades, para o estoque conseguir somar.
            dados["unidade"] = self.instance.unidade = "unidades"
            categoria, nome = limpar_item(self, dados, "categoria_estoque")
            if not categoria:
                self.add_error("categoria_estoque", "Selecione a categoria do item no estoque.")
            if not nome:
                self.add_error("item_nome", "Informe o item doado.")
            if nome and not (dados.get("descricao") or "").strip():
                dados["descricao"] = self.instance.descricao = nome
            self.item_estoque = (categoria, nome) if categoria and nome else None
        existente = item_existente(*self.item_estoque) if self.item_estoque else None
        try:
            conferir_edicao_da_doacao(
                self.instance, existente if self.item_estoque else None, dados.get("quantidade")
            )
        except ValidationError as erro:
            self.add_error("quantidade" if self.item_estoque else "tipo", erro.messages)

    def sincronizar_estoque(self, doacao, usuario):
        """Depois de salvar: cria ou ajusta o lote do estoque ligado a esta doacao."""
        from estoque.services import item_por_nome, sincronizar_doacao

        item = item_por_nome(*self.item_estoque) if self.item_estoque else None
        return sincronizar_doacao(doacao, item, self.cleaned_data.get("validade"), usuario)


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
        self.fields["cep"].widget.attrs.update(
            {"inputmode": "numeric", "maxlength": 9, "autocomplete": "postal-code"}
        )

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


class MetaItemCampanhaForm(forms.ModelForm):
    quantidade = forms.IntegerField(
        label="Quantidade",
        min_value=1,
        widget=forms.NumberInput(attrs={"min": 1, "step": 1, "inputmode": "numeric"}),
    )

    class Meta:
        model = MetaItemCampanha
        fields = ["tipo", "quantidade", "unidade"]
        widgets = {"unidade": UnidadePorTipoSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self.fields)


class BaseMetasItemFormSet(BaseInlineFormSet):
    def clean(self):
        if any(self.errors):
            return
        combinacoes = set()
        for form in self.forms:
            dados = form.cleaned_data
            if not dados or dados.get("DELETE"):
                continue
            chave = (dados["tipo"], dados["unidade"])
            if chave in combinacoes:
                raise ValidationError("Cada tipo e unidade pode ter apenas uma meta na campanha.")
            combinacoes.add(chave)
        super().clean()


MetasItemFormSet = inlineformset_factory(
    Campanha,
    MetaItemCampanha,
    form=MetaItemCampanhaForm,
    formset=BaseMetasItemFormSet,
    extra=2,
    can_delete=True,
)
