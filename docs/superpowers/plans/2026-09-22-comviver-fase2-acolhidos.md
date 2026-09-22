# ComViver — Fase 2: Acolhidos — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o cadastro completo de crianças e adolescentes acolhidos — identificação, ficha de acolhimento, saúde, escolaridade, responsáveis e desligamento — com o recorte de sigilo exigido pelo ECA aplicado em todas as camadas.

**Architecture:** App `acolhidos` consumindo as bases da Fase 1. Esta fase também cria as classes base de CRUD em `core`, que as Fases 3 e 4 reutilizam em vez de reescrever. O acesso a dado sigiloso é controlado em três camadas e registrado em log de leitura.

**Tech Stack:** Django 5.x, Bootstrap 5 (local), `django-formtools` para o assistente de acolhimento, `django-simple-history` para auditoria, Pillow para imagem.

**Spec:** `docs/superpowers/specs/2026-09-22-comviver-design.md`

**Depende de:** Fase 1 concluída e verificada.

## Global Constraints

- Python 3.12; Django 5.x (`Django>=5.1,<6.0`).
- PostgreSQL exclusivamente, inclusive em teste.
- `.env` nunca versionado.
- Interface, mensagens e validações em português do Brasil.
- Exclusão sempre lógica (`deleted_at`), nunca `DELETE` físico.
- Controle de acesso em três camadas: view (`PerfilRequiredMixin`), formulário (campo não montado) e template (não renderizado).
- `ruff` limpo antes de cada commit.
- Teste escrito antes da implementação, falhando primeiro pelo motivo certo.

## Restrição central desta fase

O art. 143 do ECA veda divulgação de informação que identifique criança ou
adolescente acolhido. Traduzido para este sistema:

- O perfil **Operacional** vê apenas nome, foto, status e o que precisa para o
  cuidado diário: medicação em vigor e quem está autorizado a retirar.
- Motivo do acolhimento, número do processo, vara, medida protetiva, histórico
  familiar e diagnóstico de saúde são exclusivos de **Técnico** e **Admin**.
- Toda leitura de ficha é registrada em `LogAcessoFicha`, com autor e momento.

Esta restrição não é um requisito entre outros. É o critério que decide se o
sistema pode ser usado.

## O que a Fase 1 deixou pronto

- `core.models.TimeStampedModel`, `SoftDeleteModel`, `Endereco`
- `core.mixins.PerfilRequiredMixin`
- `accounts.models.Usuario`, `Perfil`, `Usuario.pode_ver_ficha_completa()`
- `accounts.factories.UsuarioFactory`; fixtures `usuario_admin`, `usuario_tecnico`, `usuario_operacional`
- `templates/base.html` com blocos `titulo`, `cabecalho`, `acoes`, `conteudo`
- `core.context_processors.menu` — acrescentar itens aqui
- `core.views.PainelView._montar_cartoes` — acrescentar cartões aqui

---

## Estrutura de arquivos ao fim da Fase 2

```
core/
├── views.py                        # + BaseListView, BaseCreateView, BaseUpdateView
├── forms.py                        # + FormularioPorPerfilMixin  (novo)
├── storage.py                      # + servir media com permissao     (novo)
└── tests/
    ├── test_views_base.py                                             (novo)
    └── test_media_protegida.py                                        (novo)

acolhidos/
├── models.py                       # Acolhido, Responsavel, VinculoFamiliar,
│                                   # FichaAcolhimento, DadosSaude, Medicacao,
│                                   # Escolaridade, DocumentoAcolhido, Consentimento
├── forms.py                        # formularios do assistente e dos vinculos
├── views.py                        # lista, detalhe, assistente, desligamento
├── urls.py
├── admin.py
├── factories.py
├── seeds.py                        # dados ficticios coerentes
├── management/commands/seed_demo.py
├── migrations/
└── tests/
    ├── test_models.py
    ├── test_permissoes.py          # a matriz da spec 5.1, celula a celula
    ├── test_assistente.py
    ├── test_vinculos.py
    ├── test_desligamento.py
    └── test_log_acesso.py

accounts/
├── models.py                       # + LogAcessoFicha
└── tests/test_log_acesso_model.py

templates/acolhidos/
├── acolhido_list.html
├── acolhido_detail.html
├── acolhido_wizard.html
├── acolhido_desligar.html
├── responsavel_form.html
└── partials/
    ├── _ficha_sigilosa.html        # so renderiza para Tecnico e Admin
    └── _cuidado_diario.html        # o que o Operacional ve
```

---

## Task 1: Classes base de CRUD no `core`

Escritas uma vez aqui, consumidas por acolhidos, doações, voluntários e escalas.
Sem isto, as Fases 3 e 4 repetiriam o mesmo código quatro vezes.

**Files:**
- Modify: `core/views.py`
- Create: `core/forms.py`
- Create: `core/tests/test_views_base.py`
- Modify: `tests/testapp/models.py` (model concreto para exercitar as bases)

**Interfaces:**
- Consumes: `core.mixins.PerfilRequiredMixin` (Fase 1)
- Produces:
  - `core.views.BaseListView` — atributos `campos_busca: list[str]`, `paginate_by = 25`; filtra por `?q=`
  - `core.views.BaseCreateView` e `core.views.BaseUpdateView` — atributo `mensagem_sucesso: str`, injetam `criado_por`
  - `core.forms.FormularioPorPerfilMixin` — atributo `campos_restritos: dict[str, list[str]]`, remove do formulário os campos que o perfil do usuário não pode editar

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/testapp/models.py`:
```python
class ModeloPesquisavel(SoftDeleteModel):
    """Model concreto para exercitar as views base do core."""

    nome = models.CharField(max_length=80)
    apelido = models.CharField(max_length=80, blank=True)
    segredo = models.CharField(max_length=80, blank=True)
    criado_por = models.ForeignKey(
        "accounts.Usuario", null=True, blank=True, on_delete=models.SET_NULL
    )

    def get_absolute_url(self):
        return "/testapp/pesquisavel/"
```

`core/tests/test_views_base.py`:
```python
import pytest
from django.urls import path

from accounts.models import Perfil
from core.forms import FormularioPorPerfilMixin
from core.views import BaseCreateView, BaseListView
from tests.testapp.models import ModeloPesquisavel


class ListaTeste(BaseListView):
    model = ModeloPesquisavel
    template_name = "testapp/lista.html"
    campos_busca = ["nome", "apelido"]
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]


class FormularioTeste(FormularioPorPerfilMixin):
    campos_restritos = {Perfil.OPERACIONAL: ["segredo"]}

    class Meta:
        model = ModeloPesquisavel
        fields = ["nome", "apelido", "segredo"]


class CriarTeste(BaseCreateView):
    model = ModeloPesquisavel
    form_class = FormularioTeste
    template_name = "testapp/form.html"
    mensagem_sucesso = "Registro salvo."
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]


urlpatterns = [
    path("lista/", ListaTeste.as_view(), name="lista"),
    path("criar/", CriarTeste.as_view(), name="criar"),
]

pytestmark = [pytest.mark.django_db, pytest.mark.urls(__name__)]


class TestBaseListView:
    def test_lista_sem_busca_traz_tudo(self, client, usuario_admin):
        ModeloPesquisavel.objects.create(nome="Ana")
        ModeloPesquisavel.objects.create(nome="Bruno")
        client.force_login(usuario_admin)
        assert len(client.get("/lista/").context["object_list"]) == 2

    def test_busca_filtra_por_qualquer_campo_declarado(self, client, usuario_admin):
        ModeloPesquisavel.objects.create(nome="Ana", apelido="Aninha")
        ModeloPesquisavel.objects.create(nome="Bruno", apelido="Bru")
        client.force_login(usuario_admin)
        resultado = client.get("/lista/?q=aninha").context["object_list"]
        assert [o.nome for o in resultado] == ["Ana"]

    def test_busca_ignora_maiusculas_e_minusculas(self, client, usuario_admin):
        ModeloPesquisavel.objects.create(nome="Ana")
        client.force_login(usuario_admin)
        assert len(client.get("/lista/?q=ANA").context["object_list"]) == 1

    def test_excluido_logicamente_nao_aparece(self, client, usuario_admin):
        obj = ModeloPesquisavel.objects.create(nome="Ana")
        obj.delete()
        client.force_login(usuario_admin)
        assert len(client.get("/lista/").context["object_list"]) == 0


class TestBaseCreateView:
    def test_registra_quem_criou(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        client.post("/criar/", {"nome": "Ana", "apelido": "", "segredo": ""})
        assert ModeloPesquisavel.objects.get(nome="Ana").criado_por == usuario_tecnico

    def test_mostra_mensagem_de_sucesso(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        resposta = client.post(
            "/criar/", {"nome": "Ana", "apelido": "", "segredo": ""}, follow=True
        )
        assert "Registro salvo." in [m.message for m in resposta.context["messages"]]


class TestFormularioPorPerfilMixin:
    def test_operacional_nao_recebe_o_campo_restrito(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        form = client.get("/criar/").context["form"]
        assert "segredo" not in form.fields

    def test_tecnico_recebe_o_campo_restrito(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        form = client.get("/criar/").context["form"]
        assert "segredo" in form.fields

    def test_post_forjado_nao_grava_campo_restrito(self, client, usuario_operacional):
        """Camada 2 da protecao: o campo nao existe no formulario, entao
        enviar o valor direto no POST nao tem efeito."""
        client.force_login(usuario_operacional)
        client.post("/criar/", {"nome": "Ana", "apelido": "", "segredo": "vazou"})
        assert ModeloPesquisavel.objects.get(nome="Ana").segredo == ""
```

O último teste é o que prova a camada 2. Sem ele, a proteção seria apenas visual.

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_views_base.py -v
```
Esperado: `ImportError: cannot import name 'BaseListView' from 'core.views'`.

- [ ] **Step 3: Escrever `core/forms.py`**

```python
from django import forms


class FormularioPorPerfilMixin(forms.ModelForm):
    """Remove do formulario os campos vedados ao perfil do usuario.

    Segunda das tres camadas de controle de acesso (spec 5.2). O campo nao
    existe no formulario, entao um POST forjado nao o alcanca — esconder
    apenas no template deixaria a brecha aberta.

    A view precisa passar `usuario` ao instanciar o formulario; BaseCreateView
    e BaseUpdateView ja fazem isso.
    """

    campos_restritos: dict[str, list[str]] = {}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario is None:
            return
        for campo in self.campos_restritos.get(usuario.perfil, []):
            self.fields.pop(campo, None)
```

- [ ] **Step 4: Escrever as views base em `core/views.py`**

Acrescentar ao arquivo existente:

```python
from django.contrib import messages
from django.db.models import Q
from django.views.generic import CreateView, ListView, UpdateView

from core.mixins import PerfilRequiredMixin


class BaseListView(PerfilRequiredMixin, ListView):
    """Listagem com busca textual e paginacao.

    Declare `campos_busca` com os campos que o `?q=` deve varrer.
    """

    paginate_by = 25
    campos_busca: list[str] = []

    def get_queryset(self):
        qs = super().get_queryset()
        busca = self.request.GET.get("q", "").strip()
        if busca and self.campos_busca:
            filtro = Q()
            for campo in self.campos_busca:
                filtro |= Q(**{f"{campo}__icontains": busca})
            qs = qs.filter(filtro)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["busca"] = self.request.GET.get("q", "")
        return contexto


class _SalvarComAutorMixin:
    """Injeta o usuario no formulario e registra quem criou o registro."""

    mensagem_sucesso: str = "Registro salvo."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not form.instance.pk and hasattr(form.instance, "criado_por"):
            form.instance.criado_por = self.request.user
        resposta = super().form_valid(form)
        messages.success(self.request, self.mensagem_sucesso)
        return resposta


class BaseCreateView(PerfilRequiredMixin, _SalvarComAutorMixin, CreateView):
    pass


class BaseUpdateView(PerfilRequiredMixin, _SalvarComAutorMixin, UpdateView):
    pass
```

- [ ] **Step 5: Criar os templates de teste**

`tests/testapp/templates/testapp/lista.html`:
```html
{% for obj in object_list %}<p>{{ obj.nome }}</p>{% endfor %}
```

`tests/testapp/templates/testapp/form.html`:
```html
<form method="post">{% csrf_token %}{{ form.as_p }}<button>Salvar</button></form>
```

- [ ] **Step 6: Gerar a migration do model de teste e rodar**

```powershell

python manage.py makemigrations testapp

```

Nota: `testapp` só existe em `comviver/settings/test.py`. Para gerar a migration, rodar o comando com `DJANGO_SETTINGS_MODULE=comviver.settings.test`:

```powershell
$env:DJANGO_SETTINGS_MODULE = "comviver.settings.test"
python manage.py makemigrations testapp
$env:DJANGO_SETTINGS_MODULE = ""
```

```bash
pytest core/tests/test_views_base.py -v --create-db
```
Esperado: 9 testes passando.

- [ ] **Step 7: Commit**

```bash
git add core tests/testapp
git commit -m "feat(core): adiciona views base de CRUD com busca e filtro por perfil"
```

---

## Task 2: Models de identificação — `Acolhido`, `Responsavel`, `VinculoFamiliar`

**Files:**
- Create: `acolhidos/__init__.py`, `acolhidos/apps.py`, `acolhidos/models.py`, `acolhidos/factories.py`
- Create: `acolhidos/tests/__init__.py`, `acolhidos/tests/test_models.py`
- Modify: `comviver/settings/base.py` (`INSTALLED_APPS`, Pillow)
- Modify: `requirements/base.txt`

**Interfaces:**
- Consumes: `core.models.SoftDeleteModel`, `core.models.Endereco`
- Produces:
  - `acolhidos.models.StatusAcolhido` — `TextChoices` com `ACOLHIDO`, `DESLIGADO`
  - `acolhidos.models.Acolhido` — propriedades `idade: int`, `tempo_acolhimento: int | None` (dias), `nome_exibicao: str`
  - `acolhidos.models.Responsavel`
  - `acolhidos.models.VinculoFamiliar` — `unique(acolhido, responsavel)`
  - `acolhidos.factories.AcolhidoFactory`, `ResponsavelFactory`, `VinculoFamiliarFactory`

- [ ] **Step 1: Escrever os testes que falham**

`acolhidos/tests/test_models.py`:
```python
from datetime import date, timedelta

import pytest

from acolhidos.factories import AcolhidoFactory, ResponsavelFactory, VinculoFamiliarFactory
from acolhidos.models import Acolhido, StatusAcolhido, VinculoFamiliar

pytestmark = pytest.mark.django_db


class TestAcolhido:
    def test_idade_calculada_do_nascimento(self):
        acolhido = AcolhidoFactory(nascimento=date.today() - timedelta(days=365 * 10 + 3))
        assert acolhido.idade == 10

    def test_idade_antes_do_aniversario_no_ano(self):
        hoje = date.today()
        nascimento = date(hoje.year - 8, 12, 31) if hoje.month < 12 else date(hoje.year - 8, 1, 1)
        acolhido = AcolhidoFactory(nascimento=nascimento)
        esperado = 7 if hoje.month < 12 else 8
        assert acolhido.idade == esperado

    def test_nome_exibicao_prefere_nome_social(self):
        acolhido = AcolhidoFactory(nome="João da Silva", nome_social="Joana")
        assert acolhido.nome_exibicao == "Joana"

    def test_nome_exibicao_cai_no_nome_quando_sem_social(self):
        acolhido = AcolhidoFactory(nome="João da Silva", nome_social="")
        assert acolhido.nome_exibicao == "João da Silva"

    def test_status_inicial_e_acolhido(self):
        assert AcolhidoFactory().status == StatusAcolhido.ACOLHIDO

    def test_exclusao_e_logica(self):
        acolhido = AcolhidoFactory()
        pk = acolhido.pk
        acolhido.delete()
        assert not Acolhido.objects.filter(pk=pk).exists()
        assert Acolhido.todos.filter(pk=pk).exists()

    def test_cpf_e_unico_quando_preenchido(self):
        from django.db import IntegrityError

        AcolhidoFactory(cpf="12345678901")
        with pytest.raises(IntegrityError):
            AcolhidoFactory(cpf="12345678901")

    def test_varios_acolhidos_podem_estar_sem_cpf(self):
        """Crianca acolhida frequentemente chega sem documento."""
        AcolhidoFactory(cpf="")
        AcolhidoFactory(cpf="")
        assert Acolhido.objects.filter(cpf="").count() == 2


class TestVinculoFamiliar:
    def test_um_responsavel_vinculado_a_dois_irmaos(self):
        mae = ResponsavelFactory(nome="Maria")
        irmao_um = AcolhidoFactory()
        irmao_dois = AcolhidoFactory()
        VinculoFamiliarFactory(acolhido=irmao_um, responsavel=mae, parentesco="Mãe")
        VinculoFamiliarFactory(acolhido=irmao_dois, responsavel=mae, parentesco="Mãe")
        assert mae.vinculos.count() == 2

    def test_um_acolhido_com_varios_responsaveis(self):
        acolhido = AcolhidoFactory()
        VinculoFamiliarFactory(acolhido=acolhido, parentesco="Mãe")
        VinculoFamiliarFactory(acolhido=acolhido, parentesco="Avó", e_guardiao=True)
        assert acolhido.vinculos.count() == 2

    def test_nao_duplica_o_mesmo_vinculo(self):
        from django.db import IntegrityError

        acolhido = AcolhidoFactory()
        responsavel = ResponsavelFactory()
        VinculoFamiliarFactory(acolhido=acolhido, responsavel=responsavel)
        with pytest.raises(IntegrityError):
            VinculoFamiliarFactory(acolhido=acolhido, responsavel=responsavel)

    def test_autorizados_a_retirar_filtra_corretamente(self):
        acolhido = AcolhidoFactory()
        avo = ResponsavelFactory(nome="Ana")
        VinculoFamiliarFactory(
            acolhido=acolhido, responsavel=avo, parentesco="Avó", autorizado_retirar=True
        )
        VinculoFamiliarFactory(acolhido=acolhido, parentesco="Tio", autorizado_retirar=False)
        autorizados = VinculoFamiliar.objects.filter(
            acolhido=acolhido, autorizado_retirar=True
        )
        assert [v.responsavel.nome for v in autorizados] == ["Ana"]
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest acolhidos/tests/test_models.py -v
```
Esperado: `ModuleNotFoundError: No module named 'acolhidos'`.

- [ ] **Step 3: Criar o app e declarar a dependência de imagem**

```bash
python manage.py startapp acolhidos
mkdir acolhidos/tests && touch acolhidos/tests/__init__.py
rm acolhidos/tests.py
```

Acrescentar a `requirements/base.txt`:
```
Pillow>=10.4,<12.0
django-simple-history>=3.7,<4.0
django-formtools>=2.5,<3.0
```

```bash
pip install -r requirements/dev.txt
```

Em `comviver/settings/base.py`, `INSTALLED_APPS`:
```python
    "simple_history",
    "formtools",
    "core",
    "accounts",
    "acolhidos",
```

E em `MIDDLEWARE`, antes do middleware de troca de senha:
```python
    "simple_history.middleware.HistoryRequestMiddleware",
```

`acolhidos/apps.py`:
```python
from django.apps import AppConfig


class AcolhidosConfig(AppConfig):
    name = "acolhidos"
    verbose_name = "Acolhidos"
```

- [ ] **Step 4: Escrever `acolhidos/models.py`**

```python
from datetime import date

from django.db import models
from simple_history.models import HistoricalRecords

from core.models import Endereco, SoftDeleteModel


class StatusAcolhido(models.TextChoices):
    ACOLHIDO = "ACOLHIDO", "Acolhido"
    DESLIGADO = "DESLIGADO", "Desligado"


class Sexo(models.TextChoices):
    FEMININO = "F", "Feminino"
    MASCULINO = "M", "Masculino"
    OUTRO = "O", "Outro"


class Acolhido(SoftDeleteModel):
    """Crianca ou adolescente em acolhimento institucional.

    Dado sensivel de menor. O acesso e recortado por perfil e toda leitura da
    ficha e registrada em accounts.LogAcessoFicha (art. 143 do ECA).
    """

    nome = models.CharField("nome completo", max_length=150)
    nome_social = models.CharField(
        "nome social", max_length=150, blank=True,
        help_text="Preencha se a pessoa é chamada por outro nome.",
    )
    nascimento = models.DateField("data de nascimento")
    sexo = models.CharField("sexo", max_length=1, choices=Sexo.choices)
    naturalidade = models.CharField("naturalidade", max_length=100, blank=True)
    foto = models.ImageField("foto", upload_to="acolhidos/fotos/", blank=True)

    cpf = models.CharField("CPF", max_length=11, blank=True, unique=True, null=True)
    rg = models.CharField("RG", max_length=20, blank=True)
    certidao_nascimento = models.CharField("certidão de nascimento", max_length=50, blank=True)
    cartao_sus = models.CharField("cartão SUS", max_length=20, blank=True)

    status = models.CharField(
        "situação", max_length=10, choices=StatusAcolhido.choices,
        default=StatusAcolhido.ACOLHIDO,
    )
    observacoes = models.TextField("observações", blank=True)

    criado_por = models.ForeignKey(
        "accounts.Usuario", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="acolhidos_cadastrados",
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "acolhido"
        verbose_name_plural = "acolhidos"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome_exibicao

    def save(self, *args, **kwargs):
        # CPF vazio precisa virar NULL: unique=True trata "" como valor repetido,
        # e crianca acolhida frequentemente chega sem documento.
        if not self.cpf:
            self.cpf = None
        super().save(*args, **kwargs)

    @property
    def nome_exibicao(self) -> str:
        return self.nome_social or self.nome

    @property
    def idade(self) -> int:
        hoje = date.today()
        return (
            hoje.year
            - self.nascimento.year
            - ((hoje.month, hoje.day) < (self.nascimento.month, self.nascimento.day))
        )

    @property
    def tempo_acolhimento(self) -> int | None:
        """Dias desde a entrada. None quando a ficha ainda nao foi preenchida."""
        ficha = getattr(self, "ficha", None)
        if ficha is None or ficha.data_entrada is None:
            return None
        fim = ficha.data_desligamento or date.today()
        return (fim - ficha.data_entrada).days


class Responsavel(SoftDeleteModel, Endereco):
    """Familiar ou responsavel legal. Vive fora da instituicao."""

    nome = models.CharField("nome completo", max_length=150)
    cpf = models.CharField("CPF", max_length=11, blank=True)
    rg = models.CharField("RG", max_length=20, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    observacoes = models.TextField("observações", blank=True)

    criado_por = models.ForeignKey(
        "accounts.Usuario", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="responsaveis_cadastrados",
    )

    class Meta:
        verbose_name = "responsável"
        verbose_name_plural = "responsáveis"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class VinculoFamiliar(SoftDeleteModel):
    """Liga acolhido e responsavel, com os atributos do vinculo.

    E uma relacao muitos-para-muitos com dados proprios: um responsavel pode
    ter vinculo com dois irmaos acolhidos, e um acolhido tem varios
    responsaveis com papeis distintos.
    """

    acolhido = models.ForeignKey(
        Acolhido, on_delete=models.CASCADE, related_name="vinculos"
    )
    responsavel = models.ForeignKey(
        Responsavel, on_delete=models.CASCADE, related_name="vinculos"
    )
    parentesco = models.CharField("parentesco", max_length=50)
    e_guardiao = models.BooleanField("é guardião legal", default=False)
    autorizado_visita = models.BooleanField("autorizado a visitar", default=True)
    autorizado_retirar = models.BooleanField("autorizado a retirar", default=False)
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "vínculo familiar"
        verbose_name_plural = "vínculos familiares"
        constraints = [
            models.UniqueConstraint(
                fields=["acolhido", "responsavel"], name="vinculo_unico_por_par"
            )
        ]

    def __str__(self) -> str:
        return f"{self.responsavel.nome} — {self.parentesco} de {self.acolhido.nome_exibicao}"
```

- [ ] **Step 5: Escrever `acolhidos/factories.py`**

```python
import factory

from acolhidos.models import Acolhido, Responsavel, Sexo, VinculoFamiliar


class AcolhidoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Acolhido

    nome = factory.Faker("name", locale="pt_BR")
    nome_social = ""
    nascimento = factory.Faker("date_of_birth", minimum_age=2, maximum_age=17)
    sexo = Sexo.FEMININO
    naturalidade = factory.Faker("city", locale="pt_BR")
    cpf = ""


class ResponsavelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Responsavel

    nome = factory.Faker("name", locale="pt_BR")
    telefone = factory.Faker("cellphone_number", locale="pt_BR")
    cidade = factory.Faker("city", locale="pt_BR")
    uf = "MG"


class VinculoFamiliarFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VinculoFamiliar

    acolhido = factory.SubFactory(AcolhidoFactory)
    responsavel = factory.SubFactory(ResponsavelFactory)
    parentesco = "Mãe"
```

- [ ] **Step 6: Gerar migration e rodar os testes**

```powershell

python manage.py makemigrations acolhidos
python manage.py migrate

```

```bash
pytest acolhidos/tests/test_models.py -v --create-db
```
Esperado: 12 testes passando.

- [ ] **Step 7: Commit**

```bash
git add acolhidos comviver/settings/base.py requirements/base.txt
git commit -m "feat(acolhidos): adiciona Acolhido, Responsavel e VinculoFamiliar"
```

---

## Task 3: Models da ficha sigilosa e do cuidado diário

Separados da Task 2 de propósito: são exatamente os dados que o perfil
Operacional não pode ver, e o recorte fica mais claro quando moram em models
próprios.

**Files:**
- Modify: `acolhidos/models.py`, `acolhidos/factories.py`
- Create: `acolhidos/tests/test_ficha.py`

**Interfaces:**
- Consumes: `acolhidos.models.Acolhido` (Task 2)
- Produces:
  - `FichaAcolhimento` — 1:1 com `Acolhido`, `related_name="ficha"`; método `esta_completa() -> bool`
  - `DadosSaude` — 1:1, `related_name="saude"`
  - `Medicacao` — N:1, manager `em_vigor` filtrando por data
  - `Escolaridade` — N:1, `related_name="escolaridades"`
  - `DocumentoAcolhido` — N:1, `related_name="documentos"`
  - `Consentimento` — 1:1, termo LGPD do responsável

- [ ] **Step 1: Escrever os testes que falham**

`acolhidos/tests/test_ficha.py`:
```python
from datetime import date, timedelta

import pytest

from acolhidos.factories import (
    AcolhidoFactory,
    DadosSaudeFactory,
    FichaAcolhimentoFactory,
    MedicacaoFactory,
)
from acolhidos.models import Medicacao

pytestmark = pytest.mark.django_db


class TestFichaAcolhimento:
    def test_tempo_acolhimento_conta_da_entrada_ate_hoje(self):
        acolhido = AcolhidoFactory()
        FichaAcolhimentoFactory(
            acolhido=acolhido, data_entrada=date.today() - timedelta(days=45)
        )
        acolhido.refresh_from_db()
        assert acolhido.tempo_acolhimento == 45

    def test_tempo_acolhimento_para_no_desligamento(self):
        acolhido = AcolhidoFactory()
        FichaAcolhimentoFactory(
            acolhido=acolhido,
            data_entrada=date.today() - timedelta(days=100),
            data_desligamento=date.today() - timedelta(days=30),
        )
        acolhido.refresh_from_db()
        assert acolhido.tempo_acolhimento == 70

    def test_tempo_acolhimento_none_sem_ficha(self):
        assert AcolhidoFactory().tempo_acolhimento is None

    def test_ficha_incompleta_sem_orgao_requisitante(self):
        ficha = FichaAcolhimentoFactory(orgao_requisitante="")
        assert ficha.esta_completa() is False

    def test_ficha_completa_com_os_campos_obrigatorios(self):
        ficha = FichaAcolhimentoFactory(
            motivo="Negligência", orgao_requisitante="Vara da Infância",
            processo_numero="0001234-56.2026.8.13.0301",
        )
        assert ficha.esta_completa() is True


class TestDadosSaude:
    def test_um_acolhido_tem_uma_unica_ficha_de_saude(self):
        from django.db import IntegrityError

        acolhido = AcolhidoFactory()
        DadosSaudeFactory(acolhido=acolhido)
        with pytest.raises(IntegrityError):
            DadosSaudeFactory(acolhido=acolhido)


class TestMedicacao:
    def test_em_vigor_inclui_medicacao_sem_data_fim(self):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(acolhido=acolhido, inicio=date.today(), fim=None)
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 1

    def test_em_vigor_exclui_medicacao_encerrada(self):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(
            acolhido=acolhido,
            inicio=date.today() - timedelta(days=30),
            fim=date.today() - timedelta(days=1),
        )
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 0

    def test_em_vigor_exclui_medicacao_que_ainda_nao_comecou(self):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(acolhido=acolhido, inicio=date.today() + timedelta(days=5), fim=None)
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 0

    def test_em_vigor_inclui_medicacao_no_intervalo(self):
        acolhido = AcolhidoFactory()
        MedicacaoFactory(
            acolhido=acolhido,
            inicio=date.today() - timedelta(days=5),
            fim=date.today() + timedelta(days=5),
        )
        assert Medicacao.em_vigor.filter(acolhido=acolhido).count() == 1
```

O manager `em_vigor` é a regra que sustenta o cartão "medicações do dia" do
painel e o que o Operacional enxerga. Errar nele significa criança sem remédio
ou remédio a mais.

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest acolhidos/tests/test_ficha.py -v
```
Esperado: `ImportError: cannot import name 'FichaAcolhimentoFactory'`.

- [ ] **Step 3: Acrescentar os models**

Em `acolhidos/models.py`:

```python
class MedicacaoEmVigorManager(models.Manager):
    """Medicacao valida hoje: ja comecou e ainda nao terminou."""

    def get_queryset(self):
        hoje = date.today()
        return (
            super()
            .get_queryset()
            .filter(inicio__lte=hoje)
            .filter(models.Q(fim__isnull=True) | models.Q(fim__gte=hoje))
        )


class FichaAcolhimento(SoftDeleteModel):
    """Circunstancias do acolhimento e situacao juridica.

    Conteudo vedado ao perfil Operacional (art. 143 do ECA).
    """

    acolhido = models.OneToOneField(
        Acolhido, on_delete=models.CASCADE, related_name="ficha"
    )
    data_entrada = models.DateField("data de entrada")
    motivo = models.TextField("motivo do acolhimento", blank=True)
    orgao_requisitante = models.CharField("órgão requisitante", max_length=150, blank=True)
    processo_numero = models.CharField("número do processo", max_length=50, blank=True)
    vara = models.CharField("vara", max_length=100, blank=True)
    medida_protetiva = models.TextField("medida protetiva", blank=True)

    data_desligamento = models.DateField("data de desligamento", null=True, blank=True)
    destino = models.CharField("destino após o desligamento", max_length=150, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "ficha de acolhimento"
        verbose_name_plural = "fichas de acolhimento"

    def __str__(self) -> str:
        return f"Ficha de {self.acolhido.nome_exibicao}"

    def esta_completa(self) -> bool:
        """Campos minimos para a ficha servir a prestacao de contas."""
        return bool(self.motivo and self.orgao_requisitante and self.processo_numero)


class DadosSaude(SoftDeleteModel):
    acolhido = models.OneToOneField(
        Acolhido, on_delete=models.CASCADE, related_name="saude"
    )
    tipo_sanguineo = models.CharField("tipo sanguíneo", max_length=3, blank=True)
    alergias = models.TextField("alergias", blank=True)
    condicoes = models.TextField("condições de saúde", blank=True)
    plano_saude = models.CharField("plano de saúde", max_length=100, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "dados de saúde"
        verbose_name_plural = "dados de saúde"

    def __str__(self) -> str:
        return f"Saúde de {self.acolhido.nome_exibicao}"


class Medicacao(SoftDeleteModel):
    """Medicamento em uso.

    Unico dado de saude visivel ao perfil Operacional: sem ele, quem esta na
    casa no turno da tarde nao sabe o que administrar.
    """

    acolhido = models.ForeignKey(
        Acolhido, on_delete=models.CASCADE, related_name="medicacoes"
    )
    nome = models.CharField("medicamento", max_length=120)
    dosagem = models.CharField("dosagem", max_length=60)
    frequencia = models.CharField("frequência", max_length=80, help_text="Ex.: 8h e 20h")
    inicio = models.DateField("início")
    fim = models.DateField("fim", null=True, blank=True, help_text="Vazio = uso contínuo")
    observacoes = models.TextField("observações", blank=True)

    objects = models.Manager()
    em_vigor = MedicacaoEmVigorManager()

    class Meta:
        verbose_name = "medicação"
        verbose_name_plural = "medicações"
        ordering = ["nome"]

    def __str__(self) -> str:
        return f"{self.nome} {self.dosagem}"


class Escolaridade(SoftDeleteModel):
    acolhido = models.ForeignKey(
        Acolhido, on_delete=models.CASCADE, related_name="escolaridades"
    )
    escola = models.CharField("escola", max_length=150)
    serie = models.CharField("série", max_length=50)
    turno = models.CharField(
        "turno", max_length=10,
        choices=[("MANHA", "Manhã"), ("TARDE", "Tarde"), ("NOITE", "Noite")],
    )
    ano_letivo = models.PositiveIntegerField("ano letivo")

    class Meta:
        verbose_name = "escolaridade"
        verbose_name_plural = "escolaridades"
        ordering = ["-ano_letivo"]

    def __str__(self) -> str:
        return f"{self.serie} — {self.escola} ({self.ano_letivo})"


class DocumentoAcolhido(SoftDeleteModel):
    acolhido = models.ForeignKey(
        Acolhido, on_delete=models.CASCADE, related_name="documentos"
    )
    arquivo = models.FileField("arquivo", upload_to="acolhidos/documentos/")
    tipo = models.CharField("tipo", max_length=80)
    descricao = models.CharField("descrição", max_length=200, blank=True)

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"

    def __str__(self) -> str:
        return f"{self.tipo} — {self.acolhido.nome_exibicao}"


class Consentimento(SoftDeleteModel):
    """Termo de consentimento do responsavel (art. 14 da LGPD).

    Tratamento de dado de crianca exige consentimento especifico de quem
    responde por ela, com finalidade declarada.
    """

    acolhido = models.OneToOneField(
        Acolhido, on_delete=models.CASCADE, related_name="consentimento"
    )
    responsavel = models.ForeignKey(
        Responsavel, on_delete=models.PROTECT, related_name="consentimentos"
    )
    data_assinatura = models.DateField("data da assinatura")
    finalidade = models.TextField(
        "finalidade declarada",
        default="Registro administrativo do acolhimento e prestação de contas "
                "aos órgãos de controle.",
    )
    termo_assinado = models.FileField(
        "termo assinado", upload_to="acolhidos/consentimentos/", blank=True
    )

    class Meta:
        verbose_name = "consentimento"
        verbose_name_plural = "consentimentos"

    def __str__(self) -> str:
        return f"Consentimento de {self.acolhido.nome_exibicao}"
```

- [ ] **Step 4: Acrescentar as factories**

Em `acolhidos/factories.py`:
```python
from datetime import date

from acolhidos.models import DadosSaude, FichaAcolhimento, Medicacao


class FichaAcolhimentoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FichaAcolhimento

    acolhido = factory.SubFactory(AcolhidoFactory)
    data_entrada = factory.LazyFunction(date.today)
    motivo = "Negligência familiar"
    orgao_requisitante = "Conselho Tutelar"
    processo_numero = factory.Sequence(lambda n: f"000{n}-56.2026.8.13.0301")


class DadosSaudeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DadosSaude

    acolhido = factory.SubFactory(AcolhidoFactory)
    tipo_sanguineo = "O+"


class MedicacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Medicacao

    acolhido = factory.SubFactory(AcolhidoFactory)
    nome = "Dipirona"
    dosagem = "500mg"
    frequencia = "8h e 20h"
    inicio = factory.LazyFunction(date.today)
    fim = None
```

- [ ] **Step 5: Gerar migration e rodar**

```powershell
python manage.py makemigrations acolhidos
python manage.py migrate
```

```bash
pytest acolhidos/tests/ -v --create-db
```
Esperado: todos passando.

- [ ] **Step 6: Commit**

```bash
git add acolhidos
git commit -m "feat(acolhidos): adiciona ficha, saude, medicacao, escolaridade e consentimento"
```

---

## Task 4: `LogAcessoFicha` e mídia protegida

Duas exigências da spec §5.3 e §5.4 que sustentam o sigilo. Ficam juntas porque
ambas tratam de acesso a dado, não de cadastro.

**Files:**
- Modify: `accounts/models.py`
- Create: `accounts/tests/test_log_acesso.py`
- Create: `core/storage.py`, `core/tests/test_media_protegida.py`
- Modify: `core/mixins.py`, `comviver/urls.py`

**Interfaces:**
- Consumes: `acolhidos.models.Acolhido` (Task 2)
- Produces:
  - `accounts.models.LogAcessoFicha` — campos `usuario`, `acolhido`, `data_hora`, `acao`; `AcaoFicha` com `VIEW` e `EDIT`
  - `core.mixins.RegistraAcessoFichaMixin` — grava `VIEW` no `get`
  - `core.storage.servir_media_protegida(request, caminho)` — view que exige login e devolve 403 para quem não pode ver

- [ ] **Step 1: Escrever os testes que falham**

`accounts/tests/test_log_acesso.py`:
```python
import pytest
from django.urls import reverse

from accounts.models import AcaoFicha, LogAcessoFicha
from acolhidos.factories import AcolhidoFactory

pytestmark = pytest.mark.django_db


class TestLogAcessoFicha:
    def test_abrir_a_ficha_registra_a_leitura(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        log = LogAcessoFicha.objects.get(acolhido=acolhido)
        assert log.usuario == usuario_tecnico
        assert log.acao == AcaoFicha.VIEW

    def test_cada_abertura_gera_um_registro(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        assert LogAcessoFicha.objects.filter(acolhido=acolhido).count() == 2

    def test_operacional_tambem_e_registrado(self, client, usuario_operacional):
        """Mesmo vendo menos, o acesso do Operacional precisa ficar registrado."""
        acolhido = AcolhidoFactory()
        client.force_login(usuario_operacional)
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        assert LogAcessoFicha.objects.filter(
            acolhido=acolhido, usuario=usuario_operacional
        ).exists()

    def test_log_sobrevive_a_exclusao_do_usuario(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        usuario_tecnico.delete()
        log = LogAcessoFicha.objects.get(acolhido=acolhido)
        assert log.usuario is None
        assert log.usuario_descricao != ""
```

O último teste importa: se o registro de quem leu sumisse junto com o usuário, a
auditoria não responderia a um questionamento do Ministério Público meses depois.

`core/tests/test_media_protegida.py`:
```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from acolhidos.factories import AcolhidoFactory

pytestmark = pytest.mark.django_db


def _acolhido_com_foto():
    imagem = SimpleUploadedFile("foto.jpg", b"conteudo-falso-de-imagem", "image/jpeg")
    return AcolhidoFactory(foto=imagem)


class TestMediaProtegida:
    def test_anonimo_nao_baixa_a_foto(self, client):
        acolhido = _acolhido_com_foto()
        resposta = client.get(reverse("media_protegida", args=[acolhido.foto.name]))
        assert resposta.status_code == 302
        assert "/entrar/" in resposta.url

    def test_usuario_autenticado_baixa_a_foto(self, client, usuario_operacional):
        acolhido = _acolhido_com_foto()
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("media_protegida", args=[acolhido.foto.name]))
        assert resposta.status_code == 200

    def test_operacional_nao_baixa_documento_sigiloso(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.get(
            reverse("media_protegida", args=["acolhidos/documentos/processo.pdf"])
        )
        assert resposta.status_code == 403

    def test_tecnico_pode_tentar_baixar_documento(self, client, usuario_tecnico):
        """Perfil autorizado passa pela checagem; 404 porque o arquivo nao existe."""
        client.force_login(usuario_tecnico)
        resposta = client.get(
            reverse("media_protegida", args=["acolhidos/documentos/processo.pdf"])
        )
        assert resposta.status_code == 404

    def test_caminho_com_travessia_e_recusado(self, client, usuario_admin):
        client.force_login(usuario_admin)
        resposta = client.get("/media/../comviver/settings/base.py")
        assert resposta.status_code in (400, 403, 404)
```

O teste de travessia de diretório evita que um caminho manipulado leia arquivos
fora de `media/` — inclusive o `.env`.

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest accounts/tests/test_log_acesso.py core/tests/test_media_protegida.py -v
```
Esperado: `ImportError: cannot import name 'LogAcessoFicha'`.

- [ ] **Step 3: Acrescentar `LogAcessoFicha` em `accounts/models.py`**

```python
class AcaoFicha(models.TextChoices):
    VIEW = "VIEW", "Consultou"
    EDIT = "EDIT", "Alterou"


class LogAcessoFicha(models.Model):
    """Registro de acesso a ficha de acolhido.

    O historico de alteracoes nao revela quem apenas abriu e leu a ficha. Em
    instituicao de acolhimento essa informacao e necessaria, e precisa
    sobreviver a exclusao do usuario — por isso `usuario_descricao` guarda a
    identificacao em texto.
    """

    usuario = models.ForeignKey(
        "accounts.Usuario", null=True, on_delete=models.SET_NULL, related_name="acessos_ficha"
    )
    usuario_descricao = models.CharField("usuário", max_length=200, blank=True)
    acolhido = models.ForeignKey(
        "acolhidos.Acolhido", on_delete=models.CASCADE, related_name="acessos"
    )
    data_hora = models.DateTimeField("data e hora", auto_now_add=True)
    acao = models.CharField("ação", max_length=5, choices=AcaoFicha.choices)

    class Meta:
        verbose_name = "acesso a ficha"
        verbose_name_plural = "acessos a fichas"
        ordering = ["-data_hora"]
        indexes = [models.Index(fields=["acolhido", "-data_hora"])]

    def __str__(self) -> str:
        return f"{self.usuario_descricao} {self.get_acao_display().lower()} em {self.data_hora}"

    @classmethod
    def registrar(cls, usuario, acolhido, acao=AcaoFicha.VIEW):
        return cls.objects.create(
            usuario=usuario,
            usuario_descricao=str(usuario),
            acolhido=acolhido,
            acao=acao,
        )
```

- [ ] **Step 4: Acrescentar o mixin em `core/mixins.py`**

```python
class RegistraAcessoFichaMixin:
    """Registra em LogAcessoFicha toda abertura da ficha.

    Usar apenas em views cujo `get_object()` devolva um Acolhido.
    """

    def get_object(self, queryset=None):
        objeto = super().get_object(queryset)
        from accounts.models import AcaoFicha, LogAcessoFicha

        LogAcessoFicha.registrar(self.request.user, objeto, AcaoFicha.VIEW)
        return objeto
```

- [ ] **Step 5: Escrever `core/storage.py`**

```python
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404

# Prefixos cujo conteudo e vedado ao perfil Operacional.
PREFIXOS_SIGILOSOS = ("acolhidos/documentos/", "acolhidos/consentimentos/")


@login_required
def servir_media_protegida(request, caminho: str):
    """Entrega arquivo de `media/` apenas a quem pode ve-lo.

    Arquivo em diretorio publico ficaria acessivel a quem descobrisse a URL —
    e aqui isso significaria a foto de uma crianca acolhida exposta sem login.
    """
    raiz = Path(settings.MEDIA_ROOT).resolve()
    destino = (raiz / caminho).resolve()

    # Impede travessia de diretorio: `../` sairia de media/ e alcancaria o .env.
    if not destino.is_relative_to(raiz):
        raise PermissionDenied("Caminho inválido.")

    if caminho.startswith(PREFIXOS_SIGILOSOS) and not request.user.pode_ver_ficha_completa():
        raise PermissionDenied("Seu perfil não tem acesso a este documento.")

    if not destino.is_file():
        raise Http404("Arquivo não encontrado.")

    return FileResponse(destino.open("rb"))
```

- [ ] **Step 6: Ligar a rota e desativar o servidor de mídia do Django**

Em `comviver/urls.py`, substituir o bloco `if settings.DEBUG`:
```python
from core.storage import servir_media_protegida

urlpatterns = [
    path("admin/", admin.site.urls),
    path("media/<path:caminho>", servir_media_protegida, name="media_protegida"),
    path("", include("accounts.urls")),
    path("", include("acolhidos.urls")),
    path("", include("core.urls")),
]
```

O `static(settings.MEDIA_URL, ...)` sai: servir mídia sem checagem, ainda que só
em desenvolvimento, treina o hábito errado e vaza em qualquer demonstração.

- [ ] **Step 7: Gerar migration, rodar os testes**

```powershell

python manage.py makemigrations accounts
python manage.py migrate

```

```bash
pytest accounts/tests/ core/tests/ -v --create-db
```
Esperado: todos passando, exceto os que dependem da rota `acolhidos:detalhe`,
criada na Task 5. Rodar novamente ao fim daquela tarefa.

- [ ] **Step 8: Commit**

```bash
git add accounts core comviver/urls.py
git commit -m "feat: adiciona log de acesso a ficha e media servida com permissao"
```

---

## Task 5: Lista e ficha do acolhido, com recorte por perfil

O coração desta fase. É onde a matriz da spec §5.1 vira código.

**Files:**
- Create: `acolhidos/views.py`, `acolhidos/urls.py`
- Create: `templates/acolhidos/acolhido_list.html`, `acolhido_detail.html`
- Create: `templates/acolhidos/partials/_ficha_sigilosa.html`, `_cuidado_diario.html`
- Create: `acolhidos/tests/test_permissoes.py`
- Modify: `core/context_processors.py`, `core/views.py` (cartões do painel)

**Interfaces:**
- Consumes: `core.views.BaseListView` (Task 1), `core.mixins.RegistraAcessoFichaMixin` (Task 4)
- Produces: rotas `acolhidos:lista`, `acolhidos:detalhe`; contexto do detalhe com `pode_ver_ficha: bool`, `medicacoes_em_vigor`, `autorizados_retirar`

- [ ] **Step 1: Escrever os testes de permissão**

`acolhidos/tests/test_permissoes.py`:
```python
import pytest
from django.urls import reverse

from acolhidos.factories import (
    AcolhidoFactory,
    FichaAcolhimentoFactory,
    MedicacaoFactory,
    VinculoFamiliarFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def acolhido_completo():
    acolhido = AcolhidoFactory(nome="Ana Clara Souza")
    FichaAcolhimentoFactory(
        acolhido=acolhido,
        motivo="Negligência familiar grave",
        processo_numero="0001234-56.2026.8.13.0301",
        vara="Vara da Infância e Juventude de Itajubá",
    )
    MedicacaoFactory(acolhido=acolhido, nome="Dipirona")
    VinculoFamiliarFactory(
        acolhido=acolhido, parentesco="Avó", autorizado_retirar=True
    )
    return acolhido


class TestListaDeAcolhidos:
    @pytest.mark.parametrize(
        "fixture_usuario",
        ["usuario_admin", "usuario_tecnico", "usuario_operacional"],
    )
    def test_todos_os_perfis_veem_a_lista(self, client, request, fixture_usuario):
        usuario = request.getfixturevalue(fixture_usuario)
        client.force_login(usuario)
        assert client.get(reverse("acolhidos:lista")).status_code == 200

    def test_lista_mostra_o_nome_e_a_situacao(self, client, usuario_operacional):
        AcolhidoFactory(nome="Ana Clara Souza")
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("acolhidos:lista")).content.decode()
        assert "Ana Clara Souza" in conteudo
        assert "Acolhido" in conteudo

    def test_lista_nao_mostra_motivo_para_ninguem(self, client, usuario_admin, acolhido_completo):
        """Motivo do acolhimento nao aparece em listagem, nem para o Admin:
        listagem e tela que fica aberta e visivel a quem passa pela sala."""
        client.force_login(usuario_admin)
        conteudo = client.get(reverse("acolhidos:lista")).content.decode()
        assert "Negligência familiar grave" not in conteudo

    def test_busca_encontra_por_parte_do_nome(self, client, usuario_operacional):
        AcolhidoFactory(nome="Ana Clara Souza")
        AcolhidoFactory(nome="Bruno Lima")
        client.force_login(usuario_operacional)
        resultado = client.get(reverse("acolhidos:lista") + "?q=clara")
        assert len(resultado.context["object_list"]) == 1


class TestFichaSigilosa:
    """Matriz da spec 5.1, linha a linha."""

    @pytest.mark.parametrize("fixture_usuario", ["usuario_admin", "usuario_tecnico"])
    def test_perfil_autorizado_ve_o_motivo(
        self, client, request, fixture_usuario, acolhido_completo
    ):
        client.force_login(request.getfixturevalue(fixture_usuario))
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Negligência familiar grave" in conteudo

    def test_operacional_nao_ve_o_motivo(self, client, usuario_operacional, acolhido_completo):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Negligência familiar grave" not in conteudo

    def test_operacional_nao_ve_o_processo(self, client, usuario_operacional, acolhido_completo):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "0001234-56.2026.8.13.0301" not in conteudo

    def test_operacional_nao_ve_a_vara(self, client, usuario_operacional, acolhido_completo):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Vara da Infância" not in conteudo

    def test_contexto_marca_que_operacional_nao_pode_ver(
        self, client, usuario_operacional, acolhido_completo
    ):
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("acolhidos:detalhe", args=[acolhido_completo.pk]))
        assert resposta.context["pode_ver_ficha"] is False


class TestCuidadoDiario:
    """O que o Operacional precisa e pode ver."""

    def test_operacional_ve_a_medicacao_em_vigor(
        self, client, usuario_operacional, acolhido_completo
    ):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Dipirona" in conteudo

    def test_operacional_ve_quem_pode_retirar(
        self, client, usuario_operacional, acolhido_completo
    ):
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido_completo.pk])
        ).content.decode()
        assert "Avó" in conteudo

    def test_operacional_nao_ve_condicoes_de_saude(self, client, usuario_operacional):
        from acolhidos.factories import DadosSaudeFactory

        acolhido = AcolhidoFactory()
        DadosSaudeFactory(acolhido=acolhido, condicoes="Transtorno de ansiedade")
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[acolhido.pk])
        ).content.decode()
        assert "Transtorno de ansiedade" not in conteudo
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest acolhidos/tests/test_permissoes.py -v
```
Esperado: `NoReverseMatch: 'acolhidos' is not a registered namespace`.

- [ ] **Step 3: Escrever `acolhidos/views.py`**

```python
from django.views.generic import DetailView

from accounts.models import Perfil
from acolhidos.models import Acolhido, Medicacao, StatusAcolhido, VinculoFamiliar
from core.mixins import PerfilRequiredMixin, RegistraAcessoFichaMixin
from core.views import BaseListView

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]


class AcolhidoListView(BaseListView):
    model = Acolhido
    template_name = "acolhidos/acolhido_list.html"
    context_object_name = "acolhidos"
    campos_busca = ["nome", "nome_social"]
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        qs = super().get_queryset().select_related("ficha")
        situacao = self.request.GET.get("situacao", StatusAcolhido.ACOLHIDO)
        if situacao != "TODOS":
            qs = qs.filter(status=situacao)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["situacao"] = self.request.GET.get("situacao", StatusAcolhido.ACOLHIDO)
        return contexto


class AcolhidoDetailView(PerfilRequiredMixin, RegistraAcessoFichaMixin, DetailView):
    """Ficha do acolhido, recortada pelo perfil.

    Todos os perfis abrem a ficha, mas o Operacional recebe apenas o bloco de
    cuidado diario. Os dados sigilosos nao sao renderizados — nao basta
    esconde-los, precisam estar ausentes do HTML (spec 5.2, camada 3).
    """

    model = Acolhido
    template_name = "acolhidos/acolhido_detail.html"
    context_object_name = "acolhido"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        acolhido = self.object

        contexto["pode_ver_ficha"] = self.request.user.pode_ver_ficha_completa()
        contexto["medicacoes_em_vigor"] = Medicacao.em_vigor.filter(acolhido=acolhido)
        contexto["autorizados_retirar"] = (
            VinculoFamiliar.objects.filter(acolhido=acolhido, autorizado_retirar=True)
            .select_related("responsavel")
        )

        if contexto["pode_ver_ficha"]:
            contexto["ficha"] = getattr(acolhido, "ficha", None)
            contexto["saude"] = getattr(acolhido, "saude", None)
            contexto["vinculos"] = acolhido.vinculos.select_related("responsavel")
            contexto["escolaridades"] = acolhido.escolaridades.all()
            contexto["documentos"] = acolhido.documentos.all()

        return contexto
```

O ponto central: os dados sigilosos só entram no contexto quando o perfil pode
vê-los. O template não tem como renderizá-los por engano.

- [ ] **Step 4: Escrever `acolhidos/urls.py`**

```python
from django.urls import path

from acolhidos import views

app_name = "acolhidos"

urlpatterns = [
    path("acolhidos/", views.AcolhidoListView.as_view(), name="lista"),
    path("acolhidos/<int:pk>/", views.AcolhidoDetailView.as_view(), name="detalhe"),
]
```

- [ ] **Step 5: Escrever os templates**

`templates/acolhidos/acolhido_list.html`:
```html
{% extends "base.html" %}
{% block titulo %}Acolhidos{% endblock %}
{% block cabecalho %}Acolhidos{% endblock %}

{% block acoes %}
  {% if user.pode_ver_ficha_completa %}
    <a href="{% url 'acolhidos:novo' %}" class="btn btn-primary">
      <i class="bi bi-plus-lg"></i> Novo acolhimento
    </a>
  {% endif %}
{% endblock %}

{% block conteudo %}
  <form method="get" class="row g-2 mb-3">
    <div class="col-12 col-md-5">
      <input type="search" name="q" value="{{ busca }}" class="form-control"
             placeholder="Buscar por nome">
    </div>
    <div class="col-8 col-md-3">
      <select name="situacao" class="form-select">
        <option value="ACOLHIDO" {% if situacao == 'ACOLHIDO' %}selected{% endif %}>Acolhidos</option>
        <option value="DESLIGADO" {% if situacao == 'DESLIGADO' %}selected{% endif %}>Desligados</option>
        <option value="TODOS" {% if situacao == 'TODOS' %}selected{% endif %}>Todos</option>
      </select>
    </div>
    <div class="col-4 col-md-2">
      <button class="btn btn-outline-secondary w-100">Filtrar</button>
    </div>
  </form>

  <div class="row g-3">
    {% for acolhido in acolhidos %}
      <div class="col-12 col-sm-6 col-lg-4">
        <a href="{% url 'acolhidos:detalhe' acolhido.pk %}"
           class="card h-100 shadow-sm text-decoration-none text-dark">
          <div class="card-body d-flex gap-3 align-items-center">
            {% if acolhido.foto %}
              <img src="{% url 'media_protegida' acolhido.foto.name %}"
                   alt="" width="56" height="56"
                   class="rounded-circle object-fit-cover">
            {% else %}
              <span class="rounded-circle bg-light d-flex align-items-center
                           justify-content-center" style="width:56px;height:56px;">
                <i class="bi bi-person text-muted"></i>
              </span>
            {% endif %}
            <div>
              <div class="fw-semibold">{{ acolhido.nome_exibicao }}</div>
              <div class="text-muted small">{{ acolhido.idade }} anos</div>
              <span class="badge {% if acolhido.status == 'ACOLHIDO' %}text-bg-success
                    {% else %}text-bg-secondary{% endif %}">
                {{ acolhido.get_status_display }}
              </span>
            </div>
          </div>
        </a>
      </div>
    {% empty %}
      <div class="col-12"><p class="text-muted">Nenhum acolhido encontrado.</p></div>
    {% endfor %}
  </div>
{% endblock %}
```

A listagem mostra nome, foto, idade e situação — e nada mais. É tela que fica
aberta na sala.

`templates/acolhidos/partials/_cuidado_diario.html`:
```html
<div class="card mb-3">
  <div class="card-header">Cuidado diário</div>
  <div class="card-body">
    <h3 class="h6">Medicação em uso</h3>
    {% if medicacoes_em_vigor %}
      <ul class="list-unstyled mb-3">
        {% for medicacao in medicacoes_em_vigor %}
          <li class="mb-1">
            <strong>{{ medicacao.nome }}</strong> {{ medicacao.dosagem }}
            <span class="text-muted">— {{ medicacao.frequencia }}</span>
          </li>
        {% endfor %}
      </ul>
    {% else %}
      <p class="text-muted small mb-3">Nenhuma medicação em uso.</p>
    {% endif %}

    <h3 class="h6">Autorizados a retirar</h3>
    {% if autorizados_retirar %}
      <ul class="list-unstyled mb-0">
        {% for vinculo in autorizados_retirar %}
          <li>{{ vinculo.responsavel.nome }}
            <span class="text-muted">— {{ vinculo.parentesco }}</span>
            {% if vinculo.responsavel.telefone %}
              <span class="text-muted small">({{ vinculo.responsavel.telefone }})</span>
            {% endif %}
          </li>
        {% endfor %}
      </ul>
    {% else %}
      <p class="text-muted small mb-0">
        Ninguém autorizado. Em caso de solicitação, chame a coordenação.
      </p>
    {% endif %}
  </div>
</div>
```

`templates/acolhidos/partials/_ficha_sigilosa.html`:
```html
<div class="card mb-3 border-warning">
  <div class="card-header bg-warning-subtle d-flex align-items-center gap-2">
    <i class="bi bi-shield-lock"></i> Ficha de acolhimento
    <span class="badge text-bg-warning ms-auto">Informação sigilosa</span>
  </div>
  <div class="card-body">
    {% if ficha %}
      <dl class="row mb-0">
        <dt class="col-sm-4">Data de entrada</dt>
        <dd class="col-sm-8">{{ ficha.data_entrada|date:"d/m/Y" }}</dd>

        <dt class="col-sm-4">Tempo de acolhimento</dt>
        <dd class="col-sm-8">{{ acolhido.tempo_acolhimento }} dias</dd>

        <dt class="col-sm-4">Motivo</dt>
        <dd class="col-sm-8">{{ ficha.motivo|default:"—" }}</dd>

        <dt class="col-sm-4">Órgão requisitante</dt>
        <dd class="col-sm-8">{{ ficha.orgao_requisitante|default:"—" }}</dd>

        <dt class="col-sm-4">Processo</dt>
        <dd class="col-sm-8">{{ ficha.processo_numero|default:"—" }}</dd>

        <dt class="col-sm-4">Vara</dt>
        <dd class="col-sm-8">{{ ficha.vara|default:"—" }}</dd>

        <dt class="col-sm-4">Medida protetiva</dt>
        <dd class="col-sm-8">{{ ficha.medida_protetiva|default:"—" }}</dd>
      </dl>
    {% else %}
      <p class="text-muted mb-0">
        Ficha de acolhimento ainda não preenchida.
        <a href="{% url 'acolhidos:editar_ficha' acolhido.pk %}">Preencher agora</a>.
      </p>
    {% endif %}
  </div>
</div>

{% if saude %}
  <div class="card mb-3">
    <div class="card-header">Saúde</div>
    <div class="card-body">
      <dl class="row mb-0">
        <dt class="col-sm-4">Tipo sanguíneo</dt>
        <dd class="col-sm-8">{{ saude.tipo_sanguineo|default:"—" }}</dd>
        <dt class="col-sm-4">Alergias</dt>
        <dd class="col-sm-8">{{ saude.alergias|default:"—" }}</dd>
        <dt class="col-sm-4">Condições</dt>
        <dd class="col-sm-8">{{ saude.condicoes|default:"—" }}</dd>
      </dl>
    </div>
  </div>
{% endif %}
```

`templates/acolhidos/acolhido_detail.html`:
```html
{% extends "base.html" %}
{% block titulo %}{{ acolhido.nome_exibicao }}{% endblock %}
{% block cabecalho %}{{ acolhido.nome_exibicao }}{% endblock %}

{% block acoes %}
  {% if pode_ver_ficha %}
    <a href="{% url 'acolhidos:editar' acolhido.pk %}" class="btn btn-outline-secondary">Editar</a>
    {% if acolhido.status == 'ACOLHIDO' %}
      <a href="{% url 'acolhidos:desligar' acolhido.pk %}" class="btn btn-outline-danger">
        Registrar desligamento
      </a>
    {% endif %}
  {% endif %}
{% endblock %}

{% block conteudo %}
  <div class="row g-4">
    <div class="col-12 col-lg-4">
      <div class="card mb-3">
        <div class="card-body text-center">
          {% if acolhido.foto %}
            <img src="{% url 'media_protegida' acolhido.foto.name %}" alt=""
                 class="rounded-circle object-fit-cover mb-3" width="120" height="120">
          {% endif %}
          <h2 class="h5 mb-1">{{ acolhido.nome_exibicao }}</h2>
          {% if acolhido.nome_social %}
            <p class="text-muted small mb-1">Registro: {{ acolhido.nome }}</p>
          {% endif %}
          <p class="text-muted mb-2">
            {{ acolhido.idade }} anos · {{ acolhido.get_sexo_display }}
          </p>
          <span class="badge {% if acolhido.status == 'ACOLHIDO' %}text-bg-success
                {% else %}text-bg-secondary{% endif %}">
            {{ acolhido.get_status_display }}
          </span>
        </div>
      </div>

      {% include "acolhidos/partials/_cuidado_diario.html" %}
    </div>

    <div class="col-12 col-lg-8">
      {% if pode_ver_ficha %}
        {% include "acolhidos/partials/_ficha_sigilosa.html" %}
      {% else %}
        <div class="alert alert-secondary">
          <i class="bi bi-shield-lock"></i>
          Os demais dados desta ficha são sigilosos e restritos à equipe técnica.
        </div>
      {% endif %}
    </div>
  </div>
{% endblock %}
```

- [ ] **Step 6: Acrescentar ao menu e ao painel**

Em `core/context_processors.py`, antes do item de usuários:
```python
    itens.append(
        {"rotulo": "Acolhidos", "url": reverse("acolhidos:lista"), "icone": "people-fill"}
    )
```

Em `core/views.py`, dentro de `_montar_cartoes`, antes do cartão de usuários:
```python
        from acolhidos.models import Acolhido, StatusAcolhido

        cartoes.append(
            {
                "titulo": "Acolhidos",
                "valor": Acolhido.objects.filter(status=StatusAcolhido.ACOLHIDO).count(),
                "descricao": "em acolhimento hoje",
                "icone": "people-fill",
            }
        )

        if self.request.user.pode_ver_ficha_completa():
            from acolhidos.models import Medicacao

            cartoes.append(
                {
                    "titulo": "Medicações do dia",
                    "valor": Medicacao.em_vigor.count(),
                    "descricao": "em uso hoje",
                    "icone": "capsule",
                }
            )
```

- [ ] **Step 7: Rodar os testes**

```bash
pytest acolhidos/tests/ accounts/tests/ core/tests/ -v
```
Esperado: todos passando, inclusive os de `test_log_acesso.py` que estavam
pendentes da Task 4.

As rotas `acolhidos:novo`, `acolhidos:editar`, `acolhidos:editar_ficha` e
`acolhidos:desligar` ainda não existem e quebrariam os templates. Criá-las como
esqueleto agora, com implementação real nas Tasks 6 e 7:

```python
    path("acolhidos/novo/", views.AcolhimentoWizard.as_view(), name="novo"),
    path("acolhidos/<int:pk>/editar/", views.AcolhidoUpdateView.as_view(), name="editar"),
    path("acolhidos/<int:pk>/ficha/", views.FichaUpdateView.as_view(), name="editar_ficha"),
    path("acolhidos/<int:pk>/desligar/", views.DesligamentoView.as_view(), name="desligar"),
```

- [ ] **Step 8: Commit**

```bash
git add acolhidos templates/acolhidos core
git commit -m "feat(acolhidos): adiciona lista e ficha com recorte de sigilo por perfil"
```

---

## Task 6: Assistente de acolhimento em quatro etapas

**Files:**
- Create: `acolhidos/forms.py`
- Modify: `acolhidos/views.py`, `acolhidos/urls.py`
- Create: `templates/acolhidos/acolhido_wizard.html`
- Create: `acolhidos/tests/test_assistente.py`
- Modify: `comviver/settings/base.py` (diretório de arquivos temporários do assistente)

**Interfaces:**
- Consumes: `acolhidos.models.*` (Tasks 2 e 3)
- Produces:
  - `acolhidos.forms.EtapaIdentificacaoForm`, `EtapaAcolhimentoForm`, `EtapaSaudeEscolaForm`, `EtapaResponsavelForm`
  - `acolhidos.views.AcolhimentoWizard` — `SessionWizardView` com quatro etapas nomeadas `identificacao`, `acolhimento`, `saude`, `responsavel`

- [ ] **Step 1: Escrever os testes que falham**

`acolhidos/tests/test_assistente.py`:
```python
from datetime import date

import pytest
from django.urls import reverse

from acolhidos.models import Acolhido, FichaAcolhimento, VinculoFamiliar

pytestmark = pytest.mark.django_db

URL = "/acolhidos/novo/"

DADOS_IDENTIFICACAO = {
    "acolhimento_wizard-current_step": "identificacao",
    "identificacao-nome": "Ana Clara Souza",
    "identificacao-nome_social": "",
    "identificacao-nascimento": "2015-03-10",
    "identificacao-sexo": "F",
    "identificacao-naturalidade": "Itajubá",
    "identificacao-cpf": "",
    "identificacao-rg": "",
    "identificacao-certidao_nascimento": "",
    "identificacao-cartao_sus": "",
}

DADOS_ACOLHIMENTO = {
    "acolhimento_wizard-current_step": "acolhimento",
    "acolhimento-data_entrada": "2026-09-01",
    "acolhimento-motivo": "Negligência familiar",
    "acolhimento-orgao_requisitante": "Conselho Tutelar",
    "acolhimento-processo_numero": "0001234-56.2026.8.13.0301",
    "acolhimento-vara": "Vara da Infância",
    "acolhimento-medida_protetiva": "Acolhimento institucional",
}

DADOS_SAUDE = {
    "acolhimento_wizard-current_step": "saude",
    "saude-tipo_sanguineo": "O+",
    "saude-alergias": "Dipirona",
    "saude-condicoes": "",
    "saude-plano_saude": "",
    "saude-escola": "E.E. Dom Pedro",
    "saude-serie": "4º ano",
    "saude-turno": "MANHA",
    "saude-ano_letivo": "2026",
}

DADOS_RESPONSAVEL = {
    "acolhimento_wizard-current_step": "responsavel",
    "responsavel-nome": "Maria Souza",
    "responsavel-cpf": "",
    "responsavel-telefone": "35999990000",
    "responsavel-parentesco": "Avó",
    "responsavel-e_guardiao": "on",
    "responsavel-autorizado_visita": "on",
    "responsavel-autorizado_retirar": "on",
}


class TestAcessoAoAssistente:
    def test_operacional_recebe_403(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get(URL).status_code == 403

    def test_tecnico_acessa(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        assert client.get(URL).status_code == 200


class TestFluxoCompleto:
    def test_percorrer_as_quatro_etapas_cria_o_acolhido(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        client.post(URL, DADOS_IDENTIFICACAO)
        client.post(URL, DADOS_ACOLHIMENTO)
        client.post(URL, DADOS_SAUDE)
        resposta = client.post(URL, DADOS_RESPONSAVEL)

        assert resposta.status_code == 302
        acolhido = Acolhido.objects.get(nome="Ana Clara Souza")
        assert acolhido.idade >= 10

    def test_cria_a_ficha_de_acolhimento(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        client.post(URL, DADOS_IDENTIFICACAO)
        client.post(URL, DADOS_ACOLHIMENTO)
        client.post(URL, DADOS_SAUDE)
        client.post(URL, DADOS_RESPONSAVEL)

        ficha = FichaAcolhimento.objects.get(acolhido__nome="Ana Clara Souza")
        assert ficha.data_entrada == date(2026, 9, 1)
        assert ficha.processo_numero == "0001234-56.2026.8.13.0301"

    def test_cria_o_vinculo_com_o_responsavel(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        client.post(URL, DADOS_IDENTIFICACAO)
        client.post(URL, DADOS_ACOLHIMENTO)
        client.post(URL, DADOS_SAUDE)
        client.post(URL, DADOS_RESPONSAVEL)

        vinculo = VinculoFamiliar.objects.get(acolhido__nome="Ana Clara Souza")
        assert vinculo.responsavel.nome == "Maria Souza"
        assert vinculo.parentesco == "Avó"
        assert vinculo.e_guardiao is True

    def test_registra_quem_cadastrou(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        client.post(URL, DADOS_IDENTIFICACAO)
        client.post(URL, DADOS_ACOLHIMENTO)
        client.post(URL, DADOS_SAUDE)
        client.post(URL, DADOS_RESPONSAVEL)

        assert Acolhido.objects.get(nome="Ana Clara Souza").criado_por == usuario_tecnico


class TestValidacaoNoMeioDoCaminho:
    def test_etapa_com_erro_nao_avanca(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        dados = DADOS_IDENTIFICACAO | {"identificacao-nome": ""}
        resposta = client.post(URL, dados)
        assert resposta.status_code == 200
        assert resposta.context["wizard"]["steps"].current == "identificacao"

    def test_nada_e_gravado_antes_da_ultima_etapa(self, client, usuario_tecnico):
        """O registro so nasce ao concluir: acolhido sem ficha nem responsavel
        seria pior que nenhum registro."""
        client.force_login(usuario_tecnico)
        client.post(URL, DADOS_IDENTIFICACAO)
        client.post(URL, DADOS_ACOLHIMENTO)
        assert Acolhido.objects.count() == 0

    def test_data_de_entrada_no_futuro_e_recusada(self, client, usuario_tecnico):
        from datetime import timedelta

        client.force_login(usuario_tecnico)
        client.post(URL, DADOS_IDENTIFICACAO)
        futuro = (date.today() + timedelta(days=10)).isoformat()
        resposta = client.post(URL, DADOS_ACOLHIMENTO | {"acolhimento-data_entrada": futuro})
        assert resposta.status_code == 200
        assert "não pode ser no futuro" in resposta.content.decode()
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest acolhidos/tests/test_assistente.py -v
```
Esperado: erro 500 ou `AttributeError` — `AcolhimentoWizard` é um esqueleto vazio.

- [ ] **Step 3: Escrever `acolhidos/forms.py`**

```python
from datetime import date

from django import forms

from acolhidos.models import Acolhido, DadosSaude, FichaAcolhimento


def _aplicar_classes(campos):
    for nome, campo in campos.items():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.update({"class": "form-check-input"})
        elif isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})
        if isinstance(campo, forms.DateField):
            campo.widget = forms.DateInput(
                attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"
            )


class EtapaIdentificacaoForm(forms.ModelForm):
    class Meta:
        model = Acolhido
        fields = [
            "nome", "nome_social", "nascimento", "sexo", "naturalidade",
            "foto", "cpf", "rg", "certidao_nascimento", "cartao_sus",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self.fields)

    def clean_nascimento(self):
        nascimento = self.cleaned_data["nascimento"]
        if nascimento > date.today():
            raise forms.ValidationError("A data de nascimento não pode ser no futuro.")
        if date.today().year - nascimento.year > 21:
            raise forms.ValidationError(
                "Idade acima de 21 anos. Confira a data — o acolhimento é de "
                "crianças e adolescentes."
            )
        return nascimento

    def clean_cpf(self):
        cpf = "".join(filter(str.isdigit, self.cleaned_data.get("cpf", "")))
        if cpf and len(cpf) != 11:
            raise forms.ValidationError("O CPF precisa ter 11 dígitos.")
        return cpf


class EtapaAcolhimentoForm(forms.ModelForm):
    class Meta:
        model = FichaAcolhimento
        fields = [
            "data_entrada", "motivo", "orgao_requisitante",
            "processo_numero", "vara", "medida_protetiva",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self.fields)

    def clean_data_entrada(self):
        entrada = self.cleaned_data["data_entrada"]
        if entrada > date.today():
            raise forms.ValidationError("A data de entrada não pode ser no futuro.")
        return entrada


class EtapaSaudeEscolaForm(forms.ModelForm):
    escola = forms.CharField(label="Escola", max_length=150, required=False)
    serie = forms.CharField(label="Série", max_length=50, required=False)
    turno = forms.ChoiceField(
        label="Turno", required=False,
        choices=[("", "—"), ("MANHA", "Manhã"), ("TARDE", "Tarde"), ("NOITE", "Noite")],
    )
    ano_letivo = forms.IntegerField(label="Ano letivo", required=False)

    class Meta:
        model = DadosSaude
        fields = ["tipo_sanguineo", "alergias", "condicoes", "plano_saude"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self.fields)

    def clean(self):
        dados = super().clean()
        if dados.get("escola") and not dados.get("ano_letivo"):
            self.add_error("ano_letivo", "Informe o ano letivo da escola.")
        return dados


class EtapaResponsavelForm(forms.Form):
    nome = forms.CharField(label="Nome do responsável", max_length=150)
    cpf = forms.CharField(label="CPF", max_length=14, required=False)
    telefone = forms.CharField(label="Telefone", max_length=20, required=False)
    parentesco = forms.CharField(label="Parentesco", max_length=50)
    e_guardiao = forms.BooleanField(label="É guardião legal", required=False)
    autorizado_visita = forms.BooleanField(
        label="Autorizado a visitar", required=False, initial=True
    )
    autorizado_retirar = forms.BooleanField(label="Autorizado a retirar", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes(self.fields)
```

- [ ] **Step 4: Escrever o assistente em `acolhidos/views.py`**

```python
from django.db import transaction
from django.shortcuts import redirect
from django.contrib import messages
from formtools.wizard.views import SessionWizardView
from django.conf import settings
from django.core.files.storage import FileSystemStorage

from acolhidos.forms import (
    EtapaAcolhimentoForm,
    EtapaIdentificacaoForm,
    EtapaResponsavelForm,
    EtapaSaudeEscolaForm,
)
from acolhidos.models import DadosSaude, Escolaridade, FichaAcolhimento, Responsavel, VinculoFamiliar

ETAPAS = [
    ("identificacao", EtapaIdentificacaoForm),
    ("acolhimento", EtapaAcolhimentoForm),
    ("saude", EtapaSaudeEscolaForm),
    ("responsavel", EtapaResponsavelForm),
]

TITULOS_ETAPA = {
    "identificacao": "Identificação",
    "acolhimento": "Acolhimento",
    "saude": "Saúde e escola",
    "responsavel": "Responsáveis",
}


class AcolhimentoWizard(PerfilRequiredMixin, SessionWizardView):
    """Cadastro de novo acolhimento em quatro etapas.

    Sao cerca de 30 campos, e a etapa 2 e restrita ao perfil Tecnico. O
    rascunho fica na sessao: uma interrupcao no meio nao descarta o trabalho.

    Nada e gravado antes da ultima etapa — acolhido sem ficha nem responsavel
    seria pior que nenhum registro.
    """

    form_list = ETAPAS
    template_name = "acolhidos/acolhido_wizard.html"
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO]
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT / "_assistente")

    def get_context_data(self, form, **kwargs):
        contexto = super().get_context_data(form=form, **kwargs)
        contexto["titulos_etapa"] = TITULOS_ETAPA
        contexto["titulo_atual"] = TITULOS_ETAPA[self.steps.current]
        return contexto

    @transaction.atomic
    def done(self, form_list, form_dict, **kwargs):
        acolhido = form_dict["identificacao"].save(commit=False)
        acolhido.criado_por = self.request.user
        acolhido.save()

        ficha = form_dict["acolhimento"].save(commit=False)
        ficha.acolhido = acolhido
        ficha.save()

        etapa_saude = form_dict["saude"]
        saude = etapa_saude.save(commit=False)
        saude.acolhido = acolhido
        saude.save()

        if etapa_saude.cleaned_data.get("escola"):
            Escolaridade.objects.create(
                acolhido=acolhido,
                escola=etapa_saude.cleaned_data["escola"],
                serie=etapa_saude.cleaned_data.get("serie", ""),
                turno=etapa_saude.cleaned_data.get("turno", ""),
                ano_letivo=etapa_saude.cleaned_data["ano_letivo"],
            )

        dados_responsavel = form_dict["responsavel"].cleaned_data
        responsavel = Responsavel.objects.create(
            nome=dados_responsavel["nome"],
            cpf="".join(filter(str.isdigit, dados_responsavel.get("cpf", ""))),
            telefone=dados_responsavel.get("telefone", ""),
            criado_por=self.request.user,
        )
        VinculoFamiliar.objects.create(
            acolhido=acolhido,
            responsavel=responsavel,
            parentesco=dados_responsavel["parentesco"],
            e_guardiao=dados_responsavel.get("e_guardiao", False),
            autorizado_visita=dados_responsavel.get("autorizado_visita", False),
            autorizado_retirar=dados_responsavel.get("autorizado_retirar", False),
        )

        messages.success(
            self.request, f"Acolhimento de {acolhido.nome_exibicao} registrado."
        )
        return redirect("acolhidos:detalhe", pk=acolhido.pk)
```

O `@transaction.atomic` garante o tudo-ou-nada: falha na criação do vínculo
desfaz o acolhido e a ficha.

- [ ] **Step 5: Escrever o template do assistente**

`templates/acolhidos/acolhido_wizard.html`:
```html
{% extends "base.html" %}
{% block titulo %}Novo acolhimento{% endblock %}
{% block cabecalho %}Novo acolhimento{% endblock %}

{% block conteudo %}
  <div class="mb-4">
    <div class="d-flex gap-2 flex-wrap">
      {% for etapa in wizard.steps.all %}
        <span class="badge rounded-pill
              {% if etapa == wizard.steps.current %}text-bg-primary
              {% else %}text-bg-light text-muted{% endif %}">
          {{ forloop.counter }}. {{ titulos_etapa|default_if_none:"" }}{{ titulos_etapa.etapa }}
        </span>
      {% endfor %}
    </div>
    <div class="progress mt-2" style="height: 4px;">
      <div class="progress-bar"
           style="width: {% widthratio wizard.steps.step1 wizard.steps.count 100 %}%"></div>
    </div>
  </div>

  <h2 class="h5 mb-3">{{ titulo_atual }}</h2>

  <form method="post" enctype="multipart/form-data" style="max-width: 44rem;">
    {% csrf_token %}
    {{ wizard.management_form }}

    {% if form.non_field_errors %}
      <div class="alert alert-danger py-2">
        {% for erro in form.non_field_errors %}{{ erro }}{% endfor %}
      </div>
    {% endif %}

    {% for campo in form %}
      <div class="mb-3 {% if campo.field.widget.input_type == 'checkbox' %}form-check{% endif %}">
        <label for="{{ campo.id_for_label }}"
               class="{% if campo.field.widget.input_type == 'checkbox' %}form-check-label
                      {% else %}form-label{% endif %}">
          {{ campo.label }}
        </label>
        {{ campo }}
        {% if campo.help_text %}<div class="form-text">{{ campo.help_text }}</div>{% endif %}
        {% for erro in campo.errors %}
          <div class="form-text text-danger">{{ erro }}</div>
        {% endfor %}
      </div>
    {% endfor %}

    <div class="d-flex gap-2">
      {% if wizard.steps.prev %}
        <button type="submit" name="wizard_goto_step" value="{{ wizard.steps.prev }}"
                class="btn btn-outline-secondary" formnovalidate>Voltar</button>
      {% endif %}
      <button type="submit" class="btn btn-primary">
        {% if wizard.steps.current == wizard.steps.last %}Concluir cadastro{% else %}Continuar{% endif %}
      </button>
      <a href="{% url 'acolhidos:lista' %}" class="btn btn-link">Cancelar</a>
    </div>
  </form>
{% endblock %}
```

Corrigir a linha do badge, que ficou com expressão inválida — o dicionário é
acessado pela variável da iteração:
```html
          {{ forloop.counter }}. {{ titulos_etapa|get_item:etapa }}
```

Como o Django não tem filtro de acesso por chave variável, criar
`core/templatetags/__init__.py` e `core/templatetags/dicionario.py`:
```python
from django import template

register = template.Library()


@register.filter
def get_item(dicionario, chave):
    return dicionario.get(chave, chave)
```

E no topo do template: `{% load dicionario %}`.

- [ ] **Step 6: Ignorar o diretório temporário do assistente**

Acrescentar a `.gitignore`:
```
/media/_assistente/
```

- [ ] **Step 7: Rodar os testes**

```bash
pytest acolhidos/tests/test_assistente.py -v
```
Esperado: 9 testes passando.

- [ ] **Step 8: Commit**

```bash
git add acolhidos templates/acolhidos core/templatetags .gitignore
git commit -m "feat(acolhidos): adiciona assistente de acolhimento em quatro etapas"
```

---

## Task 7: Edição, vínculos familiares e desligamento

**Files:**
- Modify: `acolhidos/views.py`, `acolhidos/urls.py`, `acolhidos/forms.py`
- Create: `templates/acolhidos/acolhido_form.html`, `ficha_form.html`, `acolhido_desligar.html`, `vinculo_form.html`
- Create: `acolhidos/tests/test_desligamento.py`, `acolhidos/tests/test_vinculos.py`

**Interfaces:**
- Consumes: `core.views.BaseUpdateView` (Task 1)
- Produces: rotas `acolhidos:editar`, `acolhidos:editar_ficha`, `acolhidos:desligar`, `acolhidos:vinculo_novo`, `acolhidos:vinculo_editar`; `acolhidos.forms.DesligamentoForm`, `VinculoForm`

- [ ] **Step 1: Escrever os testes que falham**

`acolhidos/tests/test_desligamento.py`:
```python
from datetime import date, timedelta

import pytest
from django.urls import reverse

from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory
from acolhidos.models import StatusAcolhido

pytestmark = pytest.mark.django_db


@pytest.fixture
def acolhido_com_ficha():
    acolhido = AcolhidoFactory()
    FichaAcolhimentoFactory(
        acolhido=acolhido, data_entrada=date.today() - timedelta(days=200)
    )
    return acolhido


class TestAcessoAoDesligamento:
    def test_operacional_recebe_403(self, client, usuario_operacional, acolhido_com_ficha):
        client.force_login(usuario_operacional)
        url = reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk])
        assert client.get(url).status_code == 403

    def test_tecnico_acessa(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        url = reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk])
        assert client.get(url).status_code == 200


class TestDesligamento:
    def test_desligar_muda_o_status(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk]),
            {
                "data_desligamento": date.today().isoformat(),
                "destino": "REINTEGRACAO",
                "observacao": "Reintegração à família materna.",
            },
        )
        acolhido_com_ficha.refresh_from_db()
        assert acolhido_com_ficha.status == StatusAcolhido.DESLIGADO

    def test_desligar_preenche_a_ficha(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk]),
            {
                "data_desligamento": date.today().isoformat(),
                "destino": "ADOCAO",
                "observacao": "",
            },
        )
        acolhido_com_ficha.ficha.refresh_from_db()
        assert acolhido_com_ficha.ficha.data_desligamento == date.today()
        assert acolhido_com_ficha.ficha.destino == "ADOCAO"

    def test_desligado_some_da_lista_padrao(self, client, usuario_tecnico, acolhido_com_ficha):
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk]),
            {
                "data_desligamento": date.today().isoformat(),
                "destino": "MAIORIDADE",
                "observacao": "",
            },
        )
        lista = client.get(reverse("acolhidos:lista")).context["object_list"]
        assert acolhido_com_ficha not in lista

    def test_desligado_aparece_no_filtro_de_desligados(
        self, client, usuario_tecnico, acolhido_com_ficha
    ):
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk]),
            {
                "data_desligamento": date.today().isoformat(),
                "destino": "MAIORIDADE",
                "observacao": "",
            },
        )
        lista = client.get(
            reverse("acolhidos:lista") + "?situacao=DESLIGADO"
        ).context["object_list"]
        assert acolhido_com_ficha in lista

    def test_historico_e_preservado(self, client, usuario_tecnico, acolhido_com_ficha):
        """Desligamento nao apaga nada: o registro precisa continuar consultavel
        para prestacao de contas e para eventual retorno da crianca."""
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk]),
            {
                "data_desligamento": date.today().isoformat(),
                "destino": "REINTEGRACAO",
                "observacao": "",
            },
        )
        acolhido_com_ficha.refresh_from_db()
        assert acolhido_com_ficha.deleted_at is None
        assert acolhido_com_ficha.ficha.data_entrada is not None

    def test_data_de_desligamento_anterior_a_entrada_e_recusada(
        self, client, usuario_tecnico, acolhido_com_ficha
    ):
        client.force_login(usuario_tecnico)
        anterior = (acolhido_com_ficha.ficha.data_entrada - timedelta(days=1)).isoformat()
        resposta = client.post(
            reverse("acolhidos:desligar", args=[acolhido_com_ficha.pk]),
            {"data_desligamento": anterior, "destino": "ADOCAO", "observacao": ""},
        )
        assert resposta.status_code == 200
        assert "anterior à data de entrada" in resposta.content.decode()
        acolhido_com_ficha.refresh_from_db()
        assert acolhido_com_ficha.status == StatusAcolhido.ACOLHIDO
```

`acolhidos/tests/test_vinculos.py`:
```python
import pytest
from django.urls import reverse

from acolhidos.factories import AcolhidoFactory, ResponsavelFactory, VinculoFamiliarFactory
from acolhidos.models import VinculoFamiliar

pytestmark = pytest.mark.django_db


class TestVinculos:
    def test_operacional_nao_cria_vinculo(self, client, usuario_operacional):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_operacional)
        url = reverse("acolhidos:vinculo_novo", args=[acolhido.pk])
        assert client.get(url).status_code == 403

    def test_tecnico_cria_vinculo_com_responsavel_novo(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:vinculo_novo", args=[acolhido.pk]),
            {
                "responsavel": "",
                "nome_novo": "Maria Souza",
                "telefone_novo": "35999990000",
                "parentesco": "Mãe",
                "autorizado_visita": "on",
            },
        )
        vinculo = VinculoFamiliar.objects.get(acolhido=acolhido)
        assert vinculo.responsavel.nome == "Maria Souza"

    def test_tecnico_reaproveita_responsavel_existente(self, client, usuario_tecnico):
        """Irmaos acolhidos compartilham responsavel: cadastrar duas vezes
        criaria duplicata e telefone desatualizado em um dos registros."""
        mae = ResponsavelFactory(nome="Maria Souza")
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:vinculo_novo", args=[acolhido.pk]),
            {
                "responsavel": str(mae.pk),
                "nome_novo": "",
                "telefone_novo": "",
                "parentesco": "Mãe",
                "autorizado_visita": "on",
            },
        )
        assert VinculoFamiliar.objects.get(acolhido=acolhido).responsavel == mae

    def test_vinculo_duplicado_mostra_erro(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        mae = ResponsavelFactory()
        VinculoFamiliarFactory(acolhido=acolhido, responsavel=mae)
        client.force_login(usuario_tecnico)
        resposta = client.post(
            reverse("acolhidos:vinculo_novo", args=[acolhido.pk]),
            {
                "responsavel": str(mae.pk), "nome_novo": "", "telefone_novo": "",
                "parentesco": "Mãe", "autorizado_visita": "on",
            },
        )
        assert resposta.status_code == 200
        assert "já está vinculada" in resposta.content.decode()

    def test_formulario_exige_escolher_ou_cadastrar(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        resposta = client.post(
            reverse("acolhidos:vinculo_novo", args=[acolhido.pk]),
            {"responsavel": "", "nome_novo": "", "telefone_novo": "", "parentesco": "Mãe"},
        )
        assert "Escolha um responsável já cadastrado ou informe o nome" in resposta.content.decode()
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest acolhidos/tests/test_desligamento.py acolhidos/tests/test_vinculos.py -v
```
Esperado: `NoReverseMatch` para `acolhidos:vinculo_novo`.

- [ ] **Step 3: Acrescentar os formulários**

Em `acolhidos/forms.py`:
```python
from acolhidos.models import Responsavel, VinculoFamiliar

DESTINOS = [
    ("REINTEGRACAO", "Reintegração familiar"),
    ("ADOCAO", "Adoção"),
    ("MAIORIDADE", "Maioridade"),
    ("TRANSFERENCIA", "Transferência para outra instituição"),
    ("OUTRO", "Outro"),
]


class DesligamentoForm(forms.Form):
    """Desligamento e acao explicita, nao edicao de campo.

    Muda o status, preenche a ficha e preserva todo o historico.
    """

    data_desligamento = forms.DateField(
        label="Data do desligamento",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    destino = forms.ChoiceField(label="Destino", choices=DESTINOS)
    observacao = forms.CharField(
        label="Observação", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, acolhido=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acolhido = acolhido
        _aplicar_classes(self.fields)

    def clean_data_desligamento(self):
        data = self.cleaned_data["data_desligamento"]
        if data > date.today():
            raise forms.ValidationError("A data de desligamento não pode ser no futuro.")
        ficha = getattr(self.acolhido, "ficha", None)
        if ficha and data < ficha.data_entrada:
            raise forms.ValidationError(
                "A data de desligamento não pode ser anterior à data de entrada "
                f"({ficha.data_entrada:%d/%m/%Y})."
            )
        return data


class VinculoForm(forms.ModelForm):
    """Vincula um responsavel ao acolhido.

    Permite escolher alguem ja cadastrado — irmaos acolhidos compartilham
    responsavel, e duplicar o cadastro deixaria telefone desatualizado em um
    dos registros.
    """

    nome_novo = forms.CharField(label="Ou cadastre um novo", max_length=150, required=False)
    telefone_novo = forms.CharField(label="Telefone", max_length=20, required=False)

    class Meta:
        model = VinculoFamiliar
        fields = [
            "responsavel", "parentesco", "e_guardiao",
            "autorizado_visita", "autorizado_retirar", "observacoes",
        ]
        labels = {"responsavel": "Responsável já cadastrado"}

    def __init__(self, *args, acolhido=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acolhido = acolhido
        self.usuario = usuario
        self.fields["responsavel"].required = False
        self.fields["responsavel"].queryset = Responsavel.objects.all()
        _aplicar_classes(self.fields)

    def clean(self):
        dados = super().clean()
        responsavel = dados.get("responsavel")
        nome_novo = dados.get("nome_novo", "").strip()

        if not responsavel and not nome_novo:
            raise forms.ValidationError(
                "Escolha um responsável já cadastrado ou informe o nome de um novo."
            )

        if responsavel and self.acolhido:
            ja_existe = VinculoFamiliar.objects.filter(
                acolhido=self.acolhido, responsavel=responsavel
            ).exclude(pk=self.instance.pk).exists()
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
```

- [ ] **Step 4: Escrever as views**

Em `acolhidos/views.py`:
```python
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView

from acolhidos.forms import DesligamentoForm, VinculoForm
from core.views import BaseCreateView, BaseUpdateView


class AcolhidoUpdateView(BaseUpdateView):
    model = Acolhido
    form_class = EtapaIdentificacaoForm
    template_name = "acolhidos/acolhido_form.html"
    mensagem_sucesso = "Dados do acolhido atualizados."
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop("usuario", None)  # EtapaIdentificacaoForm nao recebe usuario
        return kwargs

    def get_success_url(self):
        return reverse("acolhidos:detalhe", args=[self.object.pk])


class FichaUpdateView(PerfilRequiredMixin, UpdateView):
    model = FichaAcolhimento
    form_class = EtapaAcolhimentoForm
    template_name = "acolhidos/ficha_form.html"
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO]

    def get_object(self, queryset=None):
        acolhido = get_object_or_404(Acolhido, pk=self.kwargs["pk"])
        ficha, _ = FichaAcolhimento.objects.get_or_create(
            acolhido=acolhido, defaults={"data_entrada": date.today()}
        )
        return ficha

    def form_valid(self, form):
        from accounts.models import AcaoFicha, LogAcessoFicha

        LogAcessoFicha.registrar(
            self.request.user, self.object.acolhido, AcaoFicha.EDIT
        )
        messages.success(self.request, "Ficha de acolhimento atualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("acolhidos:detalhe", args=[self.object.acolhido.pk])


class DesligamentoView(PerfilRequiredMixin, FormView):
    template_name = "acolhidos/acolhido_desligar.html"
    form_class = DesligamentoForm
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO]

    def dispatch(self, request, *args, **kwargs):
        self.acolhido = get_object_or_404(Acolhido, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"acolhido": self.acolhido}

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"acolhido": self.acolhido}

    @transaction.atomic
    def form_valid(self, form):
        from accounts.models import AcaoFicha, LogAcessoFicha

        ficha, _ = FichaAcolhimento.objects.get_or_create(
            acolhido=self.acolhido, defaults={"data_entrada": date.today()}
        )
        ficha.data_desligamento = form.cleaned_data["data_desligamento"]
        ficha.destino = form.cleaned_data["destino"]
        if form.cleaned_data.get("observacao"):
            ficha.medida_protetiva = (
                f"{ficha.medida_protetiva}\n\nDesligamento: "
                f"{form.cleaned_data['observacao']}"
            ).strip()
        ficha.save()

        self.acolhido.status = StatusAcolhido.DESLIGADO
        self.acolhido.save(update_fields=["status"])

        LogAcessoFicha.registrar(self.request.user, self.acolhido, AcaoFicha.EDIT)
        messages.success(
            self.request,
            f"Desligamento de {self.acolhido.nome_exibicao} registrado. "
            "O histórico permanece consultável.",
        )
        return redirect("acolhidos:detalhe", pk=self.acolhido.pk)


class VinculoCreateView(BaseCreateView):
    model = VinculoFamiliar
    form_class = VinculoForm
    template_name = "acolhidos/vinculo_form.html"
    mensagem_sucesso = "Vínculo familiar registrado."
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO]

    def dispatch(self, request, *args, **kwargs):
        self.acolhido = get_object_or_404(Acolhido, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"acolhido": self.acolhido}

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"acolhido": self.acolhido}

    def get_success_url(self):
        return reverse("acolhidos:detalhe", args=[self.acolhido.pk])
```

- [ ] **Step 5: Completar as URLs**

`acolhidos/urls.py`:
```python
from django.urls import path

from acolhidos import views

app_name = "acolhidos"

urlpatterns = [
    path("acolhidos/", views.AcolhidoListView.as_view(), name="lista"),
    path("acolhidos/novo/", views.AcolhimentoWizard.as_view(), name="novo"),
    path("acolhidos/<int:pk>/", views.AcolhidoDetailView.as_view(), name="detalhe"),
    path("acolhidos/<int:pk>/editar/", views.AcolhidoUpdateView.as_view(), name="editar"),
    path("acolhidos/<int:pk>/ficha/", views.FichaUpdateView.as_view(), name="editar_ficha"),
    path("acolhidos/<int:pk>/desligar/", views.DesligamentoView.as_view(), name="desligar"),
    path("acolhidos/<int:pk>/vinculo/", views.VinculoCreateView.as_view(), name="vinculo_novo"),
]
```

- [ ] **Step 6: Escrever os templates**

`templates/acolhidos/acolhido_desligar.html`:
```html
{% extends "base.html" %}
{% block titulo %}Registrar desligamento{% endblock %}
{% block cabecalho %}Registrar desligamento{% endblock %}

{% block conteudo %}
  <div class="alert alert-info">
    <strong>{{ acolhido.nome_exibicao }}</strong> deixará de constar entre os
    acolhidos ativos. O histórico completo permanece salvo e consultável pelo
    filtro <em>Desligados</em>.
  </div>

  <form method="post" style="max-width: 36rem;">
    {% csrf_token %}
    {% for campo in form %}
      <div class="mb-3">
        <label for="{{ campo.id_for_label }}" class="form-label">{{ campo.label }}</label>
        {{ campo }}
        {% for erro in campo.errors %}
          <div class="form-text text-danger">{{ erro }}</div>
        {% endfor %}
      </div>
    {% endfor %}
    <button type="submit" class="btn btn-danger">Confirmar desligamento</button>
    <a href="{% url 'acolhidos:detalhe' acolhido.pk %}" class="btn btn-link">Cancelar</a>
  </form>
{% endblock %}
```

`templates/acolhidos/acolhido_form.html`, `ficha_form.html` e `vinculo_form.html`
seguem o mesmo esqueleto de formulário, trocando título, cabeçalho e o link de
cancelamento. Escrever cada um com o conteúdo abaixo, ajustando os três pontos:

```html
{% extends "base.html" %}
{% block titulo %}TITULO{% endblock %}
{% block cabecalho %}CABECALHO{% endblock %}

{% block conteudo %}
  <form method="post" enctype="multipart/form-data" style="max-width: 40rem;">
    {% csrf_token %}
    {% if form.non_field_errors %}
      <div class="alert alert-danger py-2">
        {% for erro in form.non_field_errors %}{{ erro }}{% endfor %}
      </div>
    {% endif %}
    {% for campo in form %}
      <div class="mb-3 {% if campo.field.widget.input_type == 'checkbox' %}form-check{% endif %}">
        <label for="{{ campo.id_for_label }}"
               class="{% if campo.field.widget.input_type == 'checkbox' %}form-check-label
                      {% else %}form-label{% endif %}">{{ campo.label }}</label>
        {{ campo }}
        {% if campo.help_text %}<div class="form-text">{{ campo.help_text }}</div>{% endif %}
        {% for erro in campo.errors %}<div class="form-text text-danger">{{ erro }}</div>{% endfor %}
      </div>
    {% endfor %}
    <button type="submit" class="btn btn-primary">Salvar</button>
    <a href="LINK_CANCELAR" class="btn btn-link">Cancelar</a>
  </form>
{% endblock %}
```

Valores por arquivo:

| Arquivo | TITULO / CABECALHO | LINK_CANCELAR |
|---|---|---|
| `acolhido_form.html` | Editar acolhido | `{% url 'acolhidos:detalhe' object.pk %}` |
| `ficha_form.html` | Ficha de acolhimento | `{% url 'acolhidos:detalhe' object.acolhido.pk %}` |
| `vinculo_form.html` | Novo vínculo familiar | `{% url 'acolhidos:detalhe' acolhido.pk %}` |

- [ ] **Step 7: Acrescentar o bloco de vínculos à ficha sigilosa**

Ao fim de `templates/acolhidos/partials/_ficha_sigilosa.html`:
```html
<div class="card mb-3">
  <div class="card-header d-flex justify-content-between align-items-center">
    Responsáveis e vínculos
    <a href="{% url 'acolhidos:vinculo_novo' acolhido.pk %}"
       class="btn btn-sm btn-outline-primary">Adicionar</a>
  </div>
  <div class="card-body">
    {% for vinculo in vinculos %}
      <div class="border-bottom pb-2 mb-2">
        <div class="fw-semibold">{{ vinculo.responsavel.nome }}</div>
        <div class="text-muted small">
          {{ vinculo.parentesco }}
          {% if vinculo.responsavel.telefone %}· {{ vinculo.responsavel.telefone }}{% endif %}
        </div>
        <div class="mt-1">
          {% if vinculo.e_guardiao %}
            <span class="badge text-bg-primary">Guardião legal</span>
          {% endif %}
          {% if vinculo.autorizado_visita %}
            <span class="badge text-bg-light text-dark">Pode visitar</span>
          {% endif %}
          {% if vinculo.autorizado_retirar %}
            <span class="badge text-bg-success">Pode retirar</span>
          {% endif %}
        </div>
      </div>
    {% empty %}
      <p class="text-muted mb-0">Nenhum responsável vinculado.</p>
    {% endfor %}
  </div>
</div>
```

- [ ] **Step 8: Rodar a suíte completa**

```bash
pytest -v
```
Esperado: todos os testes da Fase 1 e da Fase 2 passando.

- [ ] **Step 9: Commit**

```bash
git add acolhidos templates/acolhidos
git commit -m "feat(acolhidos): adiciona edicao, vinculos familiares e desligamento"
```

---

## Task 8: Comando `seed_demo` e verificação final

**Files:**
- Create: `acolhidos/management/__init__.py`, `acolhidos/management/commands/__init__.py`
- Create: `acolhidos/management/commands/seed_demo.py`
- Create: `acolhidos/tests/test_seed.py`
- Modify: `acolhidos/admin.py`, `README.md`

**Interfaces:**
- Consumes: todas as factories da fase
- Produces: comando `python manage.py seed_demo`, com opção `--limpar`

- [ ] **Step 1: Escrever os testes que falham**

`acolhidos/tests/test_seed.py`:
```python
import pytest
from django.core.management import call_command

from acolhidos.models import Acolhido, FichaAcolhimento, VinculoFamiliar

pytestmark = pytest.mark.django_db


class TestSeedDemo:
    def test_cria_acolhidos(self):
        call_command("seed_demo", verbosity=0)
        assert Acolhido.objects.count() >= 8

    def test_todo_acolhido_tem_ficha(self):
        call_command("seed_demo", verbosity=0)
        assert FichaAcolhimento.objects.count() == Acolhido.objects.count()

    def test_todo_acolhido_tem_ao_menos_um_responsavel(self):
        call_command("seed_demo", verbosity=0)
        for acolhido in Acolhido.objects.all():
            assert acolhido.vinculos.exists()

    def test_cria_irmaos_com_responsavel_compartilhado(self):
        """O caso que mais quebra sistema mal modelado precisa estar nos dados
        de demonstracao."""
        call_command("seed_demo", verbosity=0)
        compartilhados = [
            r for r in VinculoFamiliar.objects.values_list("responsavel", flat=True)
        ]
        assert len(compartilhados) > len(set(compartilhados))

    def test_limpar_apaga_antes_de_recriar(self):
        call_command("seed_demo", verbosity=0)
        primeira_contagem = Acolhido.todos.count()
        call_command("seed_demo", "--limpar", verbosity=0)
        assert Acolhido.todos.count() == primeira_contagem
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest acolhidos/tests/test_seed.py -v
```
Esperado: `CommandError: Unknown command: 'seed_demo'`.

- [ ] **Step 3: Escrever o comando**

```bash
mkdir -p acolhidos/management/commands
touch acolhidos/management/__init__.py acolhidos/management/commands/__init__.py
```

`acolhidos/management/commands/seed_demo.py`:
```python
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from acolhidos.models import (
    Acolhido,
    DadosSaude,
    Escolaridade,
    FichaAcolhimento,
    Medicacao,
    Responsavel,
    Sexo,
    StatusAcolhido,
    VinculoFamiliar,
)

# Dados ficticios. Nenhum nome, processo ou endereco corresponde a pessoa real.
ACOLHIDOS = [
    ("Ana Clara Ribeiro", "", 2015, 3, 10, Sexo.FEMININO),
    ("Bruno Ribeiro", "", 2017, 7, 22, Sexo.MASCULINO),
    ("Carla Mendes", "", 2012, 11, 5, Sexo.FEMININO),
    ("Diego Alves", "", 2010, 1, 30, Sexo.MASCULINO),
    ("Eduarda Pinto", "Duda", 2014, 6, 18, Sexo.FEMININO),
    ("Felipe Castro", "", 2009, 9, 2, Sexo.MASCULINO),
    ("Gabriela Nunes", "", 2016, 4, 25, Sexo.FEMININO),
    ("Henrique Lopes", "", 2011, 12, 12, Sexo.MASCULINO),
    ("Isabela Rocha", "", 2013, 8, 8, Sexo.FEMININO),
]

MOTIVOS = [
    "Negligência familiar",
    "Situação de rua",
    "Violência doméstica",
    "Abandono",
    "Dependência química dos responsáveis",
]

ORGAOS = ["Conselho Tutelar", "Vara da Infância e Juventude", "Ministério Público"]


class Command(BaseCommand):
    help = "Popula o banco com dados fictícios coerentes para demonstração."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar", action="store_true",
            help="Apaga os dados de demonstração antes de recriar.",
        )

    @transaction.atomic
    def handle(self, *args, **opcoes):
        if opcoes["limpar"]:
            Acolhido.todos.all().delete()
            Responsavel.todos.all().delete()
            self.stdout.write("Dados anteriores removidos.")

        # Responsavel compartilhado por dois irmaos: o caso que exercita o
        # modelo de vinculo muitos-para-muitos.
        mae_ribeiro = Responsavel.objects.create(
            nome="Marta Ribeiro", telefone="35999990001",
            cidade="Itajubá", uf="MG",
        )

        for indice, (nome, social, ano, mes, dia, sexo) in enumerate(ACOLHIDOS):
            acolhido = Acolhido.objects.create(
                nome=nome,
                nome_social=social,
                nascimento=date(ano, mes, dia),
                sexo=sexo,
                naturalidade="Itajubá",
                status=StatusAcolhido.DESLIGADO if indice == 8 else StatusAcolhido.ACOLHIDO,
            )

            entrada = date.today() - timedelta(days=60 + indice * 45)
            FichaAcolhimento.objects.create(
                acolhido=acolhido,
                data_entrada=entrada,
                motivo=MOTIVOS[indice % len(MOTIVOS)],
                orgao_requisitante=ORGAOS[indice % len(ORGAOS)],
                processo_numero=f"000{1000 + indice}-56.2026.8.13.0301",
                vara="Vara da Infância e Juventude de Itajubá",
                medida_protetiva="Acolhimento institucional",
                data_desligamento=date.today() - timedelta(days=5) if indice == 8 else None,
                destino="REINTEGRACAO" if indice == 8 else "",
            )

            DadosSaude.objects.create(
                acolhido=acolhido,
                tipo_sanguineo=["O+", "A+", "B+", "AB+"][indice % 4],
                alergias="Nenhuma conhecida" if indice % 3 else "Dipirona",
            )

            Escolaridade.objects.create(
                acolhido=acolhido,
                escola="E.E. Dom Pedro II",
                serie=f"{max(1, acolhido.idade - 6)}º ano",
                turno="MANHA" if indice % 2 == 0 else "TARDE",
                ano_letivo=date.today().year,
            )

            if indice % 3 == 0:
                Medicacao.objects.create(
                    acolhido=acolhido, nome="Vitamina D", dosagem="1 gota",
                    frequencia="Manhã", inicio=entrada,
                )

            if indice < 2:
                responsavel = mae_ribeiro  # Ana Clara e Bruno sao irmaos
            else:
                responsavel = Responsavel.objects.create(
                    nome=f"Responsável de {nome.split()[0]}",
                    telefone=f"3599999{1000 + indice}",
                    cidade="Itajubá", uf="MG",
                )

            VinculoFamiliar.objects.create(
                acolhido=acolhido,
                responsavel=responsavel,
                parentesco="Mãe" if indice < 2 else "Avó",
                e_guardiao=indice % 2 == 0,
                autorizado_visita=True,
                autorizado_retirar=indice % 2 == 0,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(ACOLHIDOS)} acolhidos criados com ficha, saúde, escola e responsáveis."
            )
        )
```

- [ ] **Step 4: Registrar os models no admin**

`acolhidos/admin.py`:
```python
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from acolhidos.models import (
    Acolhido,
    DadosSaude,
    DocumentoAcolhido,
    Escolaridade,
    FichaAcolhimento,
    Medicacao,
    Responsavel,
    VinculoFamiliar,
)


class VinculoInline(admin.TabularInline):
    model = VinculoFamiliar
    extra = 0


@admin.register(Acolhido)
class AcolhidoAdmin(SimpleHistoryAdmin):
    list_display = ["nome_exibicao", "idade", "status", "criado_em"]
    list_filter = ["status", "sexo"]
    search_fields = ["nome", "nome_social"]
    inlines = [VinculoInline]


admin.site.register(
    [Responsavel, FichaAcolhimento, DadosSaude, Medicacao, Escolaridade, DocumentoAcolhido]
)
```

- [ ] **Step 5: Rodar a suíte e o lint**

```bash
pytest -v
ruff check .
ruff format --check .
```

- [ ] **Step 6: Verificação manual no navegador**

```powershell

python manage.py migrate

python manage.py seed_demo
python manage.py runserver
```

Roteiro, com um usuário de cada perfil:

1. Entrar como **Técnico** → Acolhidos → abrir "Ana Clara Ribeiro"
2. Confirmar que motivo, processo e vara aparecem
3. Sair, entrar como **Operacional** → abrir a mesma criança
4. Confirmar que motivo, processo e vara **não** aparecem, e que medicação e autorizados a retirar aparecem
5. Usar `Ctrl+U` para ver o código-fonte da página e confirmar que os dados sigilosos não estão no HTML
6. Ainda como Operacional, acessar `/acolhidos/novo/` pela barra de endereços → deve retornar 403
7. Voltar como Técnico → Novo acolhimento → percorrer as quatro etapas
8. Abrir "Bruno Ribeiro" e confirmar que Marta Ribeiro aparece como responsável dos dois irmãos
9. Registrar o desligamento de alguém e confirmar que sai da lista padrão e aparece no filtro Desligados
10. Copiar a URL de uma foto (`/media/acolhidos/fotos/...`), abrir em janela anônima → deve redirecionar ao login

Os passos 5 e 10 são os que verificam de fato o sigilo. Os demais verificam o
fluxo.

- [ ] **Step 7: Atualizar o README**

Acrescentar:
```markdown
## Dados de demonstração

```bash
python manage.py seed_demo
```

Cria nove acolhidos fictícios com ficha, saúde, escolaridade e responsáveis,
incluindo dois irmãos que compartilham a mesma responsável. Use `--limpar` para
recriar do zero.

Nenhum dado gerado corresponde a pessoa real.
```

- [ ] **Step 8: Commit**

```bash
git add acolhidos README.md
git commit -m "feat(acolhidos): adiciona comando seed_demo com dados ficticios coerentes"
```

---

## Verificação de conclusão da Fase 2

- [ ] `pytest` — suíte inteira passando
- [ ] `ruff check .` — sem apontamentos
- [ ] Roteiro manual da Task 8, com atenção aos passos 5 e 10
- [ ] `LogAcessoFicha.objects.count()` maior que zero após o roteiro

**O que a Fase 3 encontra pronto:**
- `core.views.BaseListView`, `BaseCreateView`, `BaseUpdateView`
- `core.forms.FormularioPorPerfilMixin`
- `core.storage.servir_media_protegida`
- `core.templatetags.dicionario.get_item`
- Padrão de template de lista, ficha e formulário para copiar

**Pendências desta fase, com destino:**

| Item | Fase |
|---|---|
| Relatório de acolhidos ativos e de movimentação | 5 |
| Busca global incluindo acolhidos | 5 |
| Exportação de dados por titular (LGPD) | 5 |
| Upload de documentos pela interface (hoje só pelo admin) | 5 |
