# ComViver — Fase 4: Voluntários e Escalas — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o cadastro de voluntários com disponibilidade declarada e a montagem de escalas em grade semanal, com bloqueio de conflito de horário, destaque para turnos descobertos e registro de presença.

**Architecture:** Dois apps — `voluntarios` (cadastro, o padrão já conhecido) e `escalas` (a grade semanal, a tela mais complexa do sistema). A regra de sobreposição de turno vive no `clean()` do model, valendo igualmente na tela, no admin e em qualquer importação futura.

**Tech Stack:** Django 5.x, Bootstrap 5 (local), HTMX para a alocação sem recarregar a página.

**Spec:** `docs/superpowers/specs/2026-09-22-comviver-design.md`

**Depende de:** Fases 1, 2 e 3 concluídas.

## Global Constraints

- Python 3.12; Django 5.x (`Django>=5.1,<6.0`).
- PostgreSQL exclusivamente, inclusive em teste.
- `.env` nunca versionado.
- Interface, mensagens e validações em português do Brasil.
- Exclusão sempre lógica (`deleted_at`).
- Controle de acesso em três camadas: view, formulário e template.
- Regra de negócio no `clean()` do model, não na view.
- `ruff` limpo antes de cada commit.
- Teste escrito antes da implementação, falhando primeiro pelo motivo certo.

## Recorte de acesso desta fase

| Ação | Admin | Técnico | Operacional |
|---|---|---|---|
| Ver voluntários e escalas | escreve | lê | escreve |
| Cadastrar e editar voluntário | sim | não | sim |
| Montar e publicar escala | sim | não | sim |
| Confirmar presença | sim | não | sim |
| Cadastrar funções e atividades | sim | não | não |

Funções e atividades são tabelas de apoio: mudam pouco e, se qualquer pessoa
puder criá-las, a lista vira um amontoado de duplicatas com grafias diferentes.

## O que as fases anteriores deixaram pronto

- `core.views.BaseListView`, `BaseCreateView`, `BaseUpdateView`
- `core.mixins.PerfilRequiredMixin`
- `core.models.SoftDeleteModel`, `Endereco`
- `core.pdf.renderizar_pdf`
- `core.context_processors.menu` e `core.views.PainelView._montar_cartoes`
- HTMX carregado em `templates/base.html`

---

## Estrutura de arquivos ao fim da Fase 4

```
voluntarios/
├── models.py          # Voluntario, Funcao, Disponibilidade, DocumentoVoluntario
├── forms.py
├── views.py
├── urls.py
├── admin.py
├── factories.py
├── migrations/
└── tests/
    ├── test_models.py
    ├── test_permissoes.py
    └── test_disponibilidade.py

escalas/
├── models.py          # Atividade, Escala, Turno, Alocacao
├── forms.py
├── views.py           # grade semanal, alocacao HTMX, presenca
├── urls.py
├── admin.py
├── factories.py
├── services.py        # voluntarios_disponiveis, turnos_descobertos
├── migrations/
└── tests/
    ├── test_models.py
    ├── test_conflito.py      # a regra central desta fase
    ├── test_grade.py
    └── test_presenca.py

templates/voluntarios/
├── voluntario_list.html
├── voluntario_detail.html
├── voluntario_form.html
└── funcao_list.html

templates/escalas/
├── escala_list.html
├── escala_form.html
├── escala_grade.html                    # a tela principal
├── presenca.html
└── partials/
    ├── _celula_turno.html               # fragmento HTMX
    └── _lista_disponiveis.html          # fragmento HTMX
```

---

## Task 1: Cadastro de voluntários

**Files:**
- Create: `voluntarios/` (app completo)
- Create: `voluntarios/tests/test_models.py`, `test_disponibilidade.py`, `test_permissoes.py`
- Create: `templates/voluntarios/*.html`
- Modify: `comviver/settings/base.py`, `comviver/urls.py`, `core/context_processors.py`

**Interfaces:**
- Consumes: `core.models.SoftDeleteModel`, `Endereco`; `core.views.Base*View`
- Produces:
  - `voluntarios.models.Funcao`
  - `voluntarios.models.StatusVoluntario` — `ATIVO`, `INATIVO`
  - `voluntarios.models.DiaSemana` — `IntegerChoices` de 0 (segunda) a 6 (domingo)
  - `voluntarios.models.Turno` — `MANHA`, `TARDE`, `NOITE`
  - `voluntarios.models.Voluntario` — propriedades `idade: int`, `resumo_disponibilidade: str`; método `esta_disponivel(dia_semana: int, turno: str) -> bool`
  - `voluntarios.models.Disponibilidade` — `unique(voluntario, dia_semana, turno)`
  - `voluntarios.factories.VoluntarioFactory`, `FuncaoFactory`, `DisponibilidadeFactory`

- [ ] **Step 1: Escrever os testes que falham**

`voluntarios/tests/test_models.py`:
```python
from datetime import date, timedelta

import pytest

from voluntarios.factories import FuncaoFactory, VoluntarioFactory
from voluntarios.models import StatusVoluntario, Voluntario

pytestmark = pytest.mark.django_db


class TestVoluntario:
    def test_idade_calculada_do_nascimento(self):
        voluntario = VoluntarioFactory(
            nascimento=date.today() - timedelta(days=365 * 40 + 10)
        )
        assert voluntario.idade == 40

    def test_status_inicial_e_ativo(self):
        assert VoluntarioFactory().status == StatusVoluntario.ATIVO

    def test_str_mostra_o_nome(self):
        assert str(VoluntarioFactory(nome="Ana Souza")) == "Ana Souza"

    def test_voluntario_pode_ter_varias_funcoes(self):
        voluntario = VoluntarioFactory()
        voluntario.funcoes.set([FuncaoFactory(nome="Cozinha"), FuncaoFactory(nome="Reforço escolar")])
        assert voluntario.funcoes.count() == 2

    def test_exclusao_e_logica(self):
        voluntario = VoluntarioFactory()
        pk = voluntario.pk
        voluntario.delete()
        assert not Voluntario.objects.filter(pk=pk).exists()
        assert Voluntario.todos.filter(pk=pk).exists()

    def test_cpf_e_unico(self):
        from django.db import IntegrityError

        VoluntarioFactory(cpf="12345678901")
        with pytest.raises(IntegrityError):
            VoluntarioFactory(cpf="12345678901")


class TestFuncao:
    def test_nome_da_funcao_e_unico(self):
        from django.db import IntegrityError

        FuncaoFactory(nome="Cozinha")
        with pytest.raises(IntegrityError):
            FuncaoFactory(nome="Cozinha")
```

`voluntarios/tests/test_disponibilidade.py`:
```python
import pytest

from voluntarios.factories import DisponibilidadeFactory, VoluntarioFactory
from voluntarios.models import DiaSemana, Turno

pytestmark = pytest.mark.django_db


class TestDisponibilidade:
    def test_voluntario_disponivel_no_dia_e_turno_declarados(self):
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
        )
        assert voluntario.esta_disponivel(DiaSemana.TERCA, Turno.MANHA) is True

    def test_voluntario_indisponivel_em_outro_turno(self):
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
        )
        assert voluntario.esta_disponivel(DiaSemana.TERCA, Turno.TARDE) is False

    def test_voluntario_indisponivel_em_outro_dia(self):
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
        )
        assert voluntario.esta_disponivel(DiaSemana.QUARTA, Turno.MANHA) is False

    def test_nao_duplica_a_mesma_disponibilidade(self):
        from django.db import IntegrityError

        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
        )
        with pytest.raises(IntegrityError):
            DisponibilidadeFactory(
                voluntario=voluntario, dia_semana=DiaSemana.TERCA, turno=Turno.MANHA
            )

    def test_resumo_agrupa_por_dia(self):
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.SEGUNDA, turno=Turno.MANHA
        )
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.SEGUNDA, turno=Turno.TARDE
        )
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=DiaSemana.QUARTA, turno=Turno.MANHA
        )
        assert voluntario.resumo_disponibilidade == "Seg: manhã, tarde · Qua: manhã"

    def test_resumo_vazio_sem_disponibilidade(self):
        assert VoluntarioFactory().resumo_disponibilidade == "Não informada"
```

`voluntarios/tests/test_permissoes.py`:
```python
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestPermissoes:
    @pytest.mark.parametrize(
        "fixture_usuario", ["usuario_admin", "usuario_tecnico", "usuario_operacional"]
    )
    def test_todos_veem_a_lista(self, client, request, fixture_usuario):
        client.force_login(request.getfixturevalue(fixture_usuario))
        assert client.get(reverse("voluntarios:lista")).status_code == 200

    def test_tecnico_nao_cadastra_voluntario(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        assert client.get(reverse("voluntarios:novo")).status_code == 403

    def test_operacional_cadastra_voluntario(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get(reverse("voluntarios:novo")).status_code == 200

    def test_so_admin_cadastra_funcao(self, client, usuario_operacional):
        """Tabela de apoio: aberta a todos, vira lista de duplicatas com
        grafias diferentes."""
        client.force_login(usuario_operacional)
        assert client.get(reverse("voluntarios:funcao_nova")).status_code == 403

    def test_admin_cadastra_funcao(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("voluntarios:funcao_nova")).status_code == 200
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest voluntarios/tests/ -v
```
Esperado: `ModuleNotFoundError: No module named 'voluntarios'`.

- [ ] **Step 3: Criar o app e escrever os models**

```bash
python manage.py startapp voluntarios
mkdir voluntarios/tests && touch voluntarios/tests/__init__.py
rm voluntarios/tests.py
```

`voluntarios/apps.py`:
```python
from django.apps import AppConfig


class VoluntariosConfig(AppConfig):
    name = "voluntarios"
    verbose_name = "Voluntários"
```

Em `comviver/settings/base.py`, `INSTALLED_APPS`, após `"doacoes"`:
```python
    "voluntarios",
```

`voluntarios/models.py`:
```python
from datetime import date

from django.db import models

from core.models import Endereco, SoftDeleteModel
from core.uploads import caminho_opaco, validar_documento


class StatusVoluntario(models.TextChoices):
    ATIVO = "ATIVO", "Ativo"
    INATIVO = "INATIVO", "Inativo"


class DiaSemana(models.IntegerChoices):
    SEGUNDA = 0, "Segunda-feira"
    TERCA = 1, "Terça-feira"
    QUARTA = 2, "Quarta-feira"
    QUINTA = 3, "Quinta-feira"
    SEXTA = 4, "Sexta-feira"
    SABADO = 5, "Sábado"
    DOMINGO = 6, "Domingo"


class Turno(models.TextChoices):
    MANHA = "MANHA", "Manhã"
    TARDE = "TARDE", "Tarde"
    NOITE = "NOITE", "Noite"


ABREVIACAO_DIA = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}


class Funcao(SoftDeleteModel):
    """Tabela de apoio: cozinha, reforco escolar, recreacao, manutencao."""

    nome = models.CharField("nome", max_length=80, unique=True)
    descricao = models.TextField("descrição", blank=True)

    class Meta:
        verbose_name = "função"
        verbose_name_plural = "funções"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Voluntario(SoftDeleteModel, Endereco):
    nome = models.CharField("nome completo", max_length=150)
    cpf = models.CharField("CPF", max_length=11, blank=True, unique=True, null=True)
    rg = models.CharField("RG", max_length=20, blank=True)
    nascimento = models.DateField("data de nascimento", null=True, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)

    funcoes = models.ManyToManyField(
        Funcao, verbose_name="funções", blank=True, related_name="voluntarios"
    )
    data_cadastro = models.DateField("data de cadastro", default=date.today)
    status = models.CharField(
        "situação", max_length=10, choices=StatusVoluntario.choices,
        default=StatusVoluntario.ATIVO,
    )
    observacoes = models.TextField("observações", blank=True)

    criado_por = models.ForeignKey(
        "accounts.Usuario", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="voluntarios_cadastrados",
    )

    class Meta:
        verbose_name = "voluntário"
        verbose_name_plural = "voluntários"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs):
        if not self.cpf:
            self.cpf = None
        super().save(*args, **kwargs)

    @property
    def idade(self) -> int | None:
        if not self.nascimento:
            return None
        hoje = date.today()
        return (
            hoje.year
            - self.nascimento.year
            - ((hoje.month, hoje.day) < (self.nascimento.month, self.nascimento.day))
        )

    def esta_disponivel(self, dia_semana: int, turno: str) -> bool:
        return self.disponibilidades.filter(dia_semana=dia_semana, turno=turno).exists()

    @property
    def resumo_disponibilidade(self) -> str:
        """Ex.: 'Seg: manhã, tarde · Qua: manhã'.

        Aparece na listagem e na lista de sugestoes ao montar escala — o
        coordenador precisa ver isso sem abrir o cadastro.
        """
        por_dia: dict[int, list[str]] = {}
        for item in self.disponibilidades.order_by("dia_semana", "turno"):
            por_dia.setdefault(item.dia_semana, []).append(
                item.get_turno_display().lower()
            )
        if not por_dia:
            return "Não informada"
        return " · ".join(
            f"{ABREVIACAO_DIA[dia]}: {', '.join(turnos)}"
            for dia, turnos in sorted(por_dia.items())
        )


class Disponibilidade(models.Model):
    voluntario = models.ForeignKey(
        Voluntario, on_delete=models.CASCADE, related_name="disponibilidades"
    )
    dia_semana = models.IntegerField("dia da semana", choices=DiaSemana.choices)
    turno = models.CharField("turno", max_length=6, choices=Turno.choices)

    class Meta:
        verbose_name = "disponibilidade"
        verbose_name_plural = "disponibilidades"
        ordering = ["dia_semana", "turno"]
        constraints = [
            models.UniqueConstraint(
                fields=["voluntario", "dia_semana", "turno"],
                name="disponibilidade_unica",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_dia_semana_display()} — {self.get_turno_display()}"


class DocumentoVoluntario(SoftDeleteModel):
    voluntario = models.ForeignKey(
        Voluntario, on_delete=models.CASCADE, related_name="documentos"
    )
    arquivo = models.FileField(
        "arquivo",
        upload_to=caminho_opaco("voluntarios/documentos"),
        validators=[validar_documento],
    )
    tipo = models.CharField("tipo", max_length=80)

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"

    def __str__(self) -> str:
        return f"{self.tipo} — {self.voluntario.nome}"
```

- [ ] **Step 4: Escrever as factories**

`voluntarios/factories.py`:
```python
import factory

from voluntarios.models import DiaSemana, Disponibilidade, Funcao, Turno, Voluntario


class FuncaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Funcao

    nome = factory.Sequence(lambda n: f"Função {n}")


class VoluntarioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Voluntario

    nome = factory.Faker("name", locale="pt_BR")
    telefone = factory.Faker("cellphone_number", locale="pt_BR")
    email = factory.Faker("email")
    cidade = "Itajubá"
    uf = "MG"
    cpf = ""


class DisponibilidadeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Disponibilidade

    voluntario = factory.SubFactory(VoluntarioFactory)
    dia_semana = DiaSemana.SEGUNDA
    turno = Turno.MANHA
```

- [ ] **Step 5: Escrever formulários, views e URLs**

`voluntarios/forms.py`:
```python
from django import forms

from voluntarios.models import DiaSemana, Disponibilidade, Funcao, Turno, Voluntario


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.update({"class": "form-check-input"})
        elif isinstance(campo.widget, (forms.Select, forms.SelectMultiple)):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


class VoluntarioForm(forms.ModelForm):
    """Cadastro com a grade de disponibilidade embutida.

    A disponibilidade e o dado que faz a escala funcionar: pedi-la numa tela
    separada garante que ninguem preencha.
    """

    class Meta:
        model = Voluntario
        fields = [
            "nome", "cpf", "rg", "nascimento", "telefone", "email",
            "funcoes", "status",
            "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf",
            "observacoes",
        ]
        widgets = {
            "nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "funcoes": forms.CheckboxSelectMultiple,
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        _aplicar_classes(self.fields)
        self.fields["funcoes"].widget.attrs.pop("class", None)
        self.fields["funcoes"].queryset = Funcao.objects.all()

        # Uma caixa por combinacao de dia e turno.
        selecionadas = set()
        if self.instance.pk:
            selecionadas = {
                (d.dia_semana, d.turno)
                for d in self.instance.disponibilidades.all()
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
        cpf = "".join(filter(str.isdigit, self.cleaned_data.get("cpf", "")))
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
        """Devolve a grade pronta para o template: linhas de turno, colunas de dia."""
        return [
            {
                "turno": turno.label,
                "celulas": [self[f"disp_{dia.value}_{turno.value}"] for dia in DiaSemana],
            }
            for turno in Turno
        ]

    @property
    def cabecalho_dias(self):
        return [dia.label[:3] for dia in DiaSemana]


class FuncaoForm(forms.ModelForm):
    class Meta:
        model = Funcao
        fields = ["nome", "descricao"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        _aplicar_classes(self.fields)
```

`voluntarios/views.py`:
```python
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin
from core.views import BaseCreateView, BaseListView, BaseUpdateView
from voluntarios.forms import FuncaoForm, VoluntarioForm
from voluntarios.models import Funcao, StatusVoluntario, Voluntario

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
QUEM_GERENCIA = [Perfil.ADMIN, Perfil.OPERACIONAL]


class VoluntarioListView(BaseListView):
    model = Voluntario
    template_name = "voluntarios/voluntario_list.html"
    context_object_name = "voluntarios"
    campos_busca = ["nome", "email", "telefone"]
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("funcoes", "disponibilidades")
        situacao = self.request.GET.get("situacao", StatusVoluntario.ATIVO)
        if situacao != "TODOS":
            qs = qs.filter(status=situacao)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["situacao"] = self.request.GET.get("situacao", StatusVoluntario.ATIVO)
        return contexto


class VoluntarioDetailView(PerfilRequiredMixin, DetailView):
    model = Voluntario
    template_name = "voluntarios/voluntario_detail.html"
    context_object_name = "voluntario"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        from escalas.models import Alocacao

        contexto = super().get_context_data(**kwargs)
        contexto["alocacoes"] = (
            Alocacao.objects.filter(voluntario=self.object)
            .select_related("turno", "turno__atividade", "turno__escala")
            .order_by("-turno__data")[:20]
        )
        return contexto


class VoluntarioCreateView(BaseCreateView):
    model = Voluntario
    form_class = VoluntarioForm
    template_name = "voluntarios/voluntario_form.html"
    mensagem_sucesso = "Voluntário cadastrado."
    perfis_permitidos = QUEM_GERENCIA

    def get_success_url(self):
        return reverse("voluntarios:detalhe", args=[self.object.pk])


class VoluntarioUpdateView(BaseUpdateView):
    model = Voluntario
    form_class = VoluntarioForm
    template_name = "voluntarios/voluntario_form.html"
    mensagem_sucesso = "Dados do voluntário atualizados."
    perfis_permitidos = QUEM_GERENCIA

    def get_success_url(self):
        return reverse("voluntarios:detalhe", args=[self.object.pk])


class FuncaoListView(BaseListView):
    model = Funcao
    template_name = "voluntarios/funcao_list.html"
    context_object_name = "funcoes"
    campos_busca = ["nome"]
    perfis_permitidos = TODOS_OS_PERFIS


class FuncaoCreateView(BaseCreateView):
    model = Funcao
    form_class = FuncaoForm
    template_name = "voluntarios/funcao_form.html"
    mensagem_sucesso = "Função cadastrada."
    success_url = reverse_lazy("voluntarios:funcao_lista")
    perfis_permitidos = [Perfil.ADMIN]
```

`voluntarios/urls.py`:
```python
from django.urls import path

from voluntarios import views

app_name = "voluntarios"

urlpatterns = [
    path("voluntarios/", views.VoluntarioListView.as_view(), name="lista"),
    path("voluntarios/novo/", views.VoluntarioCreateView.as_view(), name="novo"),
    path("voluntarios/<int:pk>/", views.VoluntarioDetailView.as_view(), name="detalhe"),
    path("voluntarios/<int:pk>/editar/", views.VoluntarioUpdateView.as_view(), name="editar"),
    path("funcoes/", views.FuncaoListView.as_view(), name="funcao_lista"),
    path("funcoes/nova/", views.FuncaoCreateView.as_view(), name="funcao_nova"),
]
```

Em `comviver/urls.py`, antes de `core.urls`:
```python
    path("", include("voluntarios.urls")),
```

- [ ] **Step 6: Escrever os templates**

`templates/voluntarios/voluntario_form.html`:
```html
{% extends "base.html" %}
{% block titulo %}{% if object %}Editar voluntário{% else %}Novo voluntário{% endif %}{% endblock %}
{% block cabecalho %}{% if object %}Editar voluntário{% else %}Novo voluntário{% endif %}{% endblock %}

{% block conteudo %}
  <form method="post" style="max-width: 46rem;">
    {% csrf_token %}

    {% if form.non_field_errors %}
      <div class="alert alert-danger py-2">
        {% for erro in form.non_field_errors %}{{ erro }}{% endfor %}
      </div>
    {% endif %}

    <h2 class="h6 mb-3">Dados pessoais</h2>
    {% for campo in form %}
      {% if not campo.name|slice:":5" == "disp_" and campo.name != 'funcoes' %}
        <div class="mb-3">
          <label for="{{ campo.id_for_label }}" class="form-label">{{ campo.label }}</label>
          {{ campo }}
          {% if campo.help_text %}<div class="form-text">{{ campo.help_text }}</div>{% endif %}
          {% for erro in campo.errors %}
            <div class="form-text text-danger">{{ erro }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endfor %}

    <h2 class="h6 mt-4 mb-3">Funções</h2>
    <div class="row g-2 mb-4">
      {% for opcao in form.funcoes %}
        <div class="col-6 col-md-4">
          <div class="form-check">
            {{ opcao.tag }}
            <label class="form-check-label" for="{{ opcao.id_for_label }}">
              {{ opcao.choice_label }}
            </label>
          </div>
        </div>
      {% empty %}
        <div class="col-12">
          <p class="text-muted small">
            Nenhuma função cadastrada.
            {% if user.e_admin %}
              <a href="{% url 'voluntarios:funcao_nova' %}">Cadastrar a primeira</a>.
            {% else %}
              Peça à coordenação para cadastrar.
            {% endif %}
          </p>
        </div>
      {% endfor %}
    </div>

    <h2 class="h6 mt-4 mb-2">Disponibilidade</h2>
    <p class="text-muted small">
      Marque os períodos em que o voluntário pode vir. É o que filtra as
      sugestões ao montar a escala.
    </p>
    <div class="table-responsive mb-4">
      <table class="table table-bordered text-center align-middle mb-0">
        <thead>
          <tr>
            <th></th>
            {% for dia in form.cabecalho_dias %}<th class="small">{{ dia }}</th>{% endfor %}
          </tr>
        </thead>
        <tbody>
          {% for linha in form.grade_disponibilidade %}
            <tr>
              <th class="text-start small">{{ linha.turno }}</th>
              {% for celula in linha.celulas %}<td>{{ celula }}</td>{% endfor %}
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <button type="submit" class="btn btn-primary">Salvar</button>
    <a href="{% url 'voluntarios:lista' %}" class="btn btn-link">Cancelar</a>
  </form>
{% endblock %}
```

`templates/voluntarios/voluntario_list.html`:
```html
{% extends "base.html" %}
{% block titulo %}Voluntários{% endblock %}
{% block cabecalho %}Voluntários{% endblock %}

{% block acoes %}
  {% if user.perfil == 'ADMIN' or user.perfil == 'OPERACIONAL' %}
    <a href="{% url 'voluntarios:novo' %}" class="btn btn-primary">
      <i class="bi bi-plus-lg"></i> Novo voluntário
    </a>
  {% endif %}
{% endblock %}

{% block conteudo %}
  <form method="get" class="row g-2 mb-3">
    <div class="col-12 col-md-5">
      <input type="search" name="q" value="{{ busca }}" class="form-control"
             placeholder="Buscar por nome, e-mail ou telefone">
    </div>
    <div class="col-8 col-md-3">
      <select name="situacao" class="form-select">
        <option value="ATIVO" {% if situacao == 'ATIVO' %}selected{% endif %}>Ativos</option>
        <option value="INATIVO" {% if situacao == 'INATIVO' %}selected{% endif %}>Inativos</option>
        <option value="TODOS" {% if situacao == 'TODOS' %}selected{% endif %}>Todos</option>
      </select>
    </div>
    <div class="col-4 col-md-2">
      <button class="btn btn-outline-secondary w-100">Filtrar</button>
    </div>
  </form>

  <div class="table-responsive">
    <table class="table table-hover align-middle">
      <thead>
        <tr><th>Nome</th><th>Contato</th><th>Funções</th><th>Disponibilidade</th><th>Situação</th></tr>
      </thead>
      <tbody>
        {% for voluntario in voluntarios %}
          <tr>
            <td><a href="{% url 'voluntarios:detalhe' voluntario.pk %}">{{ voluntario.nome }}</a></td>
            <td class="small text-muted">
              {{ voluntario.telefone|default:"—" }}<br>{{ voluntario.email|default:"" }}
            </td>
            <td class="small">
              {% for funcao in voluntario.funcoes.all %}
                <span class="badge text-bg-light text-dark">{{ funcao.nome }}</span>
              {% empty %}<span class="text-muted">—</span>{% endfor %}
            </td>
            <td class="small text-muted">{{ voluntario.resumo_disponibilidade }}</td>
            <td>
              {% if voluntario.status == 'ATIVO' %}
                <span class="badge text-bg-success">Ativo</span>
              {% else %}
                <span class="badge text-bg-secondary">Inativo</span>
              {% endif %}
            </td>
          </tr>
        {% empty %}
          <tr><td colspan="5" class="text-muted">Nenhum voluntário encontrado.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% endblock %}
```

`templates/voluntarios/voluntario_detail.html`:
```html
{% extends "base.html" %}
{% block titulo %}{{ voluntario.nome }}{% endblock %}
{% block cabecalho %}{{ voluntario.nome }}{% endblock %}

{% block acoes %}
  {% if user.perfil == 'ADMIN' or user.perfil == 'OPERACIONAL' %}
    <a href="{% url 'voluntarios:editar' voluntario.pk %}"
       class="btn btn-outline-secondary">Editar</a>
  {% endif %}
{% endblock %}

{% block conteudo %}
  <div class="row g-4">
    <div class="col-12 col-lg-5">
      <div class="card mb-3">
        <div class="card-body">
          <dl class="row mb-0">
            <dt class="col-5">Telefone</dt><dd class="col-7">{{ voluntario.telefone|default:"—" }}</dd>
            <dt class="col-5">E-mail</dt><dd class="col-7">{{ voluntario.email|default:"—" }}</dd>
            <dt class="col-5">Idade</dt>
            <dd class="col-7">{% if voluntario.idade %}{{ voluntario.idade }} anos{% else %}—{% endif %}</dd>
            <dt class="col-5">Desde</dt><dd class="col-7">{{ voluntario.data_cadastro|date:"d/m/Y" }}</dd>
            <dt class="col-5">Disponibilidade</dt>
            <dd class="col-7">{{ voluntario.resumo_disponibilidade }}</dd>
          </dl>
        </div>
      </div>
    </div>

    <div class="col-12 col-lg-7">
      <div class="card">
        <div class="card-header">Participação nas atividades</div>
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <thead><tr><th>Data</th><th>Atividade</th><th>Situação</th></tr></thead>
            <tbody>
              {% for alocacao in alocacoes %}
                <tr>
                  <td>{{ alocacao.turno.data|date:"d/m/Y" }}</td>
                  <td>{{ alocacao.turno.atividade.nome }}</td>
                  <td>
                    {% if alocacao.status == 'CONFIRMADO' %}
                      <span class="badge text-bg-success">Compareceu</span>
                    {% elif alocacao.status == 'FALTOU' %}
                      <span class="badge text-bg-danger">Faltou</span>
                    {% else %}
                      <span class="badge text-bg-light text-dark">Previsto</span>
                    {% endif %}
                  </td>
                </tr>
              {% empty %}
                <tr><td colspan="3" class="text-muted">Nenhuma participação registrada.</td></tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
{% endblock %}
```

`templates/voluntarios/funcao_list.html` e `funcao_form.html` seguem o esqueleto
de lista e formulário já usado nas fases anteriores: tabela com `nome` e
`descricao`, botão "Nova função" visível só para Admin, e formulário com os dois
campos e link de cancelamento para `{% url 'voluntarios:funcao_lista' %}`.

- [ ] **Step 7: Acrescentar ao menu**

Em `core/context_processors.py`:
```python
    itens.append(
        {"rotulo": "Voluntários", "url": reverse("voluntarios:lista"), "icone": "person-badge"}
    )
```

- [ ] **Step 8: Gerar migration e rodar os testes**

```bash
python manage.py makemigrations voluntarios
python manage.py migrate
```

```bash
pytest voluntarios/tests/ -v --create-db
```
Esperado: todos passando, exceto `VoluntarioDetailView`, que importa
`escalas.models.Alocacao` — criado na Task 2. Comentar temporariamente aquele
bloco ou rodar novamente ao fim da Task 2.

- [ ] **Step 9: Commit**

```bash
git add voluntarios templates/voluntarios core comviver
git commit -m "feat(voluntarios): adiciona cadastro com grade de disponibilidade"
```

---

## Task 2: Models de escala e a regra de conflito

A regra central da fase. Um voluntário alocado em dois turnos que se sobrepõem é
um erro que só aparece no dia, com a casa sem gente.

**Files:**
- Create: `escalas/` (app completo), `escalas/models.py`, `escalas/factories.py`
- Create: `escalas/tests/test_models.py`, `escalas/tests/test_conflito.py`
- Modify: `comviver/settings/base.py`

**Interfaces:**
- Consumes: `voluntarios.models.Voluntario`, `core.models.SoftDeleteModel`
- Produces:
  - `escalas.models.Atividade`
  - `escalas.models.StatusEscala` — `RASCUNHO`, `PUBLICADA`
  - `escalas.models.StatusAlocacao` — `PREVISTO`, `CONFIRMADO`, `FALTOU`
  - `escalas.models.Escala` — propriedade `total_turnos: int`, `turnos_descobertos: int`
  - `escalas.models.Turno` — propriedades `vagas_ocupadas: int`, `esta_descoberto: bool`, `turno_do_dia: str`; método `sobrepoe(outro: Turno) -> bool`
  - `escalas.models.Alocacao` — `clean()` recusando sobreposição; `unique(turno, voluntario)`

- [ ] **Step 1: Escrever os testes que falham**

`escalas/tests/test_conflito.py`:
```python
from datetime import date, time, timedelta

import pytest
from django.core.exceptions import ValidationError

from escalas.factories import AlocacaoFactory, EscalaFactory, TurnoFactory
from voluntarios.factories import VoluntarioFactory

pytestmark = pytest.mark.django_db


def _turno(escala, dia, inicio, fim):
    return TurnoFactory(
        escala=escala, data=dia,
        hora_inicio=time(inicio, 0), hora_fim=time(fim, 0),
    )


class TestSobreposicaoDeTurno:
    def test_turnos_no_mesmo_horario_se_sobrepoem(self):
        escala = EscalaFactory()
        hoje = date.today()
        a = _turno(escala, hoje, 8, 12)
        b = _turno(escala, hoje, 8, 12)
        assert a.sobrepoe(b) is True

    def test_turnos_com_intersecao_parcial_se_sobrepoem(self):
        escala = EscalaFactory()
        hoje = date.today()
        a = _turno(escala, hoje, 8, 12)
        b = _turno(escala, hoje, 11, 15)
        assert a.sobrepoe(b) is True

    def test_turnos_encostados_nao_se_sobrepoem(self):
        """Terminar as 12h e comecar as 12h e troca de turno, nao conflito."""
        escala = EscalaFactory()
        hoje = date.today()
        a = _turno(escala, hoje, 8, 12)
        b = _turno(escala, hoje, 12, 16)
        assert a.sobrepoe(b) is False

    def test_turnos_em_dias_diferentes_nao_se_sobrepoem(self):
        escala = EscalaFactory()
        hoje = date.today()
        a = _turno(escala, hoje, 8, 12)
        b = _turno(escala, hoje + timedelta(days=1), 8, 12)
        assert a.sobrepoe(b) is False


class TestConflitoNaAlocacao:
    def test_alocar_em_turnos_sobrepostos_e_recusado(self):
        escala = EscalaFactory()
        hoje = date.today()
        voluntario = VoluntarioFactory(nome="Ana Souza")
        AlocacaoFactory(turno=_turno(escala, hoje, 8, 12), voluntario=voluntario)

        conflitante = AlocacaoFactory.build(
            turno=_turno(escala, hoje, 10, 14), voluntario=voluntario
        )
        with pytest.raises(ValidationError) as erro:
            conflitante.full_clean()
        assert "já está escalada" in str(erro.value)

    def test_mensagem_de_conflito_diz_qual_e_o_outro_turno(self):
        escala = EscalaFactory()
        hoje = date.today()
        voluntario = VoluntarioFactory(nome="Ana Souza")
        AlocacaoFactory(turno=_turno(escala, hoje, 8, 12), voluntario=voluntario)

        conflitante = AlocacaoFactory.build(
            turno=_turno(escala, hoje, 10, 14), voluntario=voluntario
        )
        with pytest.raises(ValidationError) as erro:
            conflitante.full_clean()
        assert "08:00" in str(erro.value)

    def test_alocar_em_turnos_encostados_e_permitido(self):
        escala = EscalaFactory()
        hoje = date.today()
        voluntario = VoluntarioFactory()
        AlocacaoFactory(turno=_turno(escala, hoje, 8, 12), voluntario=voluntario)
        seguinte = AlocacaoFactory.build(
            turno=_turno(escala, hoje, 12, 16), voluntario=voluntario
        )
        seguinte.full_clean()  # nao levanta

    def test_voluntarios_diferentes_no_mesmo_turno_e_permitido(self):
        escala = EscalaFactory()
        turno = _turno(escala, date.today(), 8, 12)
        AlocacaoFactory(turno=turno, voluntario=VoluntarioFactory())
        outra = AlocacaoFactory.build(turno=turno, voluntario=VoluntarioFactory())
        outra.full_clean()  # nao levanta

    def test_editar_a_propria_alocacao_nao_conflita_consigo(self):
        """Sem excluir a si mesma da checagem, salvar uma alocacao existente
        acusaria conflito com ela propria."""
        escala = EscalaFactory()
        alocacao = AlocacaoFactory(turno=_turno(escala, date.today(), 8, 12))
        alocacao.observacao = "Chega 15 minutos mais cedo."
        alocacao.full_clean()  # nao levanta

    def test_mesmo_voluntario_duas_vezes_no_mesmo_turno_e_recusado(self):
        from django.db import IntegrityError

        escala = EscalaFactory()
        turno = _turno(escala, date.today(), 8, 12)
        voluntario = VoluntarioFactory()
        AlocacaoFactory(turno=turno, voluntario=voluntario)
        with pytest.raises(IntegrityError):
            AlocacaoFactory(turno=turno, voluntario=voluntario)

    def test_conflito_atravessa_escalas_diferentes(self):
        """Duas escalas da mesma semana nao podem alocar a mesma pessoa no
        mesmo horario — a pessoa e uma so."""
        hoje = date.today()
        voluntario = VoluntarioFactory()
        AlocacaoFactory(turno=_turno(EscalaFactory(), hoje, 8, 12), voluntario=voluntario)
        outra = AlocacaoFactory.build(
            turno=_turno(EscalaFactory(), hoje, 9, 13), voluntario=voluntario
        )
        with pytest.raises(ValidationError):
            outra.full_clean()
```

`escalas/tests/test_models.py`:
```python
from datetime import date, time, timedelta

import pytest

from escalas.factories import AlocacaoFactory, EscalaFactory, TurnoFactory
from escalas.models import StatusEscala
from voluntarios.factories import VoluntarioFactory

pytestmark = pytest.mark.django_db


class TestEscala:
    def test_escala_nasce_como_rascunho(self):
        assert EscalaFactory().status == StatusEscala.RASCUNHO

    def test_total_de_turnos(self):
        escala = EscalaFactory()
        TurnoFactory.create_batch(3, escala=escala)
        assert escala.total_turnos == 3

    def test_conta_turnos_descobertos(self):
        escala = EscalaFactory()
        coberto = TurnoFactory(escala=escala, vagas=1)
        AlocacaoFactory(turno=coberto)
        TurnoFactory(escala=escala, vagas=2)  # descoberto
        assert escala.turnos_descobertos == 1

    def test_periodo_invalido_e_recusado(self):
        from django.core.exceptions import ValidationError

        escala = EscalaFactory.build(
            data_inicio=date.today(), data_fim=date.today() - timedelta(days=1)
        )
        with pytest.raises(ValidationError):
            escala.full_clean()


class TestTurno:
    def test_vagas_ocupadas_conta_alocacoes(self):
        turno = TurnoFactory(vagas=3)
        AlocacaoFactory.create_batch(2, turno=turno)
        assert turno.vagas_ocupadas == 2

    def test_turno_sem_ninguem_esta_descoberto(self):
        assert TurnoFactory(vagas=2).esta_descoberto is True

    def test_turno_parcialmente_preenchido_ainda_esta_descoberto(self):
        """Duas vagas com uma pessoa e um buraco, e o coordenador precisa ver."""
        turno = TurnoFactory(vagas=2)
        AlocacaoFactory(turno=turno)
        assert turno.esta_descoberto is True

    def test_turno_completo_nao_esta_descoberto(self):
        turno = TurnoFactory(vagas=2)
        AlocacaoFactory.create_batch(2, turno=turno)
        assert turno.esta_descoberto is False

    def test_turno_do_dia_pela_hora_de_inicio(self):
        assert TurnoFactory(hora_inicio=time(8, 0)).turno_do_dia == "MANHA"
        assert TurnoFactory(hora_inicio=time(14, 0)).turno_do_dia == "TARDE"
        assert TurnoFactory(hora_inicio=time(19, 0)).turno_do_dia == "NOITE"

    def test_hora_fim_antes_do_inicio_e_recusada(self):
        from django.core.exceptions import ValidationError

        turno = TurnoFactory.build(hora_inicio=time(14, 0), hora_fim=time(10, 0))
        with pytest.raises(ValidationError):
            turno.full_clean()
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest escalas/tests/ -v
```
Esperado: `ModuleNotFoundError: No module named 'escalas'`.

- [ ] **Step 3: Criar o app e escrever os models**

```bash
python manage.py startapp escalas
mkdir escalas/tests && touch escalas/tests/__init__.py
rm escalas/tests.py
```

`escalas/apps.py`:
```python
from django.apps import AppConfig


class EscalasConfig(AppConfig):
    name = "escalas"
    verbose_name = "Escalas"
```

Em `comviver/settings/base.py`, `INSTALLED_APPS`, após `"voluntarios"`:
```python
    "escalas",
```

`escalas/models.py`:
```python
from datetime import time

from django.core.exceptions import ValidationError
from django.db import models

from core.models import SoftDeleteModel


class StatusEscala(models.TextChoices):
    RASCUNHO = "RASCUNHO", "Rascunho"
    PUBLICADA = "PUBLICADA", "Publicada"


class StatusAlocacao(models.TextChoices):
    PREVISTO = "PREVISTO", "Previsto"
    CONFIRMADO = "CONFIRMADO", "Compareceu"
    FALTOU = "FALTOU", "Faltou"


class Atividade(SoftDeleteModel):
    """Tabela de apoio: acompanhamento escolar, recreacao, cozinha, portaria."""

    nome = models.CharField("nome", max_length=100, unique=True)
    descricao = models.TextField("descrição", blank=True)
    ativa = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "atividade"
        verbose_name_plural = "atividades"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Escala(SoftDeleteModel):
    """Conjunto de turnos de um periodo.

    Em RASCUNHO pode ser remontada livremente; ao ser publicada, vira registro.
    """

    titulo = models.CharField("título", max_length=120)
    data_inicio = models.DateField("início")
    data_fim = models.DateField("término")
    status = models.CharField(
        "situação", max_length=10, choices=StatusEscala.choices,
        default=StatusEscala.RASCUNHO,
    )
    observacoes = models.TextField("observações", blank=True)

    criado_por = models.ForeignKey(
        "accounts.Usuario", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="escalas_criadas",
    )

    class Meta:
        verbose_name = "escala"
        verbose_name_plural = "escalas"
        ordering = ["-data_inicio"]

    def __str__(self) -> str:
        return self.titulo

    def clean(self):
        super().clean()
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError(
                {"data_fim": "O término não pode ser anterior ao início."}
            )

    @property
    def total_turnos(self) -> int:
        return self.turnos.count()

    @property
    def turnos_descobertos(self) -> int:
        return sum(1 for turno in self.turnos.all() if turno.esta_descoberto)

    @property
    def esta_publicada(self) -> bool:
        return self.status == StatusEscala.PUBLICADA


class Turno(SoftDeleteModel):
    escala = models.ForeignKey(Escala, on_delete=models.CASCADE, related_name="turnos")
    data = models.DateField("data")
    hora_inicio = models.TimeField("início")
    hora_fim = models.TimeField("término")
    atividade = models.ForeignKey(
        Atividade, on_delete=models.PROTECT, related_name="turnos"
    )
    vagas = models.PositiveSmallIntegerField("vagas", default=1)
    observacoes = models.CharField("observações", max_length=200, blank=True)

    class Meta:
        verbose_name = "turno"
        verbose_name_plural = "turnos"
        ordering = ["data", "hora_inicio"]

    def __str__(self) -> str:
        return (
            f"{self.data:%d/%m} {self.hora_inicio:%H:%M}–{self.hora_fim:%H:%M} "
            f"· {self.atividade.nome}"
        )

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fim and self.hora_fim <= self.hora_inicio:
            raise ValidationError(
                {"hora_fim": "O término precisa ser depois do início."}
            )

    def sobrepoe(self, outro: "Turno") -> bool:
        """Dois turnos no mesmo dia com intersecao de horario.

        Encostar nao e sobrepor: terminar as 12h e comecar as 12h e troca de
        turno, situacao normal.
        """
        if self.data != outro.data:
            return False
        return self.hora_inicio < outro.hora_fim and outro.hora_inicio < self.hora_fim

    @property
    def vagas_ocupadas(self) -> int:
        return self.alocacoes.count()

    @property
    def vagas_livres(self) -> int:
        return max(0, self.vagas - self.vagas_ocupadas)

    @property
    def esta_descoberto(self) -> bool:
        """Qualquer vaga em aberto conta: duas vagas com uma pessoa e um buraco."""
        return self.vagas_ocupadas < self.vagas

    @property
    def turno_do_dia(self) -> str:
        """Classifica pela hora de inicio, para casar com a disponibilidade
        declarada pelo voluntario."""
        if self.hora_inicio < time(12, 0):
            return "MANHA"
        if self.hora_inicio < time(18, 0):
            return "TARDE"
        return "NOITE"


class Alocacao(SoftDeleteModel):
    """Voluntario alocado em um turno."""

    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name="alocacoes")
    voluntario = models.ForeignKey(
        "voluntarios.Voluntario", on_delete=models.CASCADE, related_name="alocacoes"
    )
    status = models.CharField(
        "situação", max_length=10, choices=StatusAlocacao.choices,
        default=StatusAlocacao.PREVISTO,
    )
    observacao = models.CharField("observação", max_length=200, blank=True)

    class Meta:
        verbose_name = "alocação"
        verbose_name_plural = "alocações"
        constraints = [
            models.UniqueConstraint(
                fields=["turno", "voluntario"], name="alocacao_unica_por_turno"
            )
        ]

    def __str__(self) -> str:
        return f"{self.voluntario.nome} — {self.turno}"

    def clean(self):
        """Recusa alocar a mesma pessoa em turnos que se sobrepoem.

        A regra vive aqui, e nao na view, para valer igualmente no admin, em
        importacao e em qualquer tela futura. A pessoa e uma so: o conflito
        atravessa escalas diferentes.
        """
        super().clean()
        if not self.turno_id or not self.voluntario_id:
            return

        outras = (
            Alocacao.objects.filter(
                voluntario_id=self.voluntario_id, turno__data=self.turno.data
            )
            .exclude(pk=self.pk)
            .select_related("turno")
        )

        for outra in outras:
            if self.turno.sobrepoe(outra.turno):
                raise ValidationError(
                    f"{self.voluntario.nome} já está escalada neste horário: "
                    f"{outra.turno.hora_inicio:%H:%M}–{outra.turno.hora_fim:%H:%M}, "
                    f"{outra.turno.atividade.nome}."
                )
```

- [ ] **Step 4: Escrever as factories**

`escalas/factories.py`:
```python
from datetime import date, time, timedelta

import factory

from escalas.models import Alocacao, Atividade, Escala, Turno
from voluntarios.factories import VoluntarioFactory


class AtividadeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Atividade

    nome = factory.Sequence(lambda n: f"Atividade {n}")


class EscalaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Escala

    titulo = factory.Sequence(lambda n: f"Escala {n}")
    data_inicio = factory.LazyFunction(date.today)
    data_fim = factory.LazyFunction(lambda: date.today() + timedelta(days=6))


class TurnoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Turno

    escala = factory.SubFactory(EscalaFactory)
    data = factory.LazyFunction(date.today)
    hora_inicio = time(8, 0)
    hora_fim = time(12, 0)
    atividade = factory.SubFactory(AtividadeFactory)
    vagas = 1


class AlocacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Alocacao

    turno = factory.SubFactory(TurnoFactory)
    voluntario = factory.SubFactory(VoluntarioFactory)
```

- [ ] **Step 5: Gerar migration e rodar**

```bash
python manage.py makemigrations escalas
python manage.py migrate
```

```bash
pytest escalas/tests/ voluntarios/tests/ -v --create-db
```
Esperado: todos passando, inclusive os de `voluntarios` que dependiam de
`escalas.models.Alocacao`.

- [ ] **Step 6: Commit**

```bash
git add escalas comviver/settings/base.py
git commit -m "feat(escalas): adiciona Escala, Turno e Alocacao com bloqueio de conflito"
```

---

## Task 3: Grade semanal e alocação

A tela que mais define a percepção de qualidade do sistema.

**Files:**
- Create: `escalas/views.py`, `escalas/urls.py`, `escalas/forms.py`, `escalas/services.py`
- Create: `templates/escalas/escala_grade.html`, `escala_list.html`, `escala_form.html`
- Create: `templates/escalas/partials/_celula_turno.html`, `_lista_disponiveis.html`
- Create: `escalas/tests/test_grade.py`
- Modify: `comviver/urls.py`, `core/context_processors.py`, `core/views.py`

**Interfaces:**
- Consumes: `escalas.models.*` (Task 2), `voluntarios.models.Voluntario`
- Produces:
  - `escalas.services.voluntarios_disponiveis(turno) -> QuerySet[Voluntario]`
  - `escalas.services.grade_da_escala(escala) -> dict`
  - `escalas.services.turnos_descobertos_proximos(dias=7) -> QuerySet[Turno]`
  - rotas `escalas:lista`, `escalas:nova`, `escalas:grade`, `escalas:turno_novo`, `escalas:alocar`, `escalas:desalocar`, `escalas:publicar`

- [ ] **Step 1: Escrever os testes que falham**

`escalas/tests/test_grade.py`:
```python
from datetime import date, time, timedelta

import pytest
from django.urls import reverse

from escalas.factories import AlocacaoFactory, AtividadeFactory, EscalaFactory, TurnoFactory
from escalas.models import Alocacao, StatusEscala
from escalas.services import turnos_descobertos_proximos, voluntarios_disponiveis
from voluntarios.factories import DisponibilidadeFactory, VoluntarioFactory
from voluntarios.models import StatusVoluntario, Turno as TurnoDisponibilidade

pytestmark = pytest.mark.django_db


class TestVoluntariosDisponiveis:
    def test_sugere_quem_declarou_o_dia_e_turno(self):
        segunda = date(2026, 9, 21)  # segunda-feira
        turno = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        disponivel = VoluntarioFactory(nome="Ana")
        DisponibilidadeFactory(
            voluntario=disponivel, dia_semana=0, turno=TurnoDisponibilidade.MANHA
        )
        VoluntarioFactory(nome="Bruno")  # sem disponibilidade declarada

        nomes = [v.nome for v in voluntarios_disponiveis(turno)]
        assert nomes == ["Ana"]

    def test_nao_sugere_quem_declarou_outro_turno(self):
        segunda = date(2026, 9, 21)
        turno = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=0, turno=TurnoDisponibilidade.NOITE
        )
        assert voluntario not in voluntarios_disponiveis(turno)

    def test_nao_sugere_voluntario_inativo(self):
        segunda = date(2026, 9, 21)
        turno = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        inativo = VoluntarioFactory(status=StatusVoluntario.INATIVO)
        DisponibilidadeFactory(
            voluntario=inativo, dia_semana=0, turno=TurnoDisponibilidade.MANHA
        )
        assert inativo not in voluntarios_disponiveis(turno)

    def test_nao_sugere_quem_ja_esta_alocado_no_turno(self):
        segunda = date(2026, 9, 21)
        turno = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=0, turno=TurnoDisponibilidade.MANHA
        )
        AlocacaoFactory(turno=turno, voluntario=voluntario)
        assert voluntario not in voluntarios_disponiveis(turno)

    def test_nao_sugere_quem_tem_conflito_de_horario(self):
        """Sugerir quem vai ser recusado pelo clean() so gera frustracao."""
        segunda = date(2026, 9, 21)
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=0, turno=TurnoDisponibilidade.MANHA
        )
        ocupado = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        AlocacaoFactory(turno=ocupado, voluntario=voluntario)

        novo = TurnoFactory(data=segunda, hora_inicio=time(10, 0), hora_fim=time(14, 0))
        assert voluntario not in voluntarios_disponiveis(novo)


class TestTelaDaGrade:
    def test_tecnico_ve_a_grade_mas_nao_aloca(self, client, usuario_tecnico):
        escala = EscalaFactory()
        client.force_login(usuario_tecnico)
        assert client.get(reverse("escalas:grade", args=[escala.pk])).status_code == 200
        turno = TurnoFactory(escala=escala)
        voluntario = VoluntarioFactory()
        resposta = client.post(
            reverse("escalas:alocar", args=[turno.pk]), {"voluntario": voluntario.pk}
        )
        assert resposta.status_code == 403

    def test_operacional_aloca(self, client, usuario_operacional):
        escala = EscalaFactory()
        turno = TurnoFactory(escala=escala)
        voluntario = VoluntarioFactory()
        client.force_login(usuario_operacional)
        client.post(reverse("escalas:alocar", args=[turno.pk]), {"voluntario": voluntario.pk})
        assert Alocacao.objects.filter(turno=turno, voluntario=voluntario).exists()

    def test_alocacao_conflitante_devolve_mensagem(self, client, usuario_operacional):
        hoje = date.today()
        escala = EscalaFactory()
        voluntario = VoluntarioFactory(nome="Ana Souza")
        ocupado = TurnoFactory(
            escala=escala, data=hoje, hora_inicio=time(8, 0), hora_fim=time(12, 0)
        )
        AlocacaoFactory(turno=ocupado, voluntario=voluntario)
        novo = TurnoFactory(
            escala=escala, data=hoje, hora_inicio=time(10, 0), hora_fim=time(14, 0)
        )

        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("escalas:alocar", args=[novo.pk]), {"voluntario": voluntario.pk}
        )
        assert "já está escalada" in resposta.content.decode()
        assert Alocacao.objects.filter(turno=novo).count() == 0

    def test_mensagem_de_conflito_escapa_o_nome(self, client, usuario_operacional):
        """O nome do voluntario entra na mensagem de erro. Sem escape, um nome
        com marcacao viraria XSS refletido em quem monta a escala."""
        hoje = date.today()
        escala = EscalaFactory()
        voluntario = VoluntarioFactory(nome="<script>alert(1)</script>")
        ocupado = TurnoFactory(
            escala=escala, data=hoje, hora_inicio=time(8, 0), hora_fim=time(12, 0)
        )
        AlocacaoFactory(turno=ocupado, voluntario=voluntario)
        novo = TurnoFactory(
            escala=escala, data=hoje, hora_inicio=time(10, 0), hora_fim=time(14, 0)
        )

        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("escalas:alocar", args=[novo.pk]), {"voluntario": voluntario.pk}
        )
        conteudo = resposta.content.decode()
        assert "<script>alert(1)</script>" not in conteudo
        assert "&lt;script&gt;" in conteudo

    def test_alocar_voluntario_inativo_e_recusado(self, client, usuario_operacional):
        from voluntarios.models import StatusVoluntario

        turno = TurnoFactory()
        inativo = VoluntarioFactory(status=StatusVoluntario.INATIVO)
        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("escalas:alocar", args=[turno.pk]), {"voluntario": inativo.pk}
        )
        assert resposta.status_code == 404
        assert not Alocacao.objects.filter(turno=turno).exists()

    def test_desalocar_remove_a_alocacao(self, client, usuario_operacional):
        alocacao = AlocacaoFactory()
        client.force_login(usuario_operacional)
        client.post(reverse("escalas:desalocar", args=[alocacao.pk]))
        assert not Alocacao.objects.filter(pk=alocacao.pk).exists()

    def test_grade_marca_turno_descoberto(self, client, usuario_operacional):
        escala = EscalaFactory()
        TurnoFactory(escala=escala, vagas=2)
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("escalas:grade", args=[escala.pk]))
        assert resposta.context["escala"].turnos_descobertos == 1


class TestPublicacao:
    def test_publicar_muda_o_status(self, client, usuario_operacional):
        escala = EscalaFactory()
        TurnoFactory(escala=escala)
        client.force_login(usuario_operacional)
        client.post(reverse("escalas:publicar", args=[escala.pk]))
        escala.refresh_from_db()
        assert escala.status == StatusEscala.PUBLICADA

    def test_escala_sem_turno_nao_e_publicada(self, client, usuario_operacional):
        escala = EscalaFactory()
        client.force_login(usuario_operacional)
        client.post(reverse("escalas:publicar", args=[escala.pk]), follow=True)
        escala.refresh_from_db()
        assert escala.status == StatusEscala.RASCUNHO

    def test_tecnico_nao_publica(self, client, usuario_tecnico):
        escala = EscalaFactory()
        client.force_login(usuario_tecnico)
        assert client.post(reverse("escalas:publicar", args=[escala.pk])).status_code == 403


class TestTurnosDescobertosProximos:
    def test_lista_turnos_sem_gente_nos_proximos_dias(self):
        TurnoFactory(data=date.today() + timedelta(days=2), vagas=1)
        coberto = TurnoFactory(data=date.today() + timedelta(days=3), vagas=1)
        AlocacaoFactory(turno=coberto)
        assert turnos_descobertos_proximos(dias=7).count() == 1

    def test_ignora_turno_fora_da_janela(self):
        TurnoFactory(data=date.today() + timedelta(days=30), vagas=1)
        assert turnos_descobertos_proximos(dias=7).count() == 0

    def test_ignora_turno_no_passado(self):
        TurnoFactory(data=date.today() - timedelta(days=2), vagas=1)
        assert turnos_descobertos_proximos(dias=7).count() == 0
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest escalas/tests/test_grade.py -v
```
Esperado: `ModuleNotFoundError: No module named 'escalas.services'`.

- [ ] **Step 3: Escrever `escalas/services.py`**

```python
from datetime import date, timedelta

from django.db.models import Count, F, Q, QuerySet

from escalas.models import Alocacao, Turno
from voluntarios.models import StatusVoluntario, Voluntario


def voluntarios_disponiveis(turno: Turno) -> QuerySet[Voluntario]:
    """Voluntarios que podem assumir este turno.

    Filtra por quatro criterios, nesta ordem: esta ativo, declarou o dia e o
    turno, ainda nao esta neste turno, e nao tem conflito de horario no dia.

    O ultimo criterio evita sugerir alguem que o clean() do model recusaria —
    oferecer e depois recusar so gera frustracao.
    """
    dia_semana = turno.data.weekday()

    candidatos = Voluntario.objects.filter(
        status=StatusVoluntario.ATIVO,
        disponibilidades__dia_semana=dia_semana,
        disponibilidades__turno=turno.turno_do_dia,
    ).exclude(alocacoes__turno=turno).distinct()

    ocupados_no_dia = (
        Alocacao.objects.filter(turno__data=turno.data)
        .exclude(turno=turno)
        .select_related("turno")
    )
    com_conflito = {
        alocacao.voluntario_id
        for alocacao in ocupados_no_dia
        if turno.sobrepoe(alocacao.turno)
    }

    return candidatos.exclude(pk__in=com_conflito)


def grade_da_escala(escala) -> dict:
    """Monta a grade: linhas de faixa horaria, colunas de dia.

    Devolve `dias` (as colunas) e `linhas`, cada uma com a faixa e a lista de
    turnos por dia — None onde nao ha turno.
    """
    turnos = (
        escala.turnos.select_related("atividade")
        .prefetch_related("alocacoes__voluntario")
        .order_by("hora_inicio", "data")
    )

    dias = []
    dia = escala.data_inicio
    while dia <= escala.data_fim:
        dias.append(dia)
        dia += timedelta(days=1)

    faixas: dict[tuple, dict] = {}
    for turno in turnos:
        chave = (turno.hora_inicio, turno.hora_fim)
        faixa = faixas.setdefault(
            chave,
            {
                "hora_inicio": turno.hora_inicio,
                "hora_fim": turno.hora_fim,
                "por_dia": {d: None for d in dias},
            },
        )
        faixa["por_dia"][turno.data] = turno

    linhas = [
        {
            "hora_inicio": faixa["hora_inicio"],
            "hora_fim": faixa["hora_fim"],
            "celulas": [faixa["por_dia"][d] for d in dias],
        }
        for _, faixa in sorted(faixas.items())
    ]

    return {"dias": dias, "linhas": linhas}


def turnos_descobertos_proximos(dias: int = 7) -> QuerySet[Turno]:
    """Turnos com vaga em aberto na janela a frente.

    E a pergunta real do coordenador: onde esta o buraco.
    """
    hoje = date.today()
    return (
        Turno.objects.filter(data__gte=hoje, data__lte=hoje + timedelta(days=dias))
        .annotate(ocupadas=Count("alocacoes"))
        .filter(ocupadas__lt=F("vagas"))
        .select_related("atividade", "escala")
        .order_by("data", "hora_inicio")
    )
```

- [ ] **Step 4: Escrever `escalas/forms.py`**

```python
from django import forms

from escalas.models import Atividade, Escala, Turno


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


class EscalaForm(forms.ModelForm):
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
        _aplicar_classes(self.fields)


class TurnoForm(forms.ModelForm):
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
```

- [ ] **Step 5: Escrever `escalas/views.py`**

```python
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin
from core.views import BaseCreateView, BaseListView
from escalas.forms import EscalaForm, TurnoForm
from escalas.models import Alocacao, Escala, StatusEscala, Turno
from escalas.services import grade_da_escala, voluntarios_disponiveis
from voluntarios.models import StatusVoluntario, Voluntario

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
QUEM_MONTA = [Perfil.ADMIN, Perfil.OPERACIONAL]


class EscalaListView(BaseListView):
    model = Escala
    template_name = "escalas/escala_list.html"
    context_object_name = "escalas"
    campos_busca = ["titulo"]
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        return super().get_queryset().prefetch_related("turnos__alocacoes")


class EscalaCreateView(BaseCreateView):
    model = Escala
    form_class = EscalaForm
    template_name = "escalas/escala_form.html"
    mensagem_sucesso = "Escala criada. Agora adicione os turnos."
    perfis_permitidos = QUEM_MONTA

    def get_success_url(self):
        return reverse("escalas:grade", args=[self.object.pk])


class EscalaGradeView(PerfilRequiredMixin, DetailView):
    """Grade semanal: turnos nas linhas, dias nas colunas.

    A pergunta real do coordenador nao e 'quem esta escalado', e sim 'onde
    esta o buraco' — por isso turno descoberto recebe destaque.
    """

    model = Escala
    template_name = "escalas/escala_grade.html"
    context_object_name = "escala"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto |= grade_da_escala(self.object)
        contexto["pode_montar"] = self.request.user.perfil in QUEM_MONTA
        return contexto


class TurnoCreateView(BaseCreateView):
    model = Turno
    form_class = TurnoForm
    template_name = "escalas/turno_form.html"
    mensagem_sucesso = "Turno adicionado à escala."
    perfis_permitidos = QUEM_MONTA

    def dispatch(self, request, *args, **kwargs):
        self.escala = get_object_or_404(Escala, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"escala": self.escala}

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"escala": self.escala}

    def form_valid(self, form):
        form.instance.escala = self.escala
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("escalas:grade", args=[self.escala.pk])


class DisponiveisView(PerfilRequiredMixin, View):
    """Fragmento HTMX: quem pode assumir este turno."""

    perfis_permitidos = QUEM_MONTA

    def get(self, request, pk):
        turno = get_object_or_404(Turno, pk=pk)
        return render(
            request,
            "escalas/partials/_lista_disponiveis.html",
            {"turno": turno, "voluntarios": voluntarios_disponiveis(turno)},
        )


class AlocarView(PerfilRequiredMixin, View):
    """Aloca um voluntario no turno e devolve a celula atualizada."""

    perfis_permitidos = QUEM_MONTA

    def post(self, request, pk):
        turno = get_object_or_404(Turno, pk=pk)

        voluntario = get_object_or_404(
            Voluntario, pk=request.POST.get("voluntario"), status=StatusVoluntario.ATIVO
        )
        alocacao = Alocacao(turno=turno, voluntario=voluntario)

        try:
            alocacao.full_clean()
        except ValidationError as erro:
            mensagens = [m for lista in erro.message_dict.values() for m in lista]
            # Renderiza por template: a mensagem contem o nome do voluntario,
            # que e dado de entrada. Montar o HTML com f-string entregaria XSS
            # refletido a quem conseguisse cadastrar um nome com marcacao.
            return render(
                request,
                "escalas/partials/_erro_alocacao.html",
                {"mensagens": mensagens},
                status=200,
            )

        alocacao.save()
        return render(
            request, "escalas/partials/_celula_turno.html",
            {"turno": turno, "pode_montar": True},
        )


class DesalocarView(PerfilRequiredMixin, View):
    perfis_permitidos = QUEM_MONTA

    def post(self, request, pk):
        alocacao = get_object_or_404(Alocacao, pk=pk)
        turno = alocacao.turno
        alocacao.delete()
        return render(
            request, "escalas/partials/_celula_turno.html",
            {"turno": turno, "pode_montar": True},
        )


class PublicarView(PerfilRequiredMixin, View):
    perfis_permitidos = QUEM_MONTA

    def post(self, request, pk):
        escala = get_object_or_404(Escala, pk=pk)

        if not escala.turnos.exists():
            messages.error(
                request, "Adicione pelo menos um turno antes de publicar a escala."
            )
        else:
            escala.status = StatusEscala.PUBLICADA
            escala.save(update_fields=["status"])
            descobertos = escala.turnos_descobertos
            if descobertos:
                messages.warning(
                    request,
                    f"Escala publicada com {descobertos} turno(s) ainda sem "
                    "voluntário. Você pode continuar preenchendo.",
                )
            else:
                messages.success(request, "Escala publicada.")

        return redirect("escalas:grade", pk=escala.pk)
```

Publicar com turno descoberto é permitido, mas avisa. Bloquear obrigaria o
coordenador a inventar uma alocação só para liberar a publicação — e a escala
precisa circular mesmo incompleta.

- [ ] **Step 6: Escrever `escalas/urls.py` e ligar ao projeto**

```python
from django.urls import path

from escalas import views

app_name = "escalas"

urlpatterns = [
    path("escalas/", views.EscalaListView.as_view(), name="lista"),
    path("escalas/nova/", views.EscalaCreateView.as_view(), name="nova"),
    path("escalas/<int:pk>/", views.EscalaGradeView.as_view(), name="grade"),
    path("escalas/<int:pk>/turno/", views.TurnoCreateView.as_view(), name="turno_novo"),
    path("escalas/<int:pk>/publicar/", views.PublicarView.as_view(), name="publicar"),
    path("turnos/<int:pk>/disponiveis/", views.DisponiveisView.as_view(), name="disponiveis"),
    path("turnos/<int:pk>/alocar/", views.AlocarView.as_view(), name="alocar"),
    path("alocacoes/<int:pk>/remover/", views.DesalocarView.as_view(), name="desalocar"),
]
```

Em `comviver/urls.py`:
```python
    path("", include("escalas.urls")),
```

- [ ] **Step 7: Escrever os templates da grade**

`templates/escalas/partials/_celula_turno.html`:
```html
<div id="turno-{{ turno.pk }}" class="p-2 h-100
     {% if turno.esta_descoberto %}bg-warning-subtle{% endif %}">
  <div class="small text-muted mb-1">{{ turno.atividade.nome }}</div>

  {% for alocacao in turno.alocacoes.all %}
    <div class="d-flex justify-content-between align-items-center gap-1 mb-1">
      <span class="small">{{ alocacao.voluntario.nome }}</span>
      {% if pode_montar %}
        <button class="btn btn-sm btn-link text-danger p-0 lh-1"
                hx-post="{% url 'escalas:desalocar' alocacao.pk %}"
                hx-target="#turno-{{ turno.pk }}"
                hx-swap="outerHTML"
                hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'
                title="Remover">&times;</button>
      {% endif %}
    </div>
  {% endfor %}

  {% if turno.esta_descoberto %}
    <div class="small text-warning-emphasis mb-1">
      <i class="bi bi-exclamation-triangle"></i>
      {{ turno.vagas_ocupadas }}/{{ turno.vagas }}
    </div>
    {% if pode_montar %}
      <button class="btn btn-sm btn-outline-primary w-100 py-0"
              hx-get="{% url 'escalas:disponiveis' turno.pk %}"
              hx-target="#painel-alocacao"
              hx-swap="innerHTML">+ vaga</button>
    {% endif %}
  {% endif %}
</div>
```

`templates/escalas/partials/_erro_alocacao.html`:
```html
<div class="alert alert-warning py-1 px-2 small mb-0">
  {% for mensagem in mensagens %}{{ mensagem }} {% endfor %}
</div>
```

O template existe para que o escape automático do Django trate as mensagens. A
mensagem de conflito inclui o nome do voluntário, que é dado digitado por um
usuário.

`templates/escalas/partials/_lista_disponiveis.html`:
```html
<div class="card">
  <div class="card-header py-2">
    <strong class="small">{{ turno }}</strong>
    <div class="text-muted small">
      Voluntários disponíveis neste dia e turno
    </div>
  </div>
  <div class="list-group list-group-flush" style="max-height: 20rem; overflow-y: auto;">
    {% for voluntario in voluntarios %}
      <button class="list-group-item list-group-item-action py-2"
              hx-post="{% url 'escalas:alocar' turno.pk %}"
              hx-vals='{"voluntario": "{{ voluntario.pk }}"}'
              hx-target="#turno-{{ turno.pk }}"
              hx-swap="outerHTML"
              hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
        <div class="small fw-semibold">{{ voluntario.nome }}</div>
        <div class="text-muted" style="font-size: .75rem;">
          {{ voluntario.resumo_disponibilidade }}
        </div>
      </button>
    {% empty %}
      <div class="list-group-item text-muted small">
        Nenhum voluntário disponível para este dia e turno.
        Verifique a disponibilidade declarada nos cadastros.
      </div>
    {% endfor %}
  </div>
</div>
```

`templates/escalas/escala_grade.html`:
```html
{% extends "base.html" %}
{% block titulo %}{{ escala.titulo }}{% endblock %}
{% block cabecalho %}{{ escala.titulo }}{% endblock %}

{% block acoes %}
  {% if pode_montar %}
    <a href="{% url 'escalas:turno_novo' escala.pk %}" class="btn btn-outline-secondary">
      + Turno
    </a>
    {% if not escala.esta_publicada %}
      <form method="post" action="{% url 'escalas:publicar' escala.pk %}" class="d-inline">
        {% csrf_token %}
        <button type="submit" class="btn btn-primary">Publicar</button>
      </form>
    {% endif %}
  {% endif %}
{% endblock %}

{% block conteudo %}
  <div class="d-flex flex-wrap gap-3 align-items-center mb-3">
    <span class="badge {% if escala.esta_publicada %}text-bg-success
          {% else %}text-bg-secondary{% endif %}">
      {{ escala.get_status_display }}
    </span>
    <span class="text-muted small">
      {{ escala.data_inicio|date:"d/m/Y" }} a {{ escala.data_fim|date:"d/m/Y" }}
    </span>
    {% if escala.turnos_descobertos %}
      <span class="text-warning-emphasis small">
        <i class="bi bi-exclamation-triangle"></i>
        {{ escala.turnos_descobertos }} turno(s) sem voluntário
      </span>
    {% else %}
      <span class="text-success small"><i class="bi bi-check-circle"></i> Todos os turnos cobertos</span>
    {% endif %}
  </div>

  <div class="row g-3">
    <div class="col-12 col-xl-9">
      <div class="table-responsive">
        <table class="table table-bordered align-top mb-0">
          <thead>
            <tr>
              <th style="width: 7rem;"></th>
              {% for dia in dias %}
                <th class="text-center small">
                  {{ dia|date:"D" }}<br>
                  <span class="text-muted">{{ dia|date:"d/m" }}</span>
                </th>
              {% endfor %}
            </tr>
          </thead>
          <tbody>
            {% for linha in linhas %}
              <tr>
                <th class="small align-middle">
                  {{ linha.hora_inicio|time:"H:i" }}<br>
                  <span class="text-muted">{{ linha.hora_fim|time:"H:i" }}</span>
                </th>
                {% for turno in linha.celulas %}
                  <td class="p-0">
                    {% if turno %}
                      {% include "escalas/partials/_celula_turno.html" %}
                    {% endif %}
                  </td>
                {% endfor %}
              </tr>
            {% empty %}
              <tr>
                <td colspan="{{ dias|length|add:1 }}" class="text-muted p-3">
                  Nenhum turno nesta escala.
                  {% if pode_montar %}
                    <a href="{% url 'escalas:turno_novo' escala.pk %}">Adicionar o primeiro</a>.
                  {% endif %}
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <div class="col-12 col-xl-3">
      <div id="painel-alocacao">
        {% if pode_montar %}
          <div class="card">
            <div class="card-body text-muted small">
              Clique em <strong>+ vaga</strong> num turno para ver quem está
              disponível naquele dia e período.
            </div>
          </div>
        {% endif %}
      </div>
    </div>
  </div>
{% endblock %}
```

`templates/escalas/escala_list.html`:
```html
{% extends "base.html" %}
{% block titulo %}Escalas{% endblock %}
{% block cabecalho %}Escalas{% endblock %}

{% block acoes %}
  {% if user.perfil == 'ADMIN' or user.perfil == 'OPERACIONAL' %}
    <a href="{% url 'escalas:nova' %}" class="btn btn-primary">Nova escala</a>
  {% endif %}
{% endblock %}

{% block conteudo %}
  <div class="row g-3">
    {% for escala in escalas %}
      <div class="col-12 col-md-6 col-xl-4">
        <a href="{% url 'escalas:grade' escala.pk %}"
           class="card h-100 text-decoration-none text-dark">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start mb-1">
              <h2 class="h6 mb-0">{{ escala.titulo }}</h2>
              <span class="badge {% if escala.esta_publicada %}text-bg-success
                    {% else %}text-bg-secondary{% endif %}">
                {{ escala.get_status_display }}
              </span>
            </div>
            <p class="text-muted small mb-2">
              {{ escala.data_inicio|date:"d/m/Y" }} a {{ escala.data_fim|date:"d/m/Y" }}
            </p>
            <div class="small">
              {{ escala.total_turnos }} turno(s)
              {% if escala.turnos_descobertos %}
                · <span class="text-warning-emphasis">
                    {{ escala.turnos_descobertos }} sem voluntário
                  </span>
              {% endif %}
            </div>
          </div>
        </a>
      </div>
    {% empty %}
      <div class="col-12"><p class="text-muted">Nenhuma escala cadastrada.</p></div>
    {% endfor %}
  </div>
{% endblock %}
```

`templates/escalas/escala_form.html` e `turno_form.html` seguem o esqueleto de
formulário já usado nas fases anteriores, com cancelamento para
`{% url 'escalas:lista' %}` e `{% url 'escalas:grade' escala.pk %}`,
respectivamente.

- [ ] **Step 8: Acrescentar ao menu e ao painel**

Em `core/context_processors.py`:
```python
    itens.append(
        {"rotulo": "Escalas", "url": reverse("escalas:lista"), "icone": "calendar-week"}
    )
```

Em `core/views.py`, `_montar_cartoes`:
```python
        from escalas.services import turnos_descobertos_proximos

        descobertos = turnos_descobertos_proximos(dias=7).count()
        cartoes.append(
            {
                "titulo": "Turnos descobertos",
                "valor": descobertos,
                "descricao": "nos próximos 7 dias",
                "icone": "exclamation-triangle" if descobertos else "calendar-check",
            }
        )
```

- [ ] **Step 9: Rodar os testes**

```bash
pytest escalas/tests/ -v
```
Esperado: todos passando.

- [ ] **Step 10: Commit**

```bash
git add escalas templates/escalas core comviver/urls.py
git commit -m "feat(escalas): adiciona grade semanal com alocacao filtrada por disponibilidade"
```

---

## Task 4: Registro de presença, dados de demonstração e fechamento

**Files:**
- Modify: `escalas/views.py`, `escalas/urls.py`
- Create: `templates/escalas/presenca.html`
- Create: `escalas/tests/test_presenca.py`
- Create: `escalas/admin.py`, `voluntarios/admin.py`
- Modify: `acolhidos/management/commands/seed_demo.py`, `README.md`

**Interfaces:**
- Consumes: `escalas.models.Alocacao`, `StatusAlocacao`
- Produces: rota `escalas:presenca`; `seed_demo` populando voluntários, atividades e uma escala da semana

- [ ] **Step 1: Escrever os testes que falham**

`escalas/tests/test_presenca.py`:
```python
from datetime import date

import pytest
from django.urls import reverse

from escalas.factories import AlocacaoFactory, EscalaFactory, TurnoFactory
from escalas.models import StatusAlocacao

pytestmark = pytest.mark.django_db


class TestPresenca:
    def test_tecnico_nao_registra_presenca(self, client, usuario_tecnico):
        escala = EscalaFactory()
        client.force_login(usuario_tecnico)
        assert client.get(reverse("escalas:presenca", args=[escala.pk])).status_code == 403

    def test_operacional_abre_a_tela(self, client, usuario_operacional):
        escala = EscalaFactory()
        TurnoFactory(escala=escala, data=date.today())
        client.force_login(usuario_operacional)
        assert client.get(reverse("escalas:presenca", args=[escala.pk])).status_code == 200

    def test_marcar_compareceu(self, client, usuario_operacional):
        escala = EscalaFactory()
        alocacao = AlocacaoFactory(turno=TurnoFactory(escala=escala, data=date.today()))
        client.force_login(usuario_operacional)
        client.post(
            reverse("escalas:presenca", args=[escala.pk]),
            {f"status_{alocacao.pk}": StatusAlocacao.CONFIRMADO},
        )
        alocacao.refresh_from_db()
        assert alocacao.status == StatusAlocacao.CONFIRMADO

    def test_marcar_falta(self, client, usuario_operacional):
        escala = EscalaFactory()
        alocacao = AlocacaoFactory(turno=TurnoFactory(escala=escala, data=date.today()))
        client.force_login(usuario_operacional)
        client.post(
            reverse("escalas:presenca", args=[escala.pk]),
            {f"status_{alocacao.pk}": StatusAlocacao.FALTOU},
        )
        alocacao.refresh_from_db()
        assert alocacao.status == StatusAlocacao.FALTOU

    def test_alocacao_nao_enviada_permanece_como_estava(self, client, usuario_operacional):
        """Enviar o formulario de um dia nao pode zerar o registro de outro."""
        escala = EscalaFactory()
        turno = TurnoFactory(escala=escala, data=date.today())
        marcada = AlocacaoFactory(turno=turno, status=StatusAlocacao.CONFIRMADO)
        outra = AlocacaoFactory(turno=turno)
        client.force_login(usuario_operacional)
        client.post(
            reverse("escalas:presenca", args=[escala.pk]),
            {f"status_{outra.pk}": StatusAlocacao.FALTOU},
        )
        marcada.refresh_from_db()
        assert marcada.status == StatusAlocacao.CONFIRMADO

    def test_presenca_de_outra_escala_e_ignorada(self, client, usuario_operacional):
        """Id forjado de outra escala nao pode ser alterado por esta tela."""
        escala = EscalaFactory()
        TurnoFactory(escala=escala, data=date.today())
        de_fora = AlocacaoFactory()
        client.force_login(usuario_operacional)
        client.post(
            reverse("escalas:presenca", args=[escala.pk]),
            {f"status_{de_fora.pk}": StatusAlocacao.FALTOU},
        )
        de_fora.refresh_from_db()
        assert de_fora.status == StatusAlocacao.PREVISTO
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest escalas/tests/test_presenca.py -v
```
Esperado: `NoReverseMatch` para `escalas:presenca`.

- [ ] **Step 3: Escrever a view de presença**

Em `escalas/views.py`:
```python
from escalas.models import StatusAlocacao


class PresencaView(PerfilRequiredMixin, View):
    """Marcacao de presenca por escala.

    Uma tela por escala, agrupada por dia. Atualiza apenas as alocacoes
    enviadas: marcar o sabado nao pode zerar o registro da sexta.
    """

    perfis_permitidos = QUEM_MONTA
    template_name = "escalas/presenca.html"

    def get(self, request, pk):
        escala = get_object_or_404(Escala, pk=pk)
        return render(request, self.template_name, self._contexto(escala))

    def post(self, request, pk):
        escala = get_object_or_404(Escala, pk=pk)

        # Restringe as alocacoes desta escala: id forjado de outra nao passa.
        alocacoes = {
            str(a.pk): a
            for a in Alocacao.objects.filter(turno__escala=escala)
        }
        validos = {escolha.value for escolha in StatusAlocacao}
        atualizadas = 0

        for chave, valor in request.POST.items():
            if not chave.startswith("status_"):
                continue
            identificador = chave.removeprefix("status_")
            alocacao = alocacoes.get(identificador)
            if alocacao and valor in validos and alocacao.status != valor:
                alocacao.status = valor
                alocacao.save(update_fields=["status"])
                atualizadas += 1

        messages.success(request, f"{atualizadas} registro(s) de presença atualizado(s).")
        return redirect("escalas:presenca", pk=escala.pk)

    def _contexto(self, escala):
        turnos = (
            escala.turnos.select_related("atividade")
            .prefetch_related("alocacoes__voluntario")
            .order_by("data", "hora_inicio")
        )
        por_dia: dict = {}
        for turno in turnos:
            por_dia.setdefault(turno.data, []).append(turno)
        return {
            "escala": escala,
            "dias": sorted(por_dia.items()),
            "status_opcoes": StatusAlocacao.choices,
        }
```

Em `escalas/urls.py`:
```python
    path("escalas/<int:pk>/presenca/", views.PresencaView.as_view(), name="presenca"),
```

- [ ] **Step 4: Escrever `templates/escalas/presenca.html`**

```html
{% extends "base.html" %}
{% block titulo %}Presença — {{ escala.titulo }}{% endblock %}
{% block cabecalho %}Presença — {{ escala.titulo }}{% endblock %}

{% block acoes %}
  <a href="{% url 'escalas:grade' escala.pk %}" class="btn btn-outline-secondary">
    Ver grade
  </a>
{% endblock %}

{% block conteudo %}
  <form method="post">
    {% csrf_token %}

    {% for dia, turnos in dias %}
      <h2 class="h6 mt-4 mb-2">{{ dia|date:"l, d/m/Y"|capfirst }}</h2>
      <div class="table-responsive">
        <table class="table table-sm align-middle">
          <thead>
            <tr><th>Horário</th><th>Atividade</th><th>Voluntário</th><th style="width:22rem;">Situação</th></tr>
          </thead>
          <tbody>
            {% for turno in turnos %}
              {% for alocacao in turno.alocacoes.all %}
                <tr>
                  <td class="small">
                    {{ turno.hora_inicio|time:"H:i" }}–{{ turno.hora_fim|time:"H:i" }}
                  </td>
                  <td class="small">{{ turno.atividade.nome }}</td>
                  <td>{{ alocacao.voluntario.nome }}</td>
                  <td>
                    <div class="btn-group btn-group-sm" role="group">
                      {% for valor, rotulo in status_opcoes %}
                        <input type="radio" class="btn-check"
                               name="status_{{ alocacao.pk }}" value="{{ valor }}"
                               id="s{{ alocacao.pk }}-{{ valor }}"
                               {% if alocacao.status == valor %}checked{% endif %}>
                        <label class="btn btn-outline-secondary"
                               for="s{{ alocacao.pk }}-{{ valor }}">{{ rotulo }}</label>
                      {% endfor %}
                    </div>
                  </td>
                </tr>
              {% empty %}
                <tr class="text-muted">
                  <td class="small">
                    {{ turno.hora_inicio|time:"H:i" }}–{{ turno.hora_fim|time:"H:i" }}
                  </td>
                  <td class="small">{{ turno.atividade.nome }}</td>
                  <td colspan="2" class="small">Nenhum voluntário alocado.</td>
                </tr>
              {% endfor %}
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% empty %}
      <p class="text-muted">Nenhum turno nesta escala.</p>
    {% endfor %}

    {% if dias %}
      <button type="submit" class="btn btn-primary mt-3">Salvar presenças</button>
    {% endif %}
  </form>
{% endblock %}
```

Acrescentar o link na grade, no bloco `acoes` de `escala_grade.html`:
```html
    <a href="{% url 'escalas:presenca' escala.pk %}" class="btn btn-outline-secondary">
      Presença
    </a>
```

- [ ] **Step 5: Registrar no admin**

`voluntarios/admin.py`:
```python
from django.contrib import admin

from voluntarios.models import Disponibilidade, DocumentoVoluntario, Funcao, Voluntario


class DisponibilidadeInline(admin.TabularInline):
    model = Disponibilidade
    extra = 0


@admin.register(Voluntario)
class VoluntarioAdmin(admin.ModelAdmin):
    list_display = ["nome", "telefone", "status", "data_cadastro"]
    list_filter = ["status", "funcoes"]
    search_fields = ["nome", "email", "telefone"]
    inlines = [DisponibilidadeInline]


admin.site.register([Funcao, DocumentoVoluntario])
```

`escalas/admin.py`:
```python
from django.contrib import admin

from escalas.models import Alocacao, Atividade, Escala, Turno


class TurnoInline(admin.TabularInline):
    model = Turno
    extra = 0


@admin.register(Escala)
class EscalaAdmin(admin.ModelAdmin):
    list_display = ["titulo", "data_inicio", "data_fim", "status"]
    list_filter = ["status"]
    inlines = [TurnoInline]


@admin.register(Alocacao)
class AlocacaoAdmin(admin.ModelAdmin):
    list_display = ["voluntario", "turno", "status"]
    list_filter = ["status"]


admin.site.register(Atividade)
```

- [ ] **Step 6: Acrescentar voluntários e escala ao `seed_demo`**

Em `acolhidos/management/commands/seed_demo.py`, ao fim de `handle`:

```python
        from datetime import time

        from escalas.models import Alocacao, Atividade, Escala, StatusEscala, Turno
        from voluntarios.models import (
            DiaSemana,
            Disponibilidade,
            Funcao,
            Turno as TurnoDisponibilidade,
            Voluntario,
        )

        if opcoes["limpar"]:
            Escala.todos.all().delete()
            Atividade.todos.all().delete()
            Voluntario.todos.all().delete()
            Funcao.todos.all().delete()

        funcoes = {
            nome: Funcao.objects.create(nome=nome)
            for nome in ["Cozinha", "Reforço escolar", "Recreação", "Manutenção"]
        }

        atividades = {
            nome: Atividade.objects.create(nome=nome)
            for nome in ["Acompanhamento escolar", "Recreação", "Apoio na cozinha"]
        }

        perfis_voluntarios = [
            ("Ana Souza", ["Cozinha"], [(0, "MANHA"), (2, "MANHA"), (4, "MANHA")]),
            ("Carlos Dias", ["Reforço escolar"], [(0, "MANHA"), (1, "TARDE")]),
            ("Rita Nogueira", ["Recreação"], [(0, "TARDE"), (2, "TARDE"), (3, "TARDE")]),
            ("Paulo Freitas", ["Manutenção"], [(3, "MANHA")]),
            ("Lucia Amaral", ["Cozinha", "Recreação"], [(1, "MANHA"), (4, "TARDE")]),
        ]

        voluntarios = {}
        for nome, nomes_funcao, disponibilidades in perfis_voluntarios:
            voluntario = Voluntario.objects.create(
                nome=nome,
                telefone=f"3598888{1000 + len(voluntarios)}",
                email=f"{nome.split()[0].lower()}@exemplo.org",
                cidade="Itajubá", uf="MG",
            )
            voluntario.funcoes.set([funcoes[f] for f in nomes_funcao])
            Disponibilidade.objects.bulk_create(
                [
                    Disponibilidade(voluntario=voluntario, dia_semana=dia, turno=turno)
                    for dia, turno in disponibilidades
                ]
            )
            voluntarios[nome] = voluntario

        # Escala da semana corrente, comecando na segunda-feira.
        hoje = date.today()
        segunda = hoje - timedelta(days=hoje.weekday())
        escala = Escala.objects.create(
            titulo=f"Semana {segunda:%d/%m} a {segunda + timedelta(days=6):%d/%m}",
            data_inicio=segunda,
            data_fim=segunda + timedelta(days=6),
            status=StatusEscala.PUBLICADA,
        )

        planejamento = [
            (0, time(8, 0), time(12, 0), "Apoio na cozinha", 2, ["Ana Souza", "Carlos Dias"]),
            (0, time(13, 0), time(17, 0), "Recreação", 1, ["Rita Nogueira"]),
            (1, time(8, 0), time(12, 0), "Apoio na cozinha", 2, ["Lucia Amaral"]),
            (1, time(13, 0), time(17, 0), "Acompanhamento escolar", 1, []),  # descoberto
            (2, time(8, 0), time(12, 0), "Acompanhamento escolar", 2, ["Ana Souza"]),
            (2, time(13, 0), time(17, 0), "Recreação", 1, ["Rita Nogueira"]),
            (3, time(8, 0), time(12, 0), "Apoio na cozinha", 1, ["Paulo Freitas"]),
            (4, time(8, 0), time(12, 0), "Acompanhamento escolar", 2, ["Ana Souza"]),
        ]

        for deslocamento, inicio, fim, atividade, vagas, nomes in planejamento:
            turno = Turno.objects.create(
                escala=escala,
                data=segunda + timedelta(days=deslocamento),
                hora_inicio=inicio,
                hora_fim=fim,
                atividade=atividades[atividade],
                vagas=vagas,
            )
            Alocacao.objects.bulk_create(
                [Alocacao(turno=turno, voluntario=voluntarios[n]) for n in nomes]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(voluntarios)} voluntários e 1 escala da semana criados, "
                "com turnos descobertos propositais."
            )
        )
```

Os turnos descobertos são propositais: a tela precisa ser demonstrada
mostrando o problema que ela resolve.

- [ ] **Step 7: Rodar a suíte e o lint**

```bash
pytest -v
ruff check .
ruff format --check .
```

- [ ] **Step 8: Verificação manual**

```bash
python manage.py migrate
python manage.py seed_demo --limpar
python manage.py runserver
```

1. Entrar como **Operacional** → Escalas → abrir a escala da semana
2. Confirmar que os turnos descobertos aparecem destacados em amarelo
3. Clicar em "+ vaga" num turno de segunda de manhã → confirmar que a lista sugere só quem declarou segunda de manhã
4. Alocar alguém → confirmar que a célula atualiza sem recarregar a página
5. Tentar alocar a mesma pessoa em outro turno sobreposto → confirmar a mensagem de conflito com o horário do outro turno
6. Remover uma alocação pelo × → confirmar que a célula volta a "+ vaga"
7. Presença → marcar compareceu e faltou, salvar, recarregar e confirmar que ficou salvo
8. Abrir o cadastro de um voluntário → confirmar que a participação aparece no histórico
9. Entrar como **Técnico** → confirmar que a grade abre, mas "+ vaga" e "Publicar" não aparecem
10. Como Técnico, tentar `POST` em `/turnos/<id>/alocar/` → deve retornar 403

O passo 5 é o que verifica a regra central da fase; o passo 10, a camada de view.

- [ ] **Step 9: Atualizar o README**

```markdown
### Módulos de voluntários e escalas

- **Voluntários** — cadastro com disponibilidade declarada por dia e turno
- **Funções** — tabela de apoio, mantida pela coordenação
- **Escalas** — grade semanal, com turnos descobertos destacados
- **Presença** — registro de comparecimento por escala

Ao alocar, o sistema sugere apenas voluntários que declararam aquele dia e
período e que não têm conflito de horário. A tentativa de alocar alguém em dois
turnos sobrepostos é bloqueada, mesmo entre escalas diferentes.
```

- [ ] **Step 10: Commit**

```bash
git add escalas voluntarios templates/escalas acolhidos README.md
git commit -m "feat(escalas): adiciona registro de presenca e dados de demonstracao"
```

---

## Verificação de conclusão da Fase 4

- [ ] `pytest` — suíte inteira passando
- [ ] `ruff check .` — sem apontamentos
- [ ] Roteiro manual da Task 4, com atenção aos passos 5 e 10
- [ ] Painel mostra o cartão de turnos descobertos

**O que a Fase 5 encontra pronto:**
- `escalas.services.turnos_descobertos_proximos`, `voluntarios_disponiveis`, `grade_da_escala`
- `voluntarios.models.Voluntario.resumo_disponibilidade`
- `escalas.models.StatusAlocacao` — base do relatório de frequência
- `seed_demo` populando os cinco módulos

**Pendências desta fase, com destino:**

| Item | Fase |
|---|---|
| Relatório de voluntários ativos | 5 |
| Relatório de frequência (previsto × confirmado × faltas) | 5 |
| Impressão da escala em PDF para afixar no mural | 5 |
| Busca global incluindo voluntários | 5 |
| Upload de documentos do voluntário pela interface | 5 |
