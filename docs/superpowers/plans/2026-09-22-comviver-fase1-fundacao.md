# ComViver — Fase 1: Fundação — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Colocar de pé o esqueleto do ComViver — projeto Django conectado ao PostgreSQL, autenticação com três perfis, controle de acesso reutilizável, layout base e gestão de usuários — de forma que as fases seguintes só precisem adicionar módulos de domínio.

**Architecture:** Monolito Django com apps por domínio. Nesta fase existem apenas `core` (bases abstratas e mixins, não depende de ninguém) e `accounts` (usuário, perfis, login). Todo controle de acesso é construído aqui e consumido pelas fases seguintes, nunca reimplementado.

**Tech Stack:** Python 3.12, Django 5.x, PostgreSQL (Supabase em desenvolvimento), Bootstrap 5, pytest + pytest-django + factory_boy, ruff, django-environ.

**Spec:** `docs/superpowers/specs/2026-09-22-comviver-design.md`

## Global Constraints

Valem para todas as tarefas, sem repetição em cada uma:

- Python 3.12; Django 5.x (`Django>=5.1,<6.0`).
- Banco: PostgreSQL exclusivamente. Nunca SQLite, nem em teste — divergência de comportamento entre bancos é fonte de bug que só aparece em produção.
- `.env` nunca é versionado. Apenas `.env.example`, com valores vazios. Nenhuma credencial em código, comentário, teste ou mensagem de commit.
- Toda interface, mensagem de erro e validação em português do Brasil.
- Nomes de models, campos e escolhas em português, conforme a spec §4.
- Exclusão é sempre lógica (`deleted_at`), nunca `DELETE` físico.
- Controle de acesso em três camadas (spec §5.2): view, formulário e template. Nunca apenas uma.
- `ruff` limpo antes de cada commit.
- Todo teste é escrito antes da implementação e precisa falhar primeiro, pelo motivo certo.

## Conexão com o banco

Uma única conexão, declarada em `DATABASE_URL`, usada para tudo: aplicação,
migrations e testes.

```
DATABASE_URL=postgres://USUARIO:SENHA@HOST:5432/postgres
```

**Use a conexão direta, porta 5432 — não o pooler (6543).** O transaction pooler
do Supabase não suporta cursor nomeado nem DDL longo, então `migrate` e consultas
grandes falham nele. A conexão direta atende os dois casos, e o volume de uma
instituição desse porte fica muito abaixo do limite de conexões simultâneas.

Nenhum comando precisa alternar variável de ambiente: `python manage.py migrate`
funciona direto.

---

## Estrutura de arquivos ao fim da Fase 1

```
ComViver/
├── manage.py
├── .env.example
├── .pre-commit-config.yaml
├── pyproject.toml                  # ruff + pytest
├── conftest.py                     # fixtures globais de teste
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── comviver/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                 # configuração comum
│   │   ├── dev.py                  # DEBUG, debug toolbar
│   │   ├── test.py                 # inclui testapp
│   │   └── prod.py                 # headers de segurança
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/
│   ├── models.py                   # TimeStampedModel, SoftDeleteModel, Endereco
│   ├── managers.py                 # SoftDeleteManager
│   ├── mixins.py                   # PerfilRequiredMixin
│   ├── views.py                    # PainelView
│   ├── urls.py
│   └── tests/
│       ├── test_models.py
│       └── test_mixins.py
├── accounts/
│   ├── models.py                   # Usuario
│   ├── forms.py                    # UsuarioCreationForm, UsuarioChangeForm
│   ├── views.py                    # login, troca de senha, CRUD de usuário
│   ├── urls.py
│   ├── admin.py
│   ├── factories.py                # UsuarioFactory
│   ├── migrations/0002_grupos.py   # data migration dos três perfis
│   └── tests/
│       ├── test_usuario.py
│       ├── test_grupos.py
│       ├── test_login.py
│       └── test_gestao_usuarios.py
├── tests/
│   └── testapp/                    # models concretos só para testar abstratos
│       ├── __init__.py
│       ├── apps.py
│       └── models.py
├── templates/
│   ├── base.html
│   ├── 403.html
│   ├── 404.html
│   ├── 500.html
│   ├── core/painel.html
│   └── accounts/
│       ├── login.html
│       ├── trocar_senha.html
│       ├── usuario_list.html
│       └── usuario_form.html
└── static/
    ├── css/comviver.css
    ├── img/
    └── vendor/                     # Bootstrap servido localmente, sem CDN
        ├── bootstrap.min.css
        ├── bootstrap.bundle.min.js
        ├── bootstrap-icons.css
        └── fonts/
```

**Nota sobre o Bootstrap:** os arquivos são servidos de `static/vendor/`, não de
CDN. Duas razões. Carregar script de terceiro sem verificação de integridade
significa que um comprometimento da CDN executa código arbitrário no navegador
de quem opera o sistema — e aqui esse navegador tem ficha de criança acolhida na
tela. Além disso, a instituição precisa que o sistema funcione com internet
instável, e CDN indisponível deixaria a interface sem estilo algum.

**Nota sobre `LogAcessoFicha`:** previsto na spec §4.1, mas depende do model `Acolhido`, que só existe na Fase 2. É implementado lá, junto com a view de detalhe que ele registra. Registrado aqui para não parecer esquecimento.

---

## Task 1: Projeto Django conectado ao PostgreSQL

Cria o esqueleto e prova que a conexão com o Supabase funciona. Sem isso, nada mais pode ser testado.

**Files:**
- Create: `requirements/base.txt`, `requirements/dev.txt`, `requirements/prod.txt`
- Create: `manage.py`, `comviver/__init__.py`, `comviver/urls.py`, `comviver/wsgi.py`, `comviver/asgi.py`
- Create: `comviver/settings/__init__.py`, `comviver/settings/base.py`, `comviver/settings/dev.py`, `comviver/settings/prod.py`
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Consumes: nada
- Produces: pacote `comviver.settings.base` com `INSTALLED_APPS`, `DATABASES`, `TEMPLATES`, `AUTH_USER_MODEL` (definido na Task 4); conexão única lida de `DATABASE_URL`

- [ ] **Step 1: Criar ambiente virtual e arquivos de dependência**

```bash
python -m venv .venv
```

PowerShell: `.\.venv\Scripts\Activate.ps1`

`requirements/base.txt`:
```
Django>=5.1,<6.0
psycopg[binary]>=3.2,<4.0
django-environ>=0.11,<1.0
whitenoise>=6.7,<7.0
```

`requirements/dev.txt`:
```
-r base.txt
pytest>=8.0
pytest-django>=4.9
factory-boy>=3.3
django-debug-toolbar>=4.4
ruff>=0.6
pre-commit>=3.8
```

`requirements/prod.txt`:
```
-r base.txt
gunicorn>=23.0
```

```bash
pip install -r requirements/dev.txt
```

- [ ] **Step 2: Gerar o esqueleto do projeto**

```bash
django-admin startproject comviver .
```

Isso cria `manage.py` e `comviver/` com `settings.py` único. Transformar em pacote:

```bash
mkdir comviver/settings
git mv comviver/settings.py comviver/settings/base.py 2>/dev/null || mv comviver/settings.py comviver/settings/base.py
touch comviver/settings/__init__.py
```

Em `manage.py`, `comviver/wsgi.py` e `comviver/asgi.py`, trocar `"comviver.settings"` por `"comviver.settings.dev"`.

- [ ] **Step 3: Escrever `comviver/settings/base.py`**

```python
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "comviver.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "comviver.wsgi.application"

# Conexao direta (porta 5432), usada pela aplicacao, pelas migrations e pelos
# testes. O transaction pooler do Supabase nao suporta DDL longo nem cursor
# nomeado, entao nao serve como conexao unica.
DATABASES = {
    "default": {
        **env.db_url_config(env("DATABASE_URL")),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": "require"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:painel"
LOGOUT_REDIRECT_URL = "accounts:login"

# Computador compartilhado na recepcao: sessao expira por inatividade e ao
# fechar o navegador. Sem a segunda regra, quem fechasse a aba sem sair
# deixaria a sessao viva para a proxima pessoa que sentasse na maquina.
SESSION_COOKIE_AGE = 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Nao vaza o endereco da ficha aberta para sites externos pelo cabecalho
# Referer — uma URL como /acolhidos/12/ ja e informacao.
SECURE_REFERRER_POLICY = "same-origin"

# Limita o tamanho do corpo da requisicao. O limite por arquivo esta em
# core.uploads; este cobre o total enviado de uma vez.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 500
```

- [ ] **Step 4: Escrever `dev.py` e `prod.py`**

`comviver/settings/dev.py`:
```python
from .base import *  # noqa: F403

DEBUG = True
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]
```

`comviver/settings/prod.py`:
```python
from .base import *  # noqa: F403

DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Origens autorizadas a enviar formulario. Sem isso, o Django recusa POST
# vindo do proprio dominio quando ha proxy HTTPS na frente.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

# Falha cedo: DEBUG ligado em producao exibiria a senha do banco na pagina de
# erro, e SECRET_KEY de exemplo invalidaria toda sessao e token CSRF.
if DEBUG:
    raise RuntimeError("DEBUG não pode estar ligado em produção.")
if not ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError("Defina ALLOWED_HOSTS antes de publicar.")
```

Acrescentar a variável ao `.env.example`:
```
# Apenas em producao. Ex.: https://comviver.exemplo.org
CSRF_TRUSTED_ORIGINS=
```

- [ ] **Step 5: Escrever `.env.example`**

```
# Copie para .env e preencha. O arquivo .env NAO vai para o Git.
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Conexao direta com o banco, porta 5432. Nao use o pooler (6543):
# ele nao suporta migrations nem consultas grandes.
DATABASE_URL=postgres://USUARIO:SENHA@HOST:5432/postgres
```

Criar o `.env` real localmente com os valores do Supabase. Gerar a chave:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

- [ ] **Step 6: Verificar a configuração e a conexão**

```bash
python manage.py check
```
Esperado: `System check identified no issues (0 silenced).`

```bash
python manage.py migrate
```
Esperado: as migrations do Django (`auth`, `contenttypes`, `sessions`, `admin`) aplicam sem erro.

Se aparecer `SSL connection has been closed unexpectedly` ou
`prepared statement already exists`, a `DATABASE_URL` está apontando para o
pooler. Troque para a conexão direta, porta 5432.

- [ ] **Step 7: Escrever o `README.md`**

```markdown
# ComViver

Sistema de gestão administrativa do Lar Padre José Gumercindo.

## Requisitos

- Python 3.12
- Acesso a um banco PostgreSQL

## Instalação

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # PowerShell
pip install -r requirements/dev.txt
cp .env.example .env
```

Preencha o `.env` com as credenciais do banco e uma `SECRET_KEY` gerada por:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

A `DATABASE_URL` precisa apontar para a **conexão direta** do PostgreSQL
(porta 5432). O pooler em modo transação não suporta migrations.

## Migrations

```bash
python manage.py migrate
```

## Executar

```bash
python manage.py runserver
```

## Testes

```bash
pytest
```
```

- [ ] **Step 8: Commit**

```bash
git add requirements manage.py comviver .env.example README.md
git commit -m "feat: estrutura inicial do projeto Django com conexao PostgreSQL"
```

Confirmar que `.env` **não** entrou: `git status --short` não deve listá-lo.

---

## Task 2: Infraestrutura de testes e padronização

Sem isto, nenhuma tarefa seguinte pode ser feita com TDD.

**Files:**
- Create: `pyproject.toml`, `conftest.py`, `.pre-commit-config.yaml`
- Create: `comviver/settings/test.py`
- Create: `tests/__init__.py`, `tests/testapp/__init__.py`, `tests/testapp/apps.py`, `tests/testapp/models.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: `comviver.settings.base` (Task 1)
- Produces: comando `pytest` funcionando; app `tests.testapp` disponível apenas em teste, para instanciar models abstratos

- [ ] **Step 1: Escrever `pyproject.toml`**

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "comviver.settings.test"
python_files = ["test_*.py"]
addopts = "--reuse-db -q"

[tool.ruff]
line-length = 100
target-version = "py312"
exclude = ["migrations", ".venv"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "DJ", "B"]

[tool.ruff.lint.per-file-ignores]
"comviver/settings/*.py" = ["F403", "F405"]
```

`--reuse-db` importa: o banco de desenvolvimento é remoto, e recriar o banco de teste a cada execução torna a suíte lenta demais para o ciclo de TDD. Quando um model mudar, rodar uma vez com `--create-db`.

- [ ] **Step 2: Criar o app de teste para models abstratos**

`core` define models abstratos, que não geram tabela. Para testá-los é preciso um model concreto que exista apenas em teste.

`tests/__init__.py` — vazio.
`tests/testapp/__init__.py` — vazio.

`tests/testapp/apps.py`:
```python
from django.apps import AppConfig


class TestAppConfig(AppConfig):
    name = "tests.testapp"
    label = "testapp"
```

`tests/testapp/models.py`:
```python
from django.db import models

from core.models import Endereco, SoftDeleteModel, TimeStampedModel


class ModeloDatado(TimeStampedModel):
    """Model concreto usado apenas para testar TimeStampedModel."""

    nome = models.CharField(max_length=50)


class ModeloExcluivel(SoftDeleteModel):
    """Model concreto usado apenas para testar SoftDeleteModel."""

    nome = models.CharField(max_length=50)


class ModeloComEndereco(Endereco):
    """Model concreto usado apenas para testar Endereco."""

    nome = models.CharField(max_length=50)
```

Estes models importam de `core.models`, criado na Task 3. Até lá a suíte não roda — esperado, e o motivo de a Task 3 vir logo em seguida.

- [ ] **Step 3: Escrever `comviver/settings/test.py`**

```python
import sys

from .base import *  # noqa: F403

# Este settings so pode ser carregado pela suite de testes. Sem a trava, um
# erro de digitacao no DJANGO_SETTINGS_MODULE do servidor colocaria o sistema
# no ar com hash de senha em MD5 e bloqueio de login desativado.
if "pytest" not in sys.modules:
    raise RuntimeError(
        "comviver.settings.test é exclusivo da suíte de testes. "
        "Use comviver.settings.dev ou comviver.settings.prod."
    )

INSTALLED_APPS += ["tests.testapp"]  # noqa: F405

# Hash rapido: a suite cria muitos usuarios e o hasher padrao domina o tempo.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
```

O hasher fraco vale apenas em teste, onde não há senha real. Nunca em `base.py`.

- [ ] **Step 4: Escrever `conftest.py`**

```python
import pytest


@pytest.fixture
def cliente_anonimo(client):
    """Cliente HTTP sem autenticacao."""
    return client
```

Fixtures por perfil entram na Task 4, quando o model `Usuario` existir.

- [ ] **Step 5: Escrever o teste de fumaça**

`tests/test_smoke.py`:
```python
import pytest
from django.db import connection


@pytest.mark.django_db
def test_conexao_com_banco_funciona():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
```

- [ ] **Step 6: Configurar o pre-commit**

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key
```

```bash
pre-commit install
```

`detect-private-key` é rede de proteção contra commit acidental de credencial.

- [ ] **Step 7: Rodar a suíte**

```bash
pytest tests/test_smoke.py -v
```
Esperado: **FALHA** com `ModuleNotFoundError: No module named 'core.models'` — `tests/testapp/models.py` importa de `core`, que ainda não existe. Confirma que o app de teste está sendo carregado.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml conftest.py .pre-commit-config.yaml comviver/settings/test.py tests
git commit -m "chore: configura pytest, ruff e pre-commit"
```

---

## Task 3: Models abstratos do `core`

**Files:**
- Create: `core/__init__.py`, `core/apps.py`, `core/models.py`, `core/managers.py`
- Create: `core/tests/__init__.py`, `core/tests/test_models.py`

**Interfaces:**
- Consumes: `tests.testapp` (Task 2)
- Produces:
  - `core.models.TimeStampedModel` — abstrato, campos `criado_em: DateTimeField`, `atualizado_em: DateTimeField`
  - `core.models.SoftDeleteModel` — abstrato, campo `deleted_at: DateTimeField | None`, método `delete(self, *args, **kwargs) -> None` (lógico), `restaurar(self) -> None`, managers `objects` (ativos) e `todos` (inclusive excluídos)
  - `core.models.Endereco` — abstrato, campos `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`
  - `core.managers.SoftDeleteManager`

- [ ] **Step 1: Escrever os testes que falham**

`core/tests/__init__.py` — vazio.

`core/tests/test_models.py`:
```python
import pytest
from django.utils import timezone

from tests.testapp.models import ModeloComEndereco, ModeloDatado, ModeloExcluivel

pytestmark = pytest.mark.django_db


class TestTimeStampedModel:
    def test_preenche_criado_em_ao_salvar(self):
        antes = timezone.now()
        obj = ModeloDatado.objects.create(nome="teste")
        assert antes <= obj.criado_em <= timezone.now()

    def test_atualiza_atualizado_em_ao_salvar_de_novo(self):
        obj = ModeloDatado.objects.create(nome="teste")
        primeiro = obj.atualizado_em
        obj.nome = "alterado"
        obj.save()
        obj.refresh_from_db()
        assert obj.atualizado_em > primeiro


class TestSoftDeleteModel:
    def test_delete_nao_remove_a_linha_do_banco(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        pk = obj.pk
        obj.delete()
        assert ModeloExcluivel.todos.filter(pk=pk).exists()

    def test_delete_preenche_deleted_at(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        obj.delete()
        obj.refresh_from_db()
        assert obj.deleted_at is not None

    def test_excluido_some_do_manager_padrao(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        obj.delete()
        assert not ModeloExcluivel.objects.filter(pk=obj.pk).exists()

    def test_manager_todos_enxerga_o_excluido(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        obj.delete()
        assert ModeloExcluivel.todos.filter(pk=obj.pk).exists()

    def test_restaurar_traz_de_volta(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        obj.delete()
        obj.restaurar()
        assert ModeloExcluivel.objects.filter(pk=obj.pk).exists()


class TestEndereco:
    def test_endereco_formatado_monta_a_linha_completa(self):
        obj = ModeloComEndereco.objects.create(
            nome="teste",
            cep="37500-000",
            logradouro="Rua das Flores",
            numero="123",
            bairro="Centro",
            cidade="Itajubá",
            uf="MG",
        )
        assert obj.endereco_formatado == "Rua das Flores, 123 - Centro, Itajubá/MG"

    def test_endereco_formatado_vazio_quando_sem_logradouro(self):
        obj = ModeloComEndereco.objects.create(nome="teste")
        assert obj.endereco_formatado == ""
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_models.py -v
```
Esperado: `ModuleNotFoundError: No module named 'core.models'`.

- [ ] **Step 3: Escrever `core/managers.py`**

```python
from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        from django.utils import timezone

        return self.update(deleted_at=timezone.now())


class SoftDeleteManager(models.Manager):
    """Manager padrao: enxerga apenas registros nao excluidos."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class TodosManager(models.Manager):
    """Manager alternativo: enxerga inclusive os excluidos logicamente."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)
```

- [ ] **Step 4: Escrever `core/models.py`**

```python
from django.db import models
from django.utils import timezone

from core.managers import SoftDeleteManager, TodosManager


class TimeStampedModel(models.Model):
    """Registra quando o objeto foi criado e alterado pela ultima vez."""

    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    """Exclusao logica.

    Prestacao de contas e historico de acolhimento nao podem ter lacuna, e
    usuario leigo aciona exclusao por engano. A linha permanece no banco.
    """

    deleted_at = models.DateTimeField("excluido em", null=True, blank=True, editable=False)

    objects = SoftDeleteManager()
    todos = TodosManager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restaurar(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    @property
    def excluido(self) -> bool:
        return self.deleted_at is not None


class Endereco(models.Model):
    """Campos de endereco, reaproveitados por acolhidos, doadores e voluntarios."""

    UF_CHOICES = [
        ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"), ("AM", "Amazonas"),
        ("BA", "Bahia"), ("CE", "Ceará"), ("DF", "Distrito Federal"),
        ("ES", "Espírito Santo"), ("GO", "Goiás"), ("MA", "Maranhão"),
        ("MT", "Mato Grosso"), ("MS", "Mato Grosso do Sul"), ("MG", "Minas Gerais"),
        ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"), ("PE", "Pernambuco"),
        ("PI", "Piauí"), ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"),
        ("RS", "Rio Grande do Sul"), ("RO", "Rondônia"), ("RR", "Roraima"),
        ("SC", "Santa Catarina"), ("SP", "São Paulo"), ("SE", "Sergipe"),
        ("TO", "Tocantins"),
    ]

    cep = models.CharField("CEP", max_length=9, blank=True)
    logradouro = models.CharField("logradouro", max_length=150, blank=True)
    numero = models.CharField("número", max_length=10, blank=True)
    complemento = models.CharField("complemento", max_length=50, blank=True)
    bairro = models.CharField("bairro", max_length=80, blank=True)
    cidade = models.CharField("cidade", max_length=80, blank=True)
    uf = models.CharField("UF", max_length=2, choices=UF_CHOICES, blank=True)

    class Meta:
        abstract = True

    @property
    def endereco_formatado(self) -> str:
        if not self.logradouro:
            return ""
        return f"{self.logradouro}, {self.numero} - {self.bairro}, {self.cidade}/{self.uf}"
```

- [ ] **Step 5: Criar `core/apps.py`**

`core/__init__.py` — vazio.

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "Núcleo"
```

- [ ] **Step 6: Rodar os testes**

```bash
pytest core/tests/test_models.py -v --create-db
```
Esperado: 9 testes passando. `--create-db` é necessário porque as tabelas de `testapp` são novas.

- [ ] **Step 7: Commit**

```bash
git add core tests/testapp
git commit -m "feat(core): adiciona models abstratos com exclusao logica"
```

---

## Task 4: Model `Usuario` com perfis

Precisa vir antes de qualquer model de domínio: trocar `AUTH_USER_MODEL` depois que existirem migrations é custoso.

**Files:**
- Create: `accounts/__init__.py`, `accounts/apps.py`, `accounts/models.py`, `accounts/factories.py`, `accounts/admin.py`
- Create: `accounts/tests/__init__.py`, `accounts/tests/test_usuario.py`
- Modify: `comviver/settings/base.py` (adicionar `AUTH_USER_MODEL`)
- Modify: `conftest.py` (fixtures por perfil)

**Interfaces:**
- Consumes: `core.models.TimeStampedModel` (Task 3)
- Produces:
  - `accounts.models.Perfil` — `TextChoices` com `ADMIN`, `TECNICO`, `OPERACIONAL`
  - `accounts.models.Usuario` — campos `perfil: str`, `telefone: str`, `precisa_trocar_senha: bool`; propriedades `e_admin`, `e_tecnico`, `e_operacional`; método `pode_ver_ficha_completa() -> bool`
  - `accounts.factories.UsuarioFactory`
  - fixtures `usuario_admin`, `usuario_tecnico`, `usuario_operacional`

- [ ] **Step 1: Escrever os testes que falham**

`accounts/tests/__init__.py` — vazio.

`accounts/tests/test_usuario.py`:
```python
import pytest

from accounts.models import Perfil, Usuario

pytestmark = pytest.mark.django_db


class TestUsuario:
    def test_cria_usuario_com_perfil(self):
        usuario = Usuario.objects.create_user(
            username="maria", password="senha-forte-123", perfil=Perfil.TECNICO
        )
        assert usuario.perfil == Perfil.TECNICO

    def test_perfil_padrao_e_operacional(self):
        usuario = Usuario.objects.create_user(username="joao", password="senha-forte-123")
        assert usuario.perfil == Perfil.OPERACIONAL

    def test_str_mostra_nome_e_perfil(self):
        usuario = Usuario.objects.create_user(
            username="maria", first_name="Maria", last_name="Silva",
            password="senha-forte-123", perfil=Perfil.ADMIN,
        )
        assert str(usuario) == "Maria Silva (Administrador)"

    def test_str_usa_username_quando_sem_nome(self):
        usuario = Usuario.objects.create_user(
            username="maria", password="senha-forte-123", perfil=Perfil.ADMIN
        )
        assert str(usuario) == "maria (Administrador)"

    @pytest.mark.parametrize(
        "perfil,e_admin,e_tecnico,e_operacional",
        [
            (Perfil.ADMIN, True, False, False),
            (Perfil.TECNICO, False, True, False),
            (Perfil.OPERACIONAL, False, False, True),
        ],
    )
    def test_propriedades_de_perfil(self, perfil, e_admin, e_tecnico, e_operacional):
        usuario = Usuario.objects.create_user(
            username="teste", password="senha-forte-123", perfil=perfil
        )
        assert usuario.e_admin is e_admin
        assert usuario.e_tecnico is e_tecnico
        assert usuario.e_operacional is e_operacional

    @pytest.mark.parametrize(
        "perfil,esperado",
        [(Perfil.ADMIN, True), (Perfil.TECNICO, True), (Perfil.OPERACIONAL, False)],
    )
    def test_pode_ver_ficha_completa(self, perfil, esperado):
        """Sigilo do art. 143 do ECA: Operacional nao acessa ficha completa."""
        usuario = Usuario.objects.create_user(
            username="teste", password="senha-forte-123", perfil=perfil
        )
        assert usuario.pode_ver_ficha_completa() is esperado

    def test_usuario_novo_precisa_trocar_senha(self):
        usuario = Usuario.objects.create_user(username="novo", password="senha-forte-123")
        assert usuario.precisa_trocar_senha is True

    def test_superusuario_nao_precisa_trocar_senha(self):
        usuario = Usuario.objects.create_superuser(username="root", password="senha-forte-123")
        assert usuario.precisa_trocar_senha is False
        assert usuario.perfil == Perfil.ADMIN
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest accounts/tests/test_usuario.py -v
```
Esperado: `ModuleNotFoundError: No module named 'accounts.models'`.

- [ ] **Step 3: Escrever `accounts/models.py`**

`accounts/__init__.py` — vazio.

```python
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Perfil(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    TECNICO = "TECNICO", "Técnico"
    OPERACIONAL = "OPERACIONAL", "Operacional"


class UsuarioManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("perfil", Perfil.ADMIN)
        extra_fields.setdefault("precisa_trocar_senha", False)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """Usuario do sistema.

    O campo `perfil` determina o que a pessoa enxerga. O recorte entre TECNICO e
    OPERACIONAL existe por causa do art. 143 do ECA: quem trabalha na recepcao
    nao pode acessar dado que identifique a situacao do acolhido.
    """

    perfil = models.CharField(
        "perfil", max_length=15, choices=Perfil.choices, default=Perfil.OPERACIONAL
    )
    telefone = models.CharField("telefone", max_length=20, blank=True)
    precisa_trocar_senha = models.BooleanField(
        "precisa trocar a senha", default=True,
        help_text="Marcado para usuario novo; desmarcado apos a primeira troca.",
    )

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["first_name", "username"]

    def __str__(self) -> str:
        nome = self.get_full_name() or self.username
        return f"{nome} ({self.get_perfil_display()})"

    @property
    def e_admin(self) -> bool:
        return self.perfil == Perfil.ADMIN

    @property
    def e_tecnico(self) -> bool:
        return self.perfil == Perfil.TECNICO

    @property
    def e_operacional(self) -> bool:
        return self.perfil == Perfil.OPERACIONAL

    def pode_ver_ficha_completa(self) -> bool:
        """Ficha de acolhimento, situacao juridica e dados de saude."""
        return self.perfil in {Perfil.ADMIN, Perfil.TECNICO}

    def pode_gerenciar_usuarios(self) -> bool:
        return self.e_admin
```

`accounts/apps.py`:
```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"
    verbose_name = "Contas e acesso"
```

- [ ] **Step 4: Apontar `AUTH_USER_MODEL` e gerar a migration**

Em `comviver/settings/base.py`, após `DEFAULT_AUTO_FIELD`:
```python
AUTH_USER_MODEL = "accounts.Usuario"
```

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

Se o banco já tiver tabelas de `auth` da Task 1, o Django recusa a troca de usuário. Nesse caso, zerar o banco de desenvolvimento — não há dado real ainda:

```bash
python manage.py migrate accounts zero
# se persistir, apagar o schema public pelo painel do Supabase e rodar migrate de novo
```

- [ ] **Step 5: Escrever a factory e as fixtures**

`accounts/factories.py`:
```python
import factory

from accounts.models import Perfil, Usuario


class UsuarioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Usuario
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"usuario{n}")
    first_name = factory.Faker("first_name", locale="pt_BR")
    last_name = factory.Faker("last_name", locale="pt_BR")
    email = factory.LazyAttribute(lambda o: f"{o.username}@exemplo.org")
    perfil = Perfil.OPERACIONAL
    precisa_trocar_senha = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if create:
            obj.set_password(extracted or "senha-de-teste-123")
            obj.save()
```

Acrescentar a `conftest.py`:
```python
import pytest

from accounts.factories import UsuarioFactory
from accounts.models import Perfil


@pytest.fixture
def cliente_anonimo(client):
    """Cliente HTTP sem autenticacao."""
    return client


@pytest.fixture
def usuario_admin(db):
    return UsuarioFactory(perfil=Perfil.ADMIN)


@pytest.fixture
def usuario_tecnico(db):
    return UsuarioFactory(perfil=Perfil.TECNICO)


@pytest.fixture
def usuario_operacional(db):
    return UsuarioFactory(perfil=Perfil.OPERACIONAL)
```

- [ ] **Step 6: Registrar no admin**

`accounts/admin.py`:
```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ["username", "first_name", "last_name", "perfil", "is_active"]
    list_filter = ["perfil", "is_active"]
    fieldsets = UserAdmin.fieldsets + (
        ("ComViver", {"fields": ("perfil", "telefone", "precisa_trocar_senha")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("ComViver", {"fields": ("perfil", "telefone")}),
    )
```

O admin fica restrito ao superusuário, para manutenção. O usuário final nunca o acessa (spec §2).

- [ ] **Step 7: Rodar os testes**

```bash
pytest accounts/tests/test_usuario.py -v --create-db
```
Esperado: 12 testes passando.

- [ ] **Step 8: Commit**

```bash
git add accounts conftest.py comviver/settings/base.py
git commit -m "feat(accounts): adiciona Usuario customizado com tres perfis"
```

---

## Task 5: Grupos de permissão por migration de dados

Os grupos precisam existir em qualquer instalação, inclusive na hospedagem futura. Criar à mão no admin não é reproduzível.

**Files:**
- Create: `accounts/migrations/0002_grupos.py`
- Create: `accounts/tests/test_grupos.py`

**Interfaces:**
- Consumes: `accounts.models.Perfil` (Task 4)
- Produces: grupos `Administrador`, `Técnico` e `Operacional` no banco; função `accounts.models.Usuario.sincronizar_grupo(self) -> None`

- [ ] **Step 1: Escrever os testes que falham**

`accounts/tests/test_grupos.py`:
```python
import pytest
from django.contrib.auth.models import Group

from accounts.factories import UsuarioFactory
from accounts.models import Perfil

pytestmark = pytest.mark.django_db


class TestGrupos:
    def test_os_tres_grupos_existem(self):
        nomes = set(Group.objects.values_list("name", flat=True))
        assert {"Administrador", "Técnico", "Operacional"} <= nomes

    @pytest.mark.parametrize(
        "perfil,grupo",
        [
            (Perfil.ADMIN, "Administrador"),
            (Perfil.TECNICO, "Técnico"),
            (Perfil.OPERACIONAL, "Operacional"),
        ],
    )
    def test_usuario_entra_no_grupo_do_seu_perfil(self, perfil, grupo):
        usuario = UsuarioFactory(perfil=perfil)
        assert usuario.groups.filter(name=grupo).exists()

    def test_trocar_perfil_troca_de_grupo(self):
        usuario = UsuarioFactory(perfil=Perfil.OPERACIONAL)
        usuario.perfil = Perfil.TECNICO
        usuario.save()
        assert usuario.groups.filter(name="Técnico").exists()
        assert not usuario.groups.filter(name="Operacional").exists()

    def test_usuario_pertence_a_exatamente_um_grupo(self):
        usuario = UsuarioFactory(perfil=Perfil.ADMIN)
        assert usuario.groups.count() == 1
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest accounts/tests/test_grupos.py -v
```
Esperado: `AssertionError` no primeiro teste — os grupos não existem.

- [ ] **Step 3: Escrever a migration de dados**

`accounts/migrations/0002_grupos.py`:
```python
from django.db import migrations

GRUPOS = ["Administrador", "Técnico", "Operacional"]


def criar_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nome in GRUPOS:
        Group.objects.get_or_create(name=nome)


def remover_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GRUPOS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(criar_grupos, remover_grupos)]
```

- [ ] **Step 4: Sincronizar grupo com perfil no `save()`**

Acrescentar a `accounts/models.py`, dentro da classe `Usuario`:

```python
    GRUPO_POR_PERFIL = {
        Perfil.ADMIN: "Administrador",
        Perfil.TECNICO: "Técnico",
        Perfil.OPERACIONAL: "Operacional",
    }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sincronizar_grupo()

    def sincronizar_grupo(self) -> None:
        """Mantem o usuario em exatamente um grupo, o do seu perfil."""
        from django.contrib.auth.models import Group

        grupo, _ = Group.objects.get_or_create(name=self.GRUPO_POR_PERFIL[self.perfil])
        self.groups.set([grupo])
```

O `get_or_create` evita quebra em banco de teste criado antes da migration rodar.

- [ ] **Step 5: Aplicar a migration e rodar os testes**

```bash
python manage.py migrate
```

```bash
pytest accounts/tests/ -v --create-db
```
Esperado: todos passando (12 da Task 4 + 6 desta).

- [ ] **Step 6: Commit**

```bash
git add accounts
git commit -m "feat(accounts): cria grupos por migration e sincroniza com o perfil"
```

---

## Task 6: `PerfilRequiredMixin` — a porta das views

Primeira das três camadas de controle de acesso (spec §5.2). Consumido por todas as fases seguintes.

**Files:**
- Create: `core/mixins.py`
- Create: `core/tests/test_mixins.py`

**Interfaces:**
- Consumes: `accounts.models.Perfil` (Task 4)
- Produces: `core.mixins.PerfilRequiredMixin`, com atributo de classe `perfis_permitidos: list[str]`. Usuário não autenticado é redirecionado ao login; autenticado sem o perfil recebe `PermissionDenied` (403).

- [ ] **Step 1: Escrever os testes que falham**

`core/tests/test_mixins.py`:
```python
import pytest
from django.http import HttpResponse
from django.urls import path
from django.views.generic import View

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin


class ViewSoTecnico(PerfilRequiredMixin, View):
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO]

    def get(self, request):
        return HttpResponse("ok")


urlpatterns = [path("so-tecnico/", ViewSoTecnico.as_view(), name="so-tecnico")]

pytestmark = [pytest.mark.django_db, pytest.mark.urls(__name__)]


class TestPerfilRequiredMixin:
    def test_anonimo_vai_para_o_login(self, client):
        resposta = client.get("/so-tecnico/")
        assert resposta.status_code == 302
        assert "/entrar/" in resposta.url

    def test_admin_entra(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get("/so-tecnico/").status_code == 200

    def test_tecnico_entra(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        assert client.get("/so-tecnico/").status_code == 200

    def test_operacional_recebe_403(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get("/so-tecnico/").status_code == 403

    def test_view_sem_perfis_declarados_falha_ao_ser_usada(self, usuario_admin):
        """Esquecer de declarar perfis_permitidos nao pode liberar acesso."""
        from django.core.exceptions import ImproperlyConfigured
        from django.test import RequestFactory

        class ViewSemDeclaracao(PerfilRequiredMixin, View):
            def get(self, request):
                return HttpResponse("ok")

        requisicao = RequestFactory().get("/qualquer/")
        requisicao.user = usuario_admin

        with pytest.raises(ImproperlyConfigured):
            ViewSemDeclaracao.as_view()(requisicao)
```

O último teste é o mais importante: garante que esquecer a declaração produz erro em vez de acesso liberado. Falha fechada, não aberta.

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_mixins.py -v
```
Esperado: `ModuleNotFoundError: No module named 'core.mixins'`.

- [ ] **Step 3: Escrever `core/mixins.py`**

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied


class PerfilRequiredMixin(LoginRequiredMixin):
    """Restringe a view aos perfis declarados em `perfis_permitidos`.

    Primeira das tres camadas de controle de acesso (spec 5.2). As outras duas
    sao o formulario, que nao monta o campo restrito, e o template, que nao o
    renderiza.

    Omitir `perfis_permitidos` levanta ImproperlyConfigured: esquecer a
    declaracao tem de quebrar, nunca liberar acesso.
    """

    perfis_permitidos: list[str] | None = None

    def dispatch(self, request, *args, **kwargs):
        if self.perfis_permitidos is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} precisa declarar `perfis_permitidos`."
            )
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.perfil not in self.perfis_permitidos:
            raise PermissionDenied("Seu perfil não tem acesso a esta página.")
        return super().dispatch(request, *args, **kwargs)
```

- [ ] **Step 4: Rodar os testes**

```bash
pytest core/tests/test_mixins.py -v
```
Esperado: 5 testes passando.

O teste do anônimo depende da URL de login `/entrar/`, criada na Task 7. Até lá ele falha no `assert "/entrar/" in resposta.url` — registrado aqui de propósito, e resolvido na tarefa seguinte.

- [ ] **Step 5: Commit**

```bash
git add core/mixins.py core/tests/test_mixins.py
git commit -m "feat(core): adiciona PerfilRequiredMixin com falha fechada"
```

---

## Task 7: Login, logout e troca de senha no primeiro acesso

**Files:**
- Create: `accounts/views.py`, `accounts/urls.py`, `accounts/forms.py`
- Create: `templates/accounts/login.html`, `templates/accounts/trocar_senha.html`
- Create: `accounts/middleware.py`
- Create: `accounts/tests/test_login.py`
- Modify: `comviver/urls.py`, `comviver/settings/base.py` (middleware)

**Interfaces:**
- Consumes: `accounts.models.Usuario` (Task 4)
- Produces: rotas nomeadas `accounts:login`, `accounts:logout`, `accounts:trocar_senha`; `accounts.middleware.TrocaSenhaObrigatoriaMiddleware`

- [ ] **Step 1: Escrever os testes que falham**

`accounts/tests/test_login.py`:
```python
import pytest
from django.urls import reverse

from accounts.factories import UsuarioFactory

pytestmark = pytest.mark.django_db


class TestLogin:
    def test_pagina_de_login_abre(self, client):
        assert client.get(reverse("accounts:login")).status_code == 200

    def test_login_com_credenciais_corretas_leva_ao_painel(self, client):
        UsuarioFactory(username="maria", password="senha-de-teste-123")
        resposta = client.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "senha-de-teste-123"},
        )
        assert resposta.status_code == 302
        assert resposta.url == reverse("core:painel")

    def test_login_com_senha_errada_mostra_erro_em_portugues(self, client):
        UsuarioFactory(username="maria", password="senha-de-teste-123")
        resposta = client.post(
            reverse("accounts:login"), {"username": "maria", "password": "errada"}
        )
        assert resposta.status_code == 200
        assert "Usuário ou senha incorretos." in resposta.content.decode()

    def test_usuario_inativo_nao_entra(self, client):
        UsuarioFactory(username="maria", password="senha-de-teste-123", is_active=False)
        resposta = client.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "senha-de-teste-123"},
        )
        assert resposta.status_code == 200

    def test_logout_encerra_a_sessao(self, client, usuario_admin):
        client.force_login(usuario_admin)
        client.post(reverse("accounts:logout"))
        assert client.get(reverse("core:painel")).status_code == 302


class TestTrocaSenhaObrigatoria:
    def test_usuario_novo_e_desviado_para_a_troca(self, client):
        usuario = UsuarioFactory(password="senha-de-teste-123", precisa_trocar_senha=True)
        client.force_login(usuario)
        resposta = client.get(reverse("core:painel"))
        assert resposta.status_code == 302
        assert resposta.url == reverse("accounts:trocar_senha")

    def test_pode_abrir_a_propria_pagina_de_troca(self, client):
        usuario = UsuarioFactory(password="senha-de-teste-123", precisa_trocar_senha=True)
        client.force_login(usuario)
        assert client.get(reverse("accounts:trocar_senha")).status_code == 200

    def test_trocar_a_senha_libera_o_sistema(self, client):
        usuario = UsuarioFactory(password="senha-de-teste-123", precisa_trocar_senha=True)
        client.force_login(usuario)
        client.post(
            reverse("accounts:trocar_senha"),
            {
                "old_password": "senha-de-teste-123",
                "new_password1": "outra-senha-forte-456",
                "new_password2": "outra-senha-forte-456",
            },
        )
        usuario.refresh_from_db()
        assert usuario.precisa_trocar_senha is False
        assert client.get(reverse("core:painel")).status_code == 200

    def test_quem_ja_trocou_nao_e_desviado(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("core:painel")).status_code == 200
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest accounts/tests/test_login.py -v
```
Esperado: `NoReverseMatch: 'accounts' is not a registered namespace`.

- [ ] **Step 2b: Instalar o bloqueio de tentativas de login**

Sem limite de tentativas, uma senha fraca cai por força bruta em minutos — e
aqui isso dá acesso à ficha de crianças acolhidas. `django-axes` resolve com
configuração, sem código próprio, e traz uma tela no admin para a coordenação
desbloquear quem se trancou fora.

Acrescentar a `requirements/base.txt`:
```
django-axes[ipware]>=6.5,<8.0
```

```bash
pip install -r requirements/dev.txt
```

Em `comviver/settings/base.py`:
```python
INSTALLED_APPS = [
    # ...
    "axes",
    "core",
    "accounts",
]

MIDDLEWARE = [
    # ... (axes fica por ultimo)
    "axes.middleware.AxesMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",   # precisa vir primeiro
    "django.contrib.auth.backends.ModelBackend",
]

# Cinco tentativas erradas bloqueiam o usuario por 30 minutos. O bloqueio
# considera usuario e IP juntos: bloquear so por IP deixaria a recepcao inteira
# de fora quando uma pessoa errasse a senha, porque todos saem pelo mesmo IP.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.5
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "accounts/bloqueado.html"
```

Em `comviver/settings/test.py`, desligar para não interferir nos testes que
fazem vários logins seguidos:
```python
AXES_ENABLED = False
```

E um teste próprio para a trava, em `accounts/tests/test_login.py`:
```python
class TestBloqueioPorTentativas:
    def test_bloqueia_apos_cinco_erros(self, client, settings):
        """Sem essa trava, senha fraca cai por forca bruta — e o acesso obtido
        alcanca a ficha de criancas acolhidas."""
        settings.AXES_ENABLED = True
        UsuarioFactory(username="maria", password="senha-de-teste-123")

        for _ in range(5):
            client.post(
                reverse("accounts:login"), {"username": "maria", "password": "errada"}
            )

        resposta = client.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "senha-de-teste-123"},
        )
        assert resposta.status_code in (403, 429)
```

Criar `templates/accounts/bloqueado.html` seguindo o layout da tela de login,
com a mensagem:
```html
    <div class="alert alert-danger">
      <strong>Acesso bloqueado temporariamente.</strong>
      <p class="mb-0 small">
        Foram feitas várias tentativas com senha incorreta. Aguarde 30 minutos
        ou procure a coordenação.
      </p>
    </div>
```

- [ ] **Step 3: Escrever `accounts/forms.py`**

```python
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Usuário ou senha incorretos.",
        "inactive": "Este usuário está desativado. Procure a coordenação.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autofocus": True, "placeholder": "Seu usuário"}
        )
        self.fields["password"].label = "Senha"
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Sua senha"}
        )


class TrocaSenhaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Senha atual"
        self.fields["new_password1"].label = "Nova senha"
        self.fields["new_password2"].label = "Repita a nova senha"
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})
```

O Django trata usuário inativo como login inválido por padrão, o que já satisfaz o teste correspondente.

- [ ] **Step 4: Escrever `accounts/views.py`**

```python
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.urls import reverse_lazy

from accounts.forms import LoginForm, TrocaSenhaForm


class EntrarView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class SairView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class TrocarSenhaView(PasswordChangeView):
    template_name = "accounts/trocar_senha.html"
    form_class = TrocaSenhaForm
    success_url = reverse_lazy("core:painel")

    def form_valid(self, form):
        resposta = super().form_valid(form)
        self.request.user.precisa_trocar_senha = False
        self.request.user.save(update_fields=["precisa_trocar_senha"])
        return resposta
```

- [ ] **Step 5: Escrever `accounts/middleware.py`**

```python
from django.shortcuts import redirect
from django.urls import reverse


class TrocaSenhaObrigatoriaMiddleware:
    """Desvia para a troca de senha quem ainda usa a senha provisoria.

    Senha provisoria e definida pela coordenacao ao criar o usuario, entao
    circula por bilhete ou mensagem. Precisa ser trocada no primeiro acesso.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.precisa_trocar_senha:
            liberadas = {
                reverse("accounts:trocar_senha"),
                reverse("accounts:logout"),
            }
            if request.path not in liberadas and not request.path.startswith("/static/"):
                return redirect("accounts:trocar_senha")
        return self.get_response(request)
```

Em `comviver/settings/base.py`, ao fim de `MIDDLEWARE`:
```python
    "accounts.middleware.TrocaSenhaObrigatoriaMiddleware",
```

- [ ] **Step 6: Escrever as URLs**

`accounts/urls.py`:
```python
from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("entrar/", views.EntrarView.as_view(), name="login"),
    path("sair/", views.SairView.as_view(), name="logout"),
    path("trocar-senha/", views.TrocarSenhaView.as_view(), name="trocar_senha"),
]
```

`comviver/urls.py`:
```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

`core/urls.py` é criado na Task 8. Para esta tarefa passar, criá-lo agora com conteúdo mínimo:

```python
from django.urls import path

from core import views

app_name = "core"

urlpatterns = [path("", views.PainelView.as_view(), name="painel")]
```

E `core/views.py` mínimo:
```python
from django.views.generic import TemplateView

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin


class PainelView(PerfilRequiredMixin, TemplateView):
    template_name = "core/painel.html"
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
```

- [ ] **Step 7: Baixar o Bootstrap para `static/vendor/`**

Os arquivos são servidos pelo próprio sistema, nunca por CDN.

```bash
mkdir -p static/vendor/fonts
curl -L -o static/vendor/bootstrap.min.css \
  https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css
curl -L -o static/vendor/bootstrap.bundle.min.js \
  https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js
curl -L -o static/vendor/bootstrap-icons.css \
  https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css
curl -L -o static/vendor/fonts/bootstrap-icons.woff2 \
  https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2
curl -L -o static/vendor/fonts/bootstrap-icons.woff \
  https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff
```

`bootstrap-icons.css` referencia as fontes por caminho relativo `./fonts/`, que
é exatamente onde elas foram colocadas. Conferir abrindo o arquivo e procurando
por `url("./fonts/bootstrap-icons.woff2`.

Estes arquivos entram no Git. São dependência de execução, não artefato de
build, e versioná-los garante que a instalação na instituição funcione sem
acesso à internet.

- [ ] **Step 8: Escrever os templates**

`templates/accounts/login.html`:
```html
{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Entrar — ComViver</title>
  <link href="{% static 'vendor/bootstrap.min.css' %}" rel="stylesheet">
  <link href="{% static 'css/comviver.css' %}" rel="stylesheet">
</head>
<body class="bg-light">
  <main class="container" style="max-width: 24rem; margin-top: 8vh;">
    <h1 class="h3 mb-4 text-center">ComViver</h1>
    <div class="card shadow-sm">
      <div class="card-body">
        <form method="post">
          {% csrf_token %}
          {% if form.non_field_errors %}
            <div class="alert alert-danger py-2">
              {% for erro in form.non_field_errors %}{{ erro }}{% endfor %}
            </div>
          {% endif %}
          {% for campo in form %}
            <div class="mb-3">
              <label for="{{ campo.id_for_label }}" class="form-label">{{ campo.label }}</label>
              {{ campo }}
              {% for erro in campo.errors %}
                <div class="form-text text-danger">{{ erro }}</div>
              {% endfor %}
            </div>
          {% endfor %}
          <button type="submit" class="btn btn-primary w-100">Entrar</button>
        </form>
      </div>
    </div>
    <p class="text-center text-muted mt-3 small">Lar Padre José Gumercindo</p>
  </main>
</body>
</html>
```

`static/css/comviver.css`:
```css
:root {
  --bs-primary: #2a6f4e;
  --bs-primary-rgb: 42, 111, 78;
}

.navbar.bg-primary {
  background-color: var(--bs-primary) !important;
}

.btn-primary {
  --bs-btn-bg: var(--bs-primary);
  --bs-btn-border-color: var(--bs-primary);
  --bs-btn-hover-bg: #235c41;
  --bs-btn-hover-border-color: #235c41;
}

.nav-link:hover {
  background-color: rgba(42, 111, 78, 0.08);
  border-radius: 0.25rem;
}
```

`templates/accounts/trocar_senha.html`:
```html
{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trocar senha — ComViver</title>
  <link href="{% static 'vendor/bootstrap.min.css' %}" rel="stylesheet">
  <link href="{% static 'css/comviver.css' %}" rel="stylesheet">
</head>
<body class="bg-light">
  <main class="container" style="max-width: 28rem; margin-top: 8vh;">
    <h1 class="h3 mb-2 text-center">Defina sua nova senha</h1>
    <p class="text-muted small text-center mb-4">
      Por segurança, troque a senha provisória antes de usar o sistema.
    </p>
    <div class="card shadow-sm">
      <div class="card-body">
        <form method="post">
          {% csrf_token %}
          {% if form.non_field_errors %}
            <div class="alert alert-danger py-2">
              {% for erro in form.non_field_errors %}{{ erro }}{% endfor %}
            </div>
          {% endif %}
          {% for campo in form %}
            <div class="mb-3">
              <label for="{{ campo.id_for_label }}" class="form-label">{{ campo.label }}</label>
              {{ campo }}
              {% if campo.help_text %}
                <div class="form-text">{{ campo.help_text }}</div>
              {% endif %}
              {% for erro in campo.errors %}
                <div class="form-text text-danger">{{ erro }}</div>
              {% endfor %}
            </div>
          {% endfor %}
          <button type="submit" class="btn btn-primary w-100">Salvar nova senha</button>
        </form>
      </div>
    </div>
  </main>
</body>
</html>
```

- [ ] **Step 9: Rodar os testes**

```bash
pytest accounts/tests/test_login.py core/tests/test_mixins.py -v
```
Esperado: todos passando, inclusive `test_anonimo_vai_para_o_login`, que estava pendente da Task 6.

O template `core/painel.html` ainda não existe; criar um mínimo para os testes de redirecionamento:

`templates/core/painel.html`:
```html
<h1>Painel</h1>
```

Recebe conteúdo real na Task 9.

- [ ] **Step 10: Commit**

```bash
git add accounts core templates static comviver/urls.py comviver/settings/base.py
git commit -m "feat(accounts): adiciona login, logout e troca de senha obrigatoria"
```

---

## Task 8: Layout base e menu por perfil

Segunda e terceira camadas de proteção começam aqui: o menu não exibe o que o perfil não pode abrir.

**Files:**
- Create: `templates/base.html`, `static/css/comviver.css`
- Create: `core/context_processors.py`
- Create: `core/tests/test_menu.py`
- Modify: `comviver/settings/base.py` (context processor)
- Modify: `templates/core/painel.html`, `templates/accounts/trocar_senha.html`

**Interfaces:**
- Consumes: `accounts.models.Usuario` (Task 4)
- Produces: `templates/base.html` com blocos `titulo`, `conteudo` e `acoes`; `core.context_processors.menu(request) -> dict` devolvendo `{"menu_itens": list[dict]}`, cada item com chaves `rotulo`, `url` e `icone`

- [ ] **Step 1: Escrever os testes que falham**

`core/tests/test_menu.py`:
```python
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestMenuPorPerfil:
    def test_admin_ve_o_item_de_usuarios(self, client, usuario_admin):
        client.force_login(usuario_admin)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert "Usuários" in conteudo

    def test_tecnico_nao_ve_o_item_de_usuarios(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert "Usuários" not in conteudo

    def test_operacional_nao_ve_o_item_de_usuarios(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert "Usuários" not in conteudo

    def test_todos_veem_o_painel(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert "Painel" in conteudo

    def test_nome_do_usuario_aparece_no_cabecalho(self, client, usuario_admin):
        client.force_login(usuario_admin)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert usuario_admin.get_full_name() in conteudo
```

Os testes verificam a **ausência** do texto no HTML, não apenas que o link está escondido. Esconder via CSS deixaria o item no HTML e o teste falharia — que é o comportamento desejado (spec §5.2, camada 3).

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_menu.py -v
```
Esperado: falha em `test_admin_ve_o_item_de_usuarios` — o painel mínimo não tem menu.

- [ ] **Step 3: Escrever `core/context_processors.py`**

```python
from django.urls import reverse


def menu(request):
    """Monta o menu conforme o perfil.

    Item sem permissao nao e renderizado, em vez de exibido e retornar 403.
    """
    if not request.user.is_authenticated:
        return {"menu_itens": []}

    itens = [
        {"rotulo": "Painel", "url": reverse("core:painel"), "icone": "house"},
    ]

    # Os itens de dominio entram nas fases 2 a 5, cada um com seu recorte de perfil.

    if request.user.pode_gerenciar_usuarios():
        itens.append(
            {"rotulo": "Usuários", "url": reverse("accounts:usuario_list"), "icone": "people"}
        )

    return {"menu_itens": itens}
```

A rota `accounts:usuario_list` é criada na Task 10. Para esta tarefa, adicioná-la já em `accounts/urls.py` apontando para uma view mínima, substituída na Task 10:

```python
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_list"),
```

E em `accounts/views.py`:
```python
from django.views.generic import ListView

from accounts.models import Perfil, Usuario
from core.mixins import PerfilRequiredMixin


class UsuarioListView(PerfilRequiredMixin, ListView):
    model = Usuario
    template_name = "accounts/usuario_list.html"
    context_object_name = "usuarios"
    perfis_permitidos = [Perfil.ADMIN]
```

Em `comviver/settings/base.py`, dentro de `TEMPLATES[0]["OPTIONS"]["context_processors"]`:
```python
                "core.context_processors.menu",
```

- [ ] **Step 4: Escrever `templates/base.html`**

```html
{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block titulo %}ComViver{% endblock %} — ComViver</title>
  <link href="{% static 'vendor/bootstrap.min.css' %}" rel="stylesheet">
  <link href="{% static 'vendor/bootstrap-icons.css' %}" rel="stylesheet">
  <link href="{% static 'css/comviver.css' %}" rel="stylesheet">
</head>
<body>
  <nav class="navbar navbar-dark bg-primary sticky-top">
    <div class="container-fluid">
      <a class="navbar-brand fw-semibold" href="{% url 'core:painel' %}">ComViver</a>
      <div class="d-flex align-items-center gap-3">
        <span class="text-white-50 small">{{ user.get_full_name|default:user.username }}</span>
        <form method="post" action="{% url 'accounts:logout' %}" class="m-0">
          {% csrf_token %}
          <button class="btn btn-sm btn-outline-light" type="submit">Sair</button>
        </form>
      </div>
    </div>
  </nav>

  <div class="container-fluid">
    <div class="row">
      <aside class="col-12 col-md-3 col-lg-2 bg-light border-end min-vh-100 py-3">
        <nav class="nav flex-column">
          {% for item in menu_itens %}
            <a class="nav-link text-dark d-flex align-items-center gap-2" href="{{ item.url }}">
              <i class="bi bi-{{ item.icone }}"></i>{{ item.rotulo }}
            </a>
          {% endfor %}
        </nav>
      </aside>

      <main class="col-12 col-md-9 col-lg-10 py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
          <h1 class="h4 mb-0">{% block cabecalho %}{% endblock %}</h1>
          <div>{% block acoes %}{% endblock %}</div>
        </div>

        {% if messages %}
          {% for mensagem in messages %}
            <div class="alert alert-{{ mensagem.tags|default:'info' }} alert-dismissible fade show">
              {{ mensagem }}
              <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
          {% endfor %}
        {% endif %}

        {% block conteudo %}{% endblock %}
      </main>
    </div>
  </div>

  <script src="{% static 'vendor/bootstrap.bundle.min.js' %}"></script>
</body>
</html>
```

`static/css/comviver.css` já foi criado na Task 7 e não muda aqui.

- [ ] **Step 5: Atualizar `templates/core/painel.html`**

```html
{% extends "base.html" %}
{% block titulo %}Painel{% endblock %}
{% block cabecalho %}Painel{% endblock %}
{% block conteudo %}
  <p class="text-muted">Bem-vindo, {{ user.get_full_name|default:user.username }}.</p>
{% endblock %}
```

Criar também `templates/accounts/usuario_list.html` mínimo, substituído na Task 10:
```html
{% extends "base.html" %}
{% block titulo %}Usuários{% endblock %}
{% block cabecalho %}Usuários{% endblock %}
{% block conteudo %}
  <ul>{% for usuario in usuarios %}<li>{{ usuario }}</li>{% endfor %}</ul>
{% endblock %}
```

- [ ] **Step 6: Rodar os testes**

```bash
pytest core/tests/ accounts/tests/ -v
```
Esperado: todos passando.

- [ ] **Step 7: Commit**

```bash
git add templates static core accounts comviver/settings/base.py
git commit -m "feat(core): adiciona layout base com menu montado por perfil"
```

---

## Task 9: Painel com cartões por perfil

**Files:**
- Modify: `core/views.py`, `templates/core/painel.html`
- Create: `core/tests/test_painel.py`

**Interfaces:**
- Consumes: `core.mixins.PerfilRequiredMixin` (Task 6), `accounts.models.Perfil` (Task 4)
- Produces: `core.views.PainelView` com `get_context_data` devolvendo `cartoes: list[dict]`, cada um com `titulo`, `valor`, `descricao` e `icone`

Nesta fase os cartões trazem apenas o que já existe no banco: contagem de usuários. Os números de acolhidos, doações e voluntários entram nas fases 2 a 4, acrescentando entradas nesta mesma lista.

- [ ] **Step 1: Escrever os testes que falham**

`core/tests/test_painel.py`:
```python
import pytest
from django.urls import reverse

from accounts.factories import UsuarioFactory
from accounts.models import Perfil

pytestmark = pytest.mark.django_db


class TestPainel:
    def test_admin_ve_o_cartao_de_usuarios_ativos(self, client, usuario_admin):
        UsuarioFactory.create_batch(3, perfil=Perfil.OPERACIONAL)
        client.force_login(usuario_admin)
        cartoes = client.get(reverse("core:painel")).context["cartoes"]
        titulos = [c["titulo"] for c in cartoes]
        assert "Usuários ativos" in titulos

    def test_cartao_conta_apenas_usuarios_ativos(self, client, usuario_admin):
        UsuarioFactory.create_batch(2, perfil=Perfil.OPERACIONAL)
        UsuarioFactory(perfil=Perfil.OPERACIONAL, is_active=False)
        client.force_login(usuario_admin)
        cartoes = client.get(reverse("core:painel")).context["cartoes"]
        cartao = next(c for c in cartoes if c["titulo"] == "Usuários ativos")
        assert cartao["valor"] == 3  # os 2 criados + o proprio admin

    def test_operacional_nao_ve_o_cartao_de_usuarios(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        cartoes = client.get(reverse("core:painel")).context["cartoes"]
        assert "Usuários ativos" not in [c["titulo"] for c in cartoes]

    def test_painel_sauda_o_usuario_pelo_nome(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        conteudo = client.get(reverse("core:painel")).content.decode()
        assert usuario_tecnico.first_name in conteudo
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_painel.py -v
```
Esperado: `KeyError: 'cartoes'`.

- [ ] **Step 3: Escrever `core/views.py`**

```python
from django.views.generic import TemplateView

from accounts.models import Perfil, Usuario
from core.mixins import PerfilRequiredMixin


class PainelView(PerfilRequiredMixin, TemplateView):
    """Tela inicial. Os cartoes variam conforme o perfil (spec 6.7).

    As fases 2 a 5 acrescentam cartoes a esta lista: acolhidos ativos,
    doacoes do mes, escala de hoje e turnos descobertos.
    """

    template_name = "core/painel.html"
    perfis_permitidos = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["cartoes"] = self._montar_cartoes()
        return contexto

    def _montar_cartoes(self) -> list[dict]:
        cartoes = []

        if self.request.user.pode_gerenciar_usuarios():
            cartoes.append(
                {
                    "titulo": "Usuários ativos",
                    "valor": Usuario.objects.filter(is_active=True).count(),
                    "descricao": "com acesso ao sistema",
                    "icone": "people",
                }
            )

        return cartoes
```

- [ ] **Step 4: Atualizar `templates/core/painel.html`**

```html
{% extends "base.html" %}
{% block titulo %}Painel{% endblock %}
{% block cabecalho %}Painel{% endblock %}

{% block conteudo %}
  <p class="text-muted mb-4">
    Bem-vindo, {{ user.get_full_name|default:user.username }}.
  </p>

  <div class="row g-3">
    {% for cartao in cartoes %}
      <div class="col-12 col-sm-6 col-lg-3">
        <div class="card h-100 shadow-sm">
          <div class="card-body">
            <div class="d-flex align-items-center gap-2 text-muted small mb-2">
              <i class="bi bi-{{ cartao.icone }}"></i>{{ cartao.titulo }}
            </div>
            <div class="h2 mb-0">{{ cartao.valor }}</div>
            <div class="text-muted small">{{ cartao.descricao }}</div>
          </div>
        </div>
      </div>
    {% empty %}
      <div class="col-12">
        <p class="text-muted">Nenhum indicador disponível para o seu perfil.</p>
      </div>
    {% endfor %}
  </div>
{% endblock %}
```

- [ ] **Step 5: Rodar os testes**

```bash
pytest core/tests/test_painel.py -v
```
Esperado: 4 testes passando.

- [ ] **Step 6: Commit**

```bash
git add core templates/core/painel.html
git commit -m "feat(core): adiciona painel com cartoes por perfil"
```

---

## Task 10: Gestão de usuários (restrita ao Admin)

**Files:**
- Modify: `accounts/views.py`, `accounts/urls.py`, `accounts/forms.py`
- Create: `templates/accounts/usuario_form.html`, `templates/accounts/usuario_confirmar_desativacao.html`
- Modify: `templates/accounts/usuario_list.html`
- Create: `accounts/tests/test_gestao_usuarios.py`

**Interfaces:**
- Consumes: `accounts.models.Usuario` (Task 4), `core.mixins.PerfilRequiredMixin` (Task 6)
- Produces: rotas `accounts:usuario_list`, `accounts:usuario_novo`, `accounts:usuario_editar`, `accounts:usuario_desativar`; `accounts.forms.UsuarioForm`

- [ ] **Step 1: Escrever os testes que falham**

`accounts/tests/test_gestao_usuarios.py`:
```python
import pytest
from django.urls import reverse

from accounts.factories import UsuarioFactory
from accounts.models import Perfil, Usuario

pytestmark = pytest.mark.django_db


class TestAcessoAGestaoDeUsuarios:
    @pytest.mark.parametrize(
        "rota", ["accounts:usuario_list", "accounts:usuario_novo"]
    )
    def test_tecnico_recebe_403(self, client, usuario_tecnico, rota):
        client.force_login(usuario_tecnico)
        assert client.get(reverse(rota)).status_code == 403

    @pytest.mark.parametrize(
        "rota", ["accounts:usuario_list", "accounts:usuario_novo"]
    )
    def test_operacional_recebe_403(self, client, usuario_operacional, rota):
        client.force_login(usuario_operacional)
        assert client.get(reverse(rota)).status_code == 403

    def test_admin_acessa(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("accounts:usuario_list")).status_code == 200


class TestCriarUsuario:
    def test_admin_cria_usuario(self, client, usuario_admin):
        client.force_login(usuario_admin)
        resposta = client.post(
            reverse("accounts:usuario_novo"),
            {
                "username": "joana",
                "first_name": "Joana",
                "last_name": "Pereira",
                "email": "joana@exemplo.org",
                "telefone": "35999990000",
                "perfil": Perfil.TECNICO,
                "password1": "senha-provisoria-789",
                "password2": "senha-provisoria-789",
            },
        )
        assert resposta.status_code == 302
        novo = Usuario.objects.get(username="joana")
        assert novo.perfil == Perfil.TECNICO
        assert novo.precisa_trocar_senha is True

    def test_usuario_criado_entra_no_grupo_certo(self, client, usuario_admin):
        client.force_login(usuario_admin)
        client.post(
            reverse("accounts:usuario_novo"),
            {
                "username": "joana", "first_name": "Joana", "last_name": "Pereira",
                "email": "joana@exemplo.org", "telefone": "", "perfil": Perfil.TECNICO,
                "password1": "senha-provisoria-789", "password2": "senha-provisoria-789",
            },
        )
        novo = Usuario.objects.get(username="joana")
        assert novo.groups.filter(name="Técnico").exists()

    def test_username_repetido_mostra_erro(self, client, usuario_admin):
        UsuarioFactory(username="joana")
        client.force_login(usuario_admin)
        resposta = client.post(
            reverse("accounts:usuario_novo"),
            {
                "username": "joana", "first_name": "Joana", "last_name": "Pereira",
                "email": "j@exemplo.org", "telefone": "", "perfil": Perfil.TECNICO,
                "password1": "senha-provisoria-789", "password2": "senha-provisoria-789",
            },
        )
        assert resposta.status_code == 200
        assert "Já existe um usuário com este nome de acesso." in resposta.content.decode()


class TestEditarUsuario:
    def test_admin_troca_o_perfil(self, client, usuario_admin):
        alvo = UsuarioFactory(perfil=Perfil.OPERACIONAL)
        client.force_login(usuario_admin)
        client.post(
            reverse("accounts:usuario_editar", args=[alvo.pk]),
            {
                "username": alvo.username, "first_name": alvo.first_name,
                "last_name": alvo.last_name, "email": alvo.email,
                "telefone": "", "perfil": Perfil.TECNICO, "is_active": "on",
            },
        )
        alvo.refresh_from_db()
        assert alvo.perfil == Perfil.TECNICO
        assert alvo.groups.filter(name="Técnico").exists()


class TestDesativarUsuario:
    def test_desativar_nao_apaga_o_registro(self, client, usuario_admin):
        alvo = UsuarioFactory(perfil=Perfil.OPERACIONAL)
        client.force_login(usuario_admin)
        client.post(reverse("accounts:usuario_desativar", args=[alvo.pk]))
        alvo.refresh_from_db()
        assert alvo.is_active is False
        assert Usuario.objects.filter(pk=alvo.pk).exists()

    def test_admin_nao_desativa_a_si_mesmo(self, client, usuario_admin):
        client.force_login(usuario_admin)
        resposta = client.post(
            reverse("accounts:usuario_desativar", args=[usuario_admin.pk])
        )
        usuario_admin.refresh_from_db()
        assert usuario_admin.is_active is True
        assert resposta.status_code == 302
```

O último teste evita o acidente de a coordenação se trancar para fora do sistema.

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest accounts/tests/test_gestao_usuarios.py -v
```
Esperado: `NoReverseMatch` para `accounts:usuario_novo`.

- [ ] **Step 3: Acrescentar os formulários em `accounts/forms.py`**

```python
from django import forms
from django.contrib.auth.forms import UserCreationForm

from accounts.models import Usuario

CAMPOS_USUARIO = ["username", "first_name", "last_name", "email", "telefone", "perfil"]

ROTULOS = {
    "username": "Nome de acesso",
    "first_name": "Nome",
    "last_name": "Sobrenome",
    "email": "E-mail",
    "telefone": "Telefone",
    "perfil": "Perfil",
    "is_active": "Usuário ativo",
}


class UsuarioCreationForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = CAMPOS_USUARIO
        labels = ROTULOS
        error_messages = {
            "username": {"unique": "Já existe um usuário com este nome de acesso."}
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Senha provisória"
        self.fields["password2"].label = "Repita a senha provisória"
        self.fields["password1"].help_text = (
            "O usuário será obrigado a trocá-la no primeiro acesso."
        )
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})
        self.fields["perfil"].widget.attrs.update({"class": "form-select"})


class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = CAMPOS_USUARIO + ["is_active"]
        labels = ROTULOS
        error_messages = {
            "username": {"unique": "Já existe um usuário com este nome de acesso."}
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome, campo in self.fields.items():
            if nome == "is_active":
                campo.widget.attrs.update({"class": "form-check-input"})
            elif nome == "perfil":
                campo.widget.attrs.update({"class": "form-select"})
            else:
                campo.widget.attrs.update({"class": "form-control"})
```

- [ ] **Step 4: Escrever as views**

Substituir a `UsuarioListView` mínima em `accounts/views.py` e acrescentar as demais:

```python
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from accounts.forms import UsuarioCreationForm, UsuarioForm
from accounts.models import Perfil, Usuario
from core.mixins import PerfilRequiredMixin


class UsuarioListView(PerfilRequiredMixin, ListView):
    model = Usuario
    template_name = "accounts/usuario_list.html"
    context_object_name = "usuarios"
    perfis_permitidos = [Perfil.ADMIN]
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        busca = self.request.GET.get("q", "").strip()
        if busca:
            qs = qs.filter(
                Q(first_name__icontains=busca)
                | Q(last_name__icontains=busca)
                | Q(username__icontains=busca)
            )
        return qs


class UsuarioCreateView(PerfilRequiredMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreationForm
    template_name = "accounts/usuario_form.html"
    success_url = reverse_lazy("accounts:usuario_list")
    perfis_permitidos = [Perfil.ADMIN]

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(
            self.request,
            f"Usuário {self.object.get_full_name()} criado. "
            "Informe a senha provisória; ele deverá trocá-la no primeiro acesso.",
        )
        return resposta


class UsuarioUpdateView(PerfilRequiredMixin, UpdateView):
    model = Usuario
    form_class = UsuarioForm
    template_name = "accounts/usuario_form.html"
    success_url = reverse_lazy("accounts:usuario_list")
    perfis_permitidos = [Perfil.ADMIN]

    def form_valid(self, form):
        messages.success(self.request, "Dados do usuário atualizados.")
        return super().form_valid(form)


class UsuarioDesativarView(PerfilRequiredMixin, View):
    """Desativa o acesso. Nunca apaga o registro: o historico de quem
    cadastrou cada doacao e ficha precisa continuar resolvivel."""

    perfis_permitidos = [Perfil.ADMIN]

    def post(self, request, pk):
        alvo = get_object_or_404(Usuario, pk=pk)
        if alvo.pk == request.user.pk:
            messages.error(request, "Você não pode desativar o seu próprio acesso.")
        else:
            alvo.is_active = False
            alvo.save(update_fields=["is_active"])
            messages.success(request, f"Acesso de {alvo.get_full_name()} desativado.")
        return redirect("accounts:usuario_list")
```

`accounts/urls.py` completo:
```python
from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("entrar/", views.EntrarView.as_view(), name="login"),
    path("sair/", views.SairView.as_view(), name="logout"),
    path("trocar-senha/", views.TrocarSenhaView.as_view(), name="trocar_senha"),
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_list"),
    path("usuarios/novo/", views.UsuarioCreateView.as_view(), name="usuario_novo"),
    path("usuarios/<int:pk>/editar/", views.UsuarioUpdateView.as_view(), name="usuario_editar"),
    path(
        "usuarios/<int:pk>/desativar/",
        views.UsuarioDesativarView.as_view(),
        name="usuario_desativar",
    ),
]
```

- [ ] **Step 5: Escrever os templates**

`templates/accounts/usuario_list.html`:
```html
{% extends "base.html" %}
{% block titulo %}Usuários{% endblock %}
{% block cabecalho %}Usuários{% endblock %}

{% block acoes %}
  <a href="{% url 'accounts:usuario_novo' %}" class="btn btn-primary">
    <i class="bi bi-plus-lg"></i> Novo usuário
  </a>
{% endblock %}

{% block conteudo %}
  <form method="get" class="mb-3">
    <div class="input-group" style="max-width: 24rem;">
      <input type="search" name="q" value="{{ request.GET.q|default:'' }}"
             class="form-control" placeholder="Buscar por nome ou usuário">
      <button class="btn btn-outline-secondary" type="submit">Buscar</button>
    </div>
  </form>

  <div class="table-responsive">
    <table class="table table-hover align-middle">
      <thead>
        <tr>
          <th>Nome</th><th>Usuário</th><th>Perfil</th><th>Situação</th><th></th>
        </tr>
      </thead>
      <tbody>
        {% for usuario in usuarios %}
          <tr>
            <td>{{ usuario.get_full_name|default:"—" }}</td>
            <td>{{ usuario.username }}</td>
            <td>{{ usuario.get_perfil_display }}</td>
            <td>
              {% if usuario.is_active %}
                <span class="badge text-bg-success">Ativo</span>
              {% else %}
                <span class="badge text-bg-secondary">Desativado</span>
              {% endif %}
            </td>
            <td class="text-end">
              <a href="{% url 'accounts:usuario_editar' usuario.pk %}"
                 class="btn btn-sm btn-outline-secondary">Editar</a>
              {% if usuario.is_active and usuario.pk != request.user.pk %}
                <form method="post" action="{% url 'accounts:usuario_desativar' usuario.pk %}"
                      class="d-inline">
                  {% csrf_token %}
                  <button type="submit" class="btn btn-sm btn-outline-danger">Desativar</button>
                </form>
              {% endif %}
            </td>
          </tr>
        {% empty %}
          <tr><td colspan="5" class="text-muted">Nenhum usuário encontrado.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% if is_paginated %}
    <nav>
      <ul class="pagination">
        {% if page_obj.has_previous %}
          <li class="page-item">
            <a class="page-link" href="?page={{ page_obj.previous_page_number }}">Anterior</a>
          </li>
        {% endif %}
        <li class="page-item disabled">
          <span class="page-link">
            Página {{ page_obj.number }} de {{ page_obj.paginator.num_pages }}
          </span>
        </li>
        {% if page_obj.has_next %}
          <li class="page-item">
            <a class="page-link" href="?page={{ page_obj.next_page_number }}">Próxima</a>
          </li>
        {% endif %}
      </ul>
    </nav>
  {% endif %}
{% endblock %}
```

A desativação usa `POST` com formulário, e não um link de confirmação em JavaScript. Diálogo do navegador não deve ser usado: o padrão do projeto é confirmar por página própria ou por ação direta reversível, e a desativação é reversível.

`templates/accounts/usuario_form.html`:
```html
{% extends "base.html" %}
{% block titulo %}{% if object %}Editar usuário{% else %}Novo usuário{% endif %}{% endblock %}
{% block cabecalho %}{% if object %}Editar usuário{% else %}Novo usuário{% endif %}{% endblock %}

{% block conteudo %}
  <form method="post" style="max-width: 40rem;">
    {% csrf_token %}
    {% for campo in form %}
      <div class="mb-3 {% if campo.name == 'is_active' %}form-check{% endif %}">
        <label for="{{ campo.id_for_label }}"
               class="{% if campo.name == 'is_active' %}form-check-label{% else %}form-label{% endif %}">
          {{ campo.label }}
        </label>
        {{ campo }}
        {% if campo.help_text %}
          <div class="form-text">{{ campo.help_text }}</div>
        {% endif %}
        {% for erro in campo.errors %}
          <div class="form-text text-danger">{{ erro }}</div>
        {% endfor %}
      </div>
    {% endfor %}
    <button type="submit" class="btn btn-primary">Salvar</button>
    <a href="{% url 'accounts:usuario_list' %}" class="btn btn-link">Cancelar</a>
  </form>
{% endblock %}
```

- [ ] **Step 6: Rodar a suíte completa**

```bash
pytest -v
```
Esperado: todos os testes passando.

- [ ] **Step 7: Commit**

```bash
git add accounts templates/accounts
git commit -m "feat(accounts): adiciona gestao de usuarios restrita ao Admin"
```

---

## Task 11: Páginas de erro e verificação final

**Files:**
- Create: `templates/403.html`, `templates/404.html`, `templates/500.html`
- Create: `core/tests/test_paginas_erro.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `templates/base.html` (Task 8)
- Produces: páginas de erro dentro do layout do sistema

- [ ] **Step 1: Escrever os testes que falham**

`core/tests/test_paginas_erro.py`:
```python
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestPaginasDeErro:
    def test_403_usa_template_proprio(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("accounts:usuario_list"))
        assert resposta.status_code == 403
        assert "Seu perfil não tem acesso" in resposta.content.decode()

    def test_404_usa_template_proprio(self, client, usuario_admin, settings):
        settings.DEBUG = False
        client.force_login(usuario_admin)
        resposta = client.get("/rota-que-nao-existe/")
        assert resposta.status_code == 404
        assert "Página não encontrada" in resposta.content.decode()
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_paginas_erro.py -v
```
Esperado: falha — o Django usa a página padrão, sem esse texto.

- [ ] **Step 3: Escrever os templates de erro**

`templates/403.html`:
```html
{% extends "base.html" %}
{% block titulo %}Acesso negado{% endblock %}
{% block cabecalho %}Acesso negado{% endblock %}
{% block conteudo %}
  <div class="alert alert-warning">
    <p class="mb-1"><strong>Seu perfil não tem acesso a esta página.</strong></p>
    <p class="mb-0 small">
      Se você precisa deste acesso para o seu trabalho, fale com a coordenação.
    </p>
  </div>
  <a href="{% url 'core:painel' %}" class="btn btn-primary">Voltar ao painel</a>
{% endblock %}
```

`templates/404.html`:
```html
{% extends "base.html" %}
{% block titulo %}Página não encontrada{% endblock %}
{% block cabecalho %}Página não encontrada{% endblock %}
{% block conteudo %}
  <p class="text-muted">
    O endereço acessado não existe ou o registro foi removido.
  </p>
  <a href="{% url 'core:painel' %}" class="btn btn-primary">Voltar ao painel</a>
{% endblock %}
```

`templates/500.html` — não pode estender `base.html`, porque o erro pode estar justamente no contexto:
```html
{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Erro no sistema — ComViver</title>
  <link href="{% static 'vendor/bootstrap.min.css' %}" rel="stylesheet">
</head>
<body class="bg-light">
  <main class="container py-5" style="max-width: 32rem;">
    <h1 class="h4">Erro no sistema</h1>
    <p class="text-muted">
      Algo deu errado ao processar esta página. O problema foi registrado.
      Tente novamente em alguns instantes; se persistir, avise o responsável
      técnico informando o que estava fazendo.
    </p>
    <a href="/" class="btn btn-primary">Voltar ao início</a>
  </main>
</body>
</html>
```

- [ ] **Step 4: Rodar a suíte completa e o lint**

```bash
pytest -v
ruff check .
ruff format --check .
```
Esperado: todos os testes passando, ruff sem apontamentos.

- [ ] **Step 5: Verificação manual no navegador**

```bash
python manage.py runserver
```

Roteiro, com um superusuário criado por `python manage.py createsuperuser`:

1. Abrir `http://127.0.0.1:8000/` — deve redirecionar para `/entrar/`
2. Entrar com o superusuário — deve cair no painel
3. Criar um usuário de perfil Operacional em Usuários → Novo usuário
4. Sair e entrar com esse usuário — deve exigir troca de senha
5. Trocar a senha — deve liberar o painel
6. Conferir que o menu **não** mostra "Usuários"
7. Acessar `http://127.0.0.1:8000/usuarios/` na barra de endereços — deve mostrar a página 403 própria
8. Acessar `http://127.0.0.1:8000/nao-existe/` — deve mostrar a 404 própria

O passo 7 é o mais importante: confirma que a proteção está na view, não apenas no menu.

- [ ] **Step 6: Atualizar o README com a seção de perfis**

Acrescentar ao `README.md`:

```markdown
## Perfis de acesso

| Perfil | O que faz |
|---|---|
| Administrador | Acesso total, inclusive gestão de usuários e relatórios completos |
| Técnico | Ficha completa do acolhido, saúde, situação jurídica; leitura nos demais módulos |
| Operacional | Doações, voluntários e escalas; do acolhido vê apenas o essencial do dia a dia |

O recorte entre Técnico e Operacional atende ao art. 143 do ECA, que veda a
divulgação de informação que identifique criança ou adolescente acolhido.

## Primeiro acesso

```bash
python manage.py createsuperuser
```

O superusuário nasce com perfil Administrador e sem obrigação de trocar a senha.
Os demais usuários são criados por ele em Usuários → Novo usuário, recebem senha
provisória e são obrigados a trocá-la no primeiro acesso.
```

- [ ] **Step 7: Commit**

```bash
git add templates core/tests README.md
git commit -m "feat(core): adiciona paginas de erro proprias em portugues"
```

---

## Verificação de conclusão da Fase 1

Antes de considerar a fase encerrada, confirmar com os comandos e registrar a saída:

- [ ] `pytest` — suíte inteira passando, sem testes ignorados
- [ ] `ruff check .` — sem apontamentos
- [ ] `git status --short` — `.env` não listado
- [ ] `git log --oneline` — um commit por tarefa
- [ ] Roteiro manual da Task 11, passo a passo, com o passo 7 confirmando o 403

**O que fica pronto:** projeto conectado ao PostgreSQL, autenticação, três perfis sincronizados com grupos, mixin de controle de acesso com falha fechada, layout com menu por perfil, painel, gestão de usuários e páginas de erro.

**O que a Fase 2 encontra pronto para consumir:**
- `core.models.TimeStampedModel`, `SoftDeleteModel`, `Endereco`
- `core.mixins.PerfilRequiredMixin`
- `accounts.models.Usuario`, `Perfil`, `Usuario.pode_ver_ficha_completa()`
- `accounts.factories.UsuarioFactory` e as fixtures `usuario_admin`, `usuario_tecnico`, `usuario_operacional`
- `templates/base.html` com os blocos `titulo`, `cabecalho`, `acoes` e `conteudo`
- `core.context_processors.menu`, onde cada fase acrescenta seus itens
- `core.views.PainelView._montar_cartoes`, onde cada fase acrescenta seus cartões

**Pendências registradas, com a fase em que são resolvidas:**

| Item da spec | Por que não entra aqui | Fase |
|---|---|---|
| `LogAcessoFicha` (§4.1) | Depende do model `Acolhido` e da view de detalhe que ele registra | 2 |
| View protegida para servir `media/` (§5.4) | Não há upload de arquivo antes da foto do acolhido | 2 |
| Termo de consentimento e exportação por titular (§5.5) | Dependem do cadastro de acolhido e do vínculo com o responsável | 2 |
| Busca global (§6.6) | Precisa de pelo menos dois módulos de domínio para ter sentido | 5 |
| Comando `seed_demo` (§8.4) | Só há usuários para popular; sem dado de domínio não demonstra nada | 2 |
| Rotina de backup (§8.5) | Amarrada ao banco de produção, ainda não contratado | 5 |

Nenhum item da spec destinado à Fase 1 ficou de fora. Cada linha acima é uma
exigência real da spec, com destino definido — não é backlog aberto.
