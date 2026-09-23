from django import forms
from django.core.exceptions import PermissionDenied

from accounts.forms import FormularioAcessivelMixin
from accounts.models import Perfil
from voluntarios.models import DiaSemana, Disponibilidade, Funcao, Turno, Voluntario


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.update({"class": "form-check-input"})
        elif isinstance(campo.widget, (forms.Select, forms.SelectMultiple)):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


class FormularioVoluntariosMixin(FormularioAcessivelMixin):
    perfis_permitidos: tuple = ()

    def __init__(self, *args, usuario=None, **kwargs):
        if usuario is None or not usuario.is_active or usuario.perfil not in self.perfis_permitidos:
            raise PermissionDenied("Seu perfil não pode alterar este cadastro.")
        self.usuario = usuario
        super().__init__(*args, **kwargs)


class VoluntarioForm(FormularioVoluntariosMixin, forms.ModelForm):
    """Cadastro com a grade de disponibilidade embutida.

    A disponibilidade e o dado que faz a escala funcionar: pedi-la numa tela
    separada garante que ninguem preencha.
    """

    perfis_permitidos = (Perfil.ADMIN, Perfil.OPERACIONAL)

    class Meta:
        model = Voluntario
        fields = [
            "nome",
            "cpf",
            "rg",
            "nascimento",
            "telefone",
            "email",
            "funcoes",
            "status",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "observacoes",
        ]
        widgets = {
            "nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "funcoes": forms.CheckboxSelectMultiple,
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, usuario=usuario, **kwargs)
        self.usuario = usuario
        _aplicar_classes(self.fields)
        self.fields["funcoes"].widget.attrs.pop("class", None)
        self.fields["funcoes"].queryset = Funcao.objects.all()

        # Uma caixa por combinacao de dia e turno.
        selecionadas = set()
        if self.instance.pk:
            selecionadas = {
                (d.dia_semana, d.turno) for d in self.instance.disponibilidades.all()
            }
        for dia in DiaSemana:
            for turno in Turno:
                nome = f"disp_{dia.value}_{turno.value}"
                self.fields[nome] = forms.BooleanField(
                    required=False,
                    initial=(dia.value, turno.value) in selecionadas,
                    widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
                )

    def clean_cpf(self):
        # O campo do modelo tem null=True (para a unicidade aceitar varios
        # voluntarios sem CPF); o ModelForm entao usa None, e nao "", como
        # valor vazio do campo.
        cpf = "".join(filter(str.isdigit, self.cleaned_data.get("cpf") or ""))
        if cpf and len(cpf) != 11:
            raise forms.ValidationError("O CPF precisa ter 11 dígitos.")
        return cpf

    def save(self, commit=True):
        voluntario = super().save(commit)
        if commit:
            self._salvar_disponibilidades(voluntario)
        return voluntario

    def _salvar_disponibilidades(self, voluntario):
        voluntario.disponibilidades.all().delete()
        Disponibilidade.objects.bulk_create(
            [
                Disponibilidade(voluntario=voluntario, dia_semana=dia.value, turno=turno.value)
                for dia in DiaSemana
                for turno in Turno
                if self.cleaned_data.get(f"disp_{dia.value}_{turno.value}")
            ]
        )

    @property
    def grade_disponibilidade(self):
        """Devolve a grade pronta para o template: linhas de turno, colunas de dia.

        Cada celula carrega o campo e o rotulo acessivel completo (ex.:
        "Segunda-feira, manhã"), pois a coluna mostra so a abreviacao do dia.
        """
        return [
            {
                "turno": turno.label,
                "celulas": [
                    {
                        "campo": self[f"disp_{dia.value}_{turno.value}"],
                        "rotulo": f"{dia.label}, {turno.label.lower()}",
                    }
                    for dia in DiaSemana
                ],
            }
            for turno in Turno
        ]

    @property
    def cabecalho_dias(self):
        return [dia.label[:3] for dia in DiaSemana]


class FuncaoForm(FormularioVoluntariosMixin, forms.ModelForm):
    perfis_permitidos = (Perfil.ADMIN,)

    class Meta:
        model = Funcao
        fields = ["nome", "descricao"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, usuario=usuario, **kwargs)
        self.usuario = usuario
        _aplicar_classes(self.fields)
