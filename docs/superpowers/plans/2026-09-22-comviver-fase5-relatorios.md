# ComViver — Fase 5: Relatórios, Busca Global e Entrega — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar o sistema com os oito relatórios da spec em três formatos, busca global, configuração da instituição, backup documentado e os manuais que permitem à instituição continuar usando o ComViver depois que o projeto de extensão terminar.

**Architecture:** App `relatorios` como folha do grafo — lê todos os outros e ninguém depende dele. Cada relatório é uma função em `services.py` que devolve dados estruturados; três renderizadores genéricos (tela, CSV, PDF) consomem essa saída. Relatório novo é uma função, não uma tela inteira.

**Tech Stack:** Django 5.x, Bootstrap 5 (local), WeasyPrint (PDF), biblioteca padrão `csv`.

**Spec:** `docs/superpowers/specs/2026-09-22-comviver-design.md`

**Depende de:** Fases 1 a 4 concluídas.

## Global Constraints

- Python 3.12; Django 5.x (`Django>=5.1,<6.0`).
- PostgreSQL exclusivamente, inclusive em teste.
- `.env` nunca versionado.
- Interface, mensagens e validações em português do Brasil.
- Exclusão sempre lógica (`deleted_at`).
- Controle de acesso em três camadas: view, formulário e template.
- `ruff` limpo antes de cada commit.
- Teste escrito antes da implementação, falhando primeiro pelo motivo certo.

## Restrição central desta fase

Relatório é o ponto em que dado sigiloso sai do sistema — em papel, em PDF, em
planilha anexada a e-mail. Duas regras valem para tudo nesta fase:

1. **Relatório com nome de acolhido é restrito a Admin e Técnico**, e todo PDF
   que o contenha sai com marca de documento sigiloso, nome do emissor e data.
2. **Relatório destinado a público externo usa dados agregados**, sem
   identificação. É o que o ECA exige e, na prática, é o que a instituição mais
   emite: o conselho quer saber quantas crianças, não quais.

## O que as fases anteriores deixaram pronto

- `core.pdf.renderizar_pdf(template, contexto, nome_arquivo, request)`
- `core.views.BaseListView`, `BaseCreateView`, `BaseUpdateView`
- `core.mixins.PerfilRequiredMixin`
- `core.storage.servir_media_protegida`
- `doacoes.services.totais_por_tipo`, `total_arrecadado`, `doadores_recorrentes_inativos`
- `escalas.services.turnos_descobertos_proximos`
- `acolhidos.models.Acolhido.tempo_acolhimento`, `Medicacao.em_vigor`
- `seed_demo` populando os cinco módulos

---

## Estrutura de arquivos ao fim da Fase 5

```
relatorios/
├── services.py        # uma funcao por relatorio; devolve dados, nao HTML
├── renderers.py       # tela, CSV e PDF a partir da mesma estrutura
├── views.py
├── urls.py
├── forms.py           # filtros de periodo
├── migrations/
└── tests/
    ├── test_services.py
    ├── test_renderers.py
    ├── test_permissoes.py
    └── test_sigilo.py          # o que nao pode sair do sistema

core/
├── models.py          # + ConfiguracaoInstituicao  (singleton)
├── views.py           # + BuscaGlobalView
├── search.py          # busca por modulo, filtrada por perfil
└── management/commands/backup_dados.py

templates/relatorios/
├── indice.html
├── base_relatorio.html          # layout de tela
├── base_impressao.html          # layout de PDF, com marca de sigilo
└── <um por relatorio>.html

docs/
├── manual-usuario.md
└── manual-admin.md
```

---

## Task 1: Configuração da instituição

Pendência registrada na Fase 3: o recibo sai sem CNPJ e endereço. Relatório de
prestação de contas tem o mesmo problema. Resolver antes dos relatórios.

**Files:**
- Modify: `core/models.py`
- Create: `core/forms.py` (acrescentar `ConfiguracaoForm`), `core/tests/test_configuracao.py`
- Modify: `core/views.py`, `core/urls.py`, `core/context_processors.py`
- Create: `templates/core/configuracao_form.html`
- Modify: `templates/doacoes/recibo.html`

**Interfaces:**
- Consumes: `core.mixins.PerfilRequiredMixin`
- Produces:
  - `core.models.ConfiguracaoInstituicao` — singleton com `nome`, `cnpj`, `endereco`, `telefone`, `email`, `responsavel_legal`, `logo`
  - método de classe `ConfiguracaoInstituicao.obter() -> ConfiguracaoInstituicao`
  - context processor disponibilizando `instituicao` em todo template

- [ ] **Step 1: Escrever os testes que falham**

`core/tests/test_configuracao.py`:
```python
import pytest
from django.urls import reverse

from core.models import ConfiguracaoInstituicao

pytestmark = pytest.mark.django_db


class TestSingleton:
    def test_obter_cria_na_primeira_chamada(self):
        assert ConfiguracaoInstituicao.objects.count() == 0
        ConfiguracaoInstituicao.obter()
        assert ConfiguracaoInstituicao.objects.count() == 1

    def test_obter_devolve_sempre_o_mesmo_registro(self):
        primeira = ConfiguracaoInstituicao.obter()
        segunda = ConfiguracaoInstituicao.obter()
        assert primeira.pk == segunda.pk

    def test_nao_cria_um_segundo_registro(self):
        """Duas configuracoes significariam recibos com dados diferentes
        dependendo de qual fosse lida."""
        ConfiguracaoInstituicao.obter()
        ConfiguracaoInstituicao.objects.create(nome="Outra")
        assert ConfiguracaoInstituicao.objects.count() == 1

    def test_nome_padrao(self):
        assert ConfiguracaoInstituicao.obter().nome == "Lar Padre José Gumercindo"

    def test_cnpj_formatado(self):
        config = ConfiguracaoInstituicao.obter()
        config.cnpj = "12345678000190"
        config.save()
        assert config.cnpj_formatado == "12.345.678/0001-90"

    def test_cnpj_formatado_vazio_devolve_string_vazia(self):
        assert ConfiguracaoInstituicao.obter().cnpj_formatado == ""


class TestAcesso:
    def test_so_admin_edita(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        assert client.get(reverse("core:configuracao")).status_code == 403

    def test_admin_edita(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("core:configuracao")).status_code == 200

    def test_salvar_atualiza_o_singleton(self, client, usuario_admin):
        client.force_login(usuario_admin)
        client.post(
            reverse("core:configuracao"),
            {
                "nome": "Lar Padre José Gumercindo",
                "cnpj": "12345678000190",
                "endereco": "Rua das Flores, 100 — Itajubá/MG",
                "telefone": "3536220000",
                "email": "contato@exemplo.org",
                "responsavel_legal": "Maria Coordenadora",
            },
        )
        assert ConfiguracaoInstituicao.obter().cnpj == "12345678000190"
        assert ConfiguracaoInstituicao.objects.count() == 1


class TestNoRecibo:
    def test_recibo_mostra_o_cnpj_configurado(self, client, usuario_operacional):
        from doacoes.factories import DoacaoFactory

        config = ConfiguracaoInstituicao.obter()
        config.cnpj = "12345678000190"
        config.save()

        doacao = DoacaoFactory()
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("doacoes:recibo", args=[doacao.pk])).content.decode()
        assert "12.345.678/0001-90" in conteudo
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_configuracao.py -v
```
Esperado: `ImportError: cannot import name 'ConfiguracaoInstituicao'`.

- [ ] **Step 3: Escrever o model**

Em `core/models.py`:
```python
class ConfiguracaoInstituicao(TimeStampedModel):
    """Dados da instituicao, usados em recibos e relatorios.

    Registro unico. Duas configuracoes significariam documentos com dados
    diferentes dependendo de qual fosse lida.
    """

    nome = models.CharField("nome", max_length=150, default="Lar Padre José Gumercindo")
    cnpj = models.CharField("CNPJ", max_length=14, blank=True)
    endereco = models.CharField("endereço", max_length=250, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    responsavel_legal = models.CharField("responsável legal", max_length=150, blank=True)
    logo = models.ImageField("logotipo", upload_to="instituicao/", blank=True)

    class Meta:
        verbose_name = "configuração da instituição"
        verbose_name_plural = "configuração da instituição"

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs):
        # Forca o singleton: qualquer save grava sempre na mesma linha.
        existente = ConfiguracaoInstituicao.objects.exclude(pk=self.pk).first()
        if existente:
            self.pk = existente.pk
        super().save(*args, **kwargs)

    @classmethod
    def obter(cls) -> "ConfiguracaoInstituicao":
        config = cls.objects.first()
        if config is None:
            config = cls.objects.create()
        return config

    @property
    def cnpj_formatado(self) -> str:
        numero = "".join(filter(str.isdigit, self.cnpj))
        if len(numero) != 14:
            return ""
        return f"{numero[:2]}.{numero[2:5]}.{numero[5:8]}/{numero[8:12]}-{numero[12:]}"
```

- [ ] **Step 4: Formulário, view, rota e context processor**

Em `core/forms.py`:
```python
from core.models import ConfiguracaoInstituicao


class ConfiguracaoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoInstituicao
        fields = [
            "nome", "cnpj", "endereco", "telefone",
            "email", "responsavel_legal", "logo",
        ]

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        for campo in self.fields.values():
            campo.widget.attrs.update({"class": "form-control"})

    def clean_cnpj(self):
        numero = "".join(filter(str.isdigit, self.cleaned_data.get("cnpj", "")))
        if numero and len(numero) != 14:
            raise forms.ValidationError("O CNPJ precisa ter 14 dígitos.")
        return numero
```

Em `core/views.py`:
```python
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from core.forms import ConfiguracaoForm
from core.models import ConfiguracaoInstituicao


class ConfiguracaoView(PerfilRequiredMixin, UpdateView):
    model = ConfiguracaoInstituicao
    form_class = ConfiguracaoForm
    template_name = "core/configuracao_form.html"
    success_url = reverse_lazy("core:configuracao")
    perfis_permitidos = [Perfil.ADMIN]

    def get_object(self, queryset=None):
        return ConfiguracaoInstituicao.obter()

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"usuario": self.request.user}

    def form_valid(self, form):
        messages.success(self.request, "Dados da instituição atualizados.")
        return super().form_valid(form)
```

Em `core/urls.py`:
```python
    path("configuracao/", views.ConfiguracaoView.as_view(), name="configuracao"),
```

Em `core/context_processors.py`, nova função:
```python
def instituicao(request):
    """Disponibiliza os dados da instituicao em qualquer template."""
    from core.models import ConfiguracaoInstituicao

    return {"instituicao": ConfiguracaoInstituicao.obter()}
```

Em `comviver/settings/base.py`, `context_processors`:
```python
                "core.context_processors.instituicao",
```

E no menu, para o Admin:
```python
    if request.user.e_admin:
        itens.append(
            {"rotulo": "Configuração", "url": reverse("core:configuracao"), "icone": "gear"}
        )
```

- [ ] **Step 5: Simplificar o recibo**

Em `doacoes/views.py`, remover o dicionário fixo de `ReciboView.get_context_data`:
```python
    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["emitido_em"] = timezone.localtime()
        contexto["emitido_por"] = self.request.user
        return contexto
```

Em `templates/doacoes/recibo.html`, o cabeçalho passa a usar o context processor:
```html
  <div class="cabecalho">
    <h1>{{ instituicao.nome }}</h1>
    {% if instituicao.cnpj_formatado %}<p>CNPJ {{ instituicao.cnpj_formatado }}</p>{% endif %}
    {% if instituicao.endereco %}<p>{{ instituicao.endereco }}</p>{% endif %}
  </div>
```

E a assinatura:
```html
  <div class="assinatura">
    <div class="linha"></div>
    <div>{{ instituicao.responsavel_legal|default:instituicao.nome }}</div>
  </div>
```

- [ ] **Step 6: Escrever o template de configuração**

`templates/core/configuracao_form.html` segue o esqueleto de formulário das
fases anteriores, com título "Configuração da instituição", e este aviso acima
do formulário:

```html
  <div class="alert alert-info">
    Estes dados aparecem em recibos e relatórios de prestação de contas.
    Confirme o CNPJ e o endereço com a coordenação antes de preencher.
  </div>
```

- [ ] **Step 7: Migration e testes**

```powershell
$env:USE_DIRECT_DB = "1"
python manage.py makemigrations core
python manage.py migrate
$env:USE_DIRECT_DB = ""
```

```bash
pytest core/tests/test_configuracao.py doacoes/tests/test_recibo.py -v --create-db
```

- [ ] **Step 8: Commit**

```bash
git add core templates/core doacoes templates/doacoes comviver/settings/base.py
git commit -m "feat(core): adiciona configuracao da instituicao usada em recibos"
```

---

## Task 2: Motor de relatórios — dados e renderizadores

Escrito antes de qualquer relatório específico. Cada relatório passa a ser uma
função de poucas linhas.

**Files:**
- Create: `relatorios/` (app completo), `relatorios/services.py`, `relatorios/renderers.py`
- Create: `relatorios/tests/test_renderers.py`
- Create: `templates/relatorios/base_relatorio.html`, `base_impressao.html`
- Modify: `comviver/settings/base.py`

**Interfaces:**
- Consumes: `core.pdf.renderizar_pdf`, `core.models.ConfiguracaoInstituicao`
- Produces:
  - `relatorios.services.Relatorio` — dataclass com `titulo`, `subtitulo`, `colunas: list[str]`, `linhas: list[list]`, `resumo: list[dict]`, `sigiloso: bool`
  - `relatorios.renderers.renderizar(relatorio, formato, request)` — devolve `HttpResponse` para `tela`, `csv` ou `pdf`

- [ ] **Step 1: Escrever os testes que falham**

`relatorios/tests/test_renderers.py`:
```python
import csv
import io

import pytest
from django.test import RequestFactory

from relatorios.renderers import renderizar
from relatorios.services import Relatorio

pytestmark = pytest.mark.django_db


def _relatorio(sigiloso=False):
    return Relatorio(
        titulo="Teste",
        subtitulo="Período de teste",
        colunas=["Nome", "Idade"],
        linhas=[["Ana", 10], ["Bruno", 12]],
        resumo=[{"rotulo": "Total", "valor": 2}],
        sigiloso=sigiloso,
    )


@pytest.fixture
def requisicao(usuario_admin):
    pedido = RequestFactory().get("/relatorios/teste/")
    pedido.user = usuario_admin
    return pedido


class TestCSV:
    def test_devolve_content_type_de_csv(self, requisicao):
        resposta = renderizar(_relatorio(), "csv", requisicao)
        assert resposta["Content-Type"].startswith("text/csv")

    def test_primeira_linha_e_o_cabecalho(self, requisicao):
        resposta = renderizar(_relatorio(), "csv", requisicao)
        linhas = list(csv.reader(io.StringIO(resposta.content.decode("utf-8-sig"))))
        assert linhas[0] == ["Nome", "Idade"]

    def test_dados_vem_depois_do_cabecalho(self, requisicao):
        resposta = renderizar(_relatorio(), "csv", requisicao)
        linhas = list(csv.reader(io.StringIO(resposta.content.decode("utf-8-sig"))))
        assert linhas[1] == ["Ana", "10"]

    def test_usa_ponto_e_virgula_e_bom(self, requisicao):
        """Excel em portugues abre CSV com virgula numa coluna so; ponto e
        virgula mais BOM e o que funciona na maquina da contabilidade."""
        resposta = renderizar(_relatorio(), "csv", requisicao)
        conteudo = resposta.content
        assert conteudo.startswith(b"\xef\xbb\xbf")
        assert b";" in conteudo

    def test_nome_do_arquivo_vem_do_titulo(self, requisicao):
        resposta = renderizar(_relatorio(), "csv", requisicao)
        assert "teste.csv" in resposta["Content-Disposition"]


class TestPDF:
    def test_devolve_pdf(self, requisicao):
        resposta = renderizar(_relatorio(), "pdf", requisicao)
        assert resposta["Content-Type"] == "application/pdf"
        assert resposta.content[:4] == b"%PDF"


class TestTela:
    def test_devolve_html_com_as_linhas(self, requisicao):
        resposta = renderizar(_relatorio(), "tela", requisicao)
        conteudo = resposta.render().content.decode()
        assert "Ana" in conteudo
        assert "Bruno" in conteudo

    def test_formato_desconhecido_cai_na_tela(self, requisicao):
        resposta = renderizar(_relatorio(), "xlsx", requisicao)
        assert resposta.status_code == 200


class TestMarcaDeSigilo:
    def test_relatorio_sigiloso_marca_o_pdf(self, requisicao):
        from relatorios.renderers import montar_contexto

        contexto = montar_contexto(_relatorio(sigiloso=True), requisicao)
        assert contexto["sigiloso"] is True

    def test_contexto_registra_quem_emitiu(self, requisicao, usuario_admin):
        from relatorios.renderers import montar_contexto

        contexto = montar_contexto(_relatorio(), requisicao)
        assert contexto["emitido_por"] == usuario_admin
        assert contexto["emitido_em"] is not None
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest relatorios/tests/test_renderers.py -v
```
Esperado: `ModuleNotFoundError: No module named 'relatorios'`.

- [ ] **Step 3: Criar o app**

```bash
python manage.py startapp relatorios
mkdir relatorios/tests && touch relatorios/tests/__init__.py
rm relatorios/tests.py relatorios/models.py
```

`relatorios` não tem models: é folha do grafo, só lê.

`relatorios/apps.py`:
```python
from django.apps import AppConfig


class RelatoriosConfig(AppConfig):
    name = "relatorios"
    verbose_name = "Relatórios"
```

Em `comviver/settings/base.py`, `INSTALLED_APPS`:
```python
    "relatorios",
```

- [ ] **Step 4: Escrever a estrutura de dados em `relatorios/services.py`**

```python
from dataclasses import dataclass, field


@dataclass
class Relatorio:
    """Saida de qualquer relatorio, independente do formato de apresentacao.

    Separar dados de apresentacao e o que permite que um relatorio novo seja
    uma funcao, e nao uma tela inteira: os tres renderizadores ja sabem o que
    fazer com esta estrutura.
    """

    titulo: str
    colunas: list[str]
    linhas: list[list]
    subtitulo: str = ""
    resumo: list[dict] = field(default_factory=list)
    sigiloso: bool = False

    @property
    def nome_arquivo(self) -> str:
        from unicodedata import normalize

        base = normalize("NFKD", self.titulo).encode("ascii", "ignore").decode()
        return base.lower().replace(" ", "-").replace("/", "-")
```

- [ ] **Step 5: Escrever `relatorios/renderers.py`**

```python
import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.models import ConfiguracaoInstituicao
from core.pdf import renderizar_pdf
from relatorios.services import Relatorio


def montar_contexto(relatorio: Relatorio, request) -> dict:
    return {
        "relatorio": relatorio,
        "sigiloso": relatorio.sigiloso,
        "instituicao": ConfiguracaoInstituicao.obter(),
        "emitido_em": timezone.localtime(),
        "emitido_por": request.user,
    }


def _csv(relatorio: Relatorio) -> HttpResponse:
    """CSV para o Excel em portugues: separador ponto e virgula e BOM.

    Com virgula e sem BOM, a contabilidade abre tudo numa coluna so, com
    acentos quebrados — e conclui que o sistema nao funciona.
    """
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        f'attachment; filename="{relatorio.nome_arquivo}.csv"'
    )
    resposta.write("﻿")

    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow(relatorio.colunas)
    for linha in relatorio.linhas:
        escritor.writerow(linha)
    return resposta


def renderizar(relatorio: Relatorio, formato: str, request) -> HttpResponse:
    contexto = montar_contexto(relatorio, request)

    if formato == "csv":
        return _csv(relatorio)

    if formato == "pdf":
        return renderizar_pdf(
            "relatorios/base_impressao.html",
            contexto,
            f"{relatorio.nome_arquivo}.pdf",
            request=request,
        )

    return render(request, "relatorios/base_relatorio.html", contexto)
```

- [ ] **Step 6: Escrever os dois layouts**

`templates/relatorios/base_relatorio.html`:
```html
{% extends "base.html" %}
{% block titulo %}{{ relatorio.titulo }}{% endblock %}
{% block cabecalho %}{{ relatorio.titulo }}{% endblock %}

{% block acoes %}
  <a href="?{{ request.GET.urlencode }}&formato=csv" class="btn btn-outline-secondary">
    <i class="bi bi-filetype-csv"></i> CSV
  </a>
  <a href="?{{ request.GET.urlencode }}&formato=pdf" class="btn btn-outline-secondary">
    <i class="bi bi-filetype-pdf"></i> PDF
  </a>
{% endblock %}

{% block conteudo %}
  {% if relatorio.subtitulo %}
    <p class="text-muted">{{ relatorio.subtitulo }}</p>
  {% endif %}

  {% if sigiloso %}
    <div class="alert alert-warning py-2">
      <i class="bi bi-shield-lock"></i>
      Este relatório contém informação sigilosa. Não divulgue fora da instituição.
    </div>
  {% endif %}

  {% block filtros %}{% endblock %}

  {% if relatorio.resumo %}
    <div class="row g-2 mb-3">
      {% for item in relatorio.resumo %}
        <div class="col-6 col-md-3">
          <div class="card">
            <div class="card-body py-2 px-3">
              <div class="text-muted small">{{ item.rotulo }}</div>
              <div class="h5 mb-0">{{ item.valor }}</div>
            </div>
          </div>
        </div>
      {% endfor %}
    </div>
  {% endif %}

  <div class="table-responsive">
    <table class="table table-sm table-hover">
      <thead>
        <tr>{% for coluna in relatorio.colunas %}<th>{{ coluna }}</th>{% endfor %}</tr>
      </thead>
      <tbody>
        {% for linha in relatorio.linhas %}
          <tr>{% for celula in linha %}<td>{{ celula }}</td>{% endfor %}</tr>
        {% empty %}
          <tr>
            <td colspan="{{ relatorio.colunas|length }}" class="text-muted">
              Nenhum registro no período selecionado.
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% endblock %}
```

`templates/relatorios/base_impressao.html`:
```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>{{ relatorio.titulo }}</title>
  <style>
    @page {
      size: A4 landscape; margin: 1.8cm;
      @bottom-center { content: "Página " counter(page) " de " counter(pages);
                       font-size: 8pt; color: #777; }
    }
    body { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 9pt; color: #1a1a1a; }
    .cabecalho { border-bottom: 2px solid #2a6f4e; padding-bottom: .6rem; margin-bottom: 1rem; }
    .cabecalho h1 { font-size: 13pt; margin: 0; }
    .cabecalho .instituicao { font-size: 8pt; color: #555; margin: 0; }
    .subtitulo { color: #555; margin: .2rem 0 0; font-size: 9pt; }
    .sigilo { background: #fff3cd; border: 1px solid #ffe69c; padding: .4rem .6rem;
              margin: .8rem 0; font-size: 8pt; }
    .resumo { display: flex; gap: 1.5rem; margin: .8rem 0; }
    .resumo div { font-size: 8pt; }
    .resumo strong { display: block; font-size: 12pt; }
    table { width: 100%; border-collapse: collapse; margin-top: .6rem; }
    th { background: #f2f2f2; text-align: left; padding: .35rem .5rem;
         border-bottom: 1.5px solid #999; font-size: 8pt; }
    td { padding: .3rem .5rem; border-bottom: .5px solid #ddd; }
    tr { page-break-inside: avoid; }
    .rodape { margin-top: 1.5rem; font-size: 7.5pt; color: #777;
              border-top: .5px solid #ddd; padding-top: .4rem; }
  </style>
</head>
<body>
  <div class="cabecalho">
    <p class="instituicao">
      {{ instituicao.nome }}
      {% if instituicao.cnpj_formatado %}· CNPJ {{ instituicao.cnpj_formatado }}{% endif %}
    </p>
    <h1>{{ relatorio.titulo }}</h1>
    {% if relatorio.subtitulo %}<p class="subtitulo">{{ relatorio.subtitulo }}</p>{% endif %}
  </div>

  {% if sigiloso %}
    <div class="sigilo">
      <strong>DOCUMENTO SIGILOSO.</strong>
      Contém informação que identifica criança ou adolescente acolhido.
      A divulgação é vedada pelo art. 143 do Estatuto da Criança e do Adolescente.
      Emitido por {{ emitido_por.get_full_name }} em {{ emitido_em|date:"d/m/Y H:i" }}.
    </div>
  {% endif %}

  {% if relatorio.resumo %}
    <div class="resumo">
      {% for item in relatorio.resumo %}
        <div>{{ item.rotulo }}<strong>{{ item.valor }}</strong></div>
      {% endfor %}
    </div>
  {% endif %}

  <table>
    <thead>
      <tr>{% for coluna in relatorio.colunas %}<th>{{ coluna }}</th>{% endfor %}</tr>
    </thead>
    <tbody>
      {% for linha in relatorio.linhas %}
        <tr>{% for celula in linha %}<td>{{ celula }}</td>{% endfor %}</tr>
      {% empty %}
        <tr>
          <td colspan="{{ relatorio.colunas|length }}">Nenhum registro no período.</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>

  <p class="rodape">
    Emitido em {{ emitido_em|date:"d/m/Y H:i" }} por {{ emitido_por.get_full_name }}
    · Sistema ComViver
  </p>
</body>
</html>
```

- [ ] **Step 7: Rodar os testes**

```bash
pytest relatorios/tests/test_renderers.py -v
```
Esperado: 11 testes passando.

- [ ] **Step 8: Commit**

```bash
git add relatorios templates/relatorios comviver/settings/base.py
git commit -m "feat(relatorios): adiciona motor com renderizacao em tela, CSV e PDF"
```

---

## Task 3: Os oito relatórios

**Files:**
- Modify: `relatorios/services.py`
- Create: `relatorios/forms.py`, `relatorios/views.py`, `relatorios/urls.py`
- Create: `templates/relatorios/indice.html`
- Create: `relatorios/tests/test_services.py`, `test_permissoes.py`, `test_sigilo.py`
- Modify: `comviver/urls.py`, `core/context_processors.py`

**Interfaces:**
- Consumes: `relatorios.services.Relatorio`, `relatorios.renderers.renderizar`
- Produces: oito funções em `services.py`, cada uma com assinatura
  `(inicio: date | None, fim: date | None, **extra) -> Relatorio`; rota
  `relatorios:ver` com parâmetro `slug`

- [ ] **Step 1: Escrever os testes que falham**

`relatorios/tests/test_services.py`:
```python
from datetime import date, timedelta
from decimal import Decimal

import pytest

from relatorios import services

pytestmark = pytest.mark.django_db


class TestAcolhidosAtivos:
    def test_lista_apenas_acolhidos(self):
        from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory
        from acolhidos.models import StatusAcolhido

        ativo = AcolhidoFactory(nome="Ana Clara")
        FichaAcolhimentoFactory(acolhido=ativo, data_entrada=date.today() - timedelta(days=30))
        desligado = AcolhidoFactory(nome="Bruno", status=StatusAcolhido.DESLIGADO)
        FichaAcolhimentoFactory(acolhido=desligado)

        relatorio = services.acolhidos_ativos(None, None)
        nomes = [linha[0] for linha in relatorio.linhas]
        assert "Ana Clara" in nomes
        assert "Bruno" not in nomes

    def test_marca_como_sigiloso(self):
        assert services.acolhidos_ativos(None, None).sigiloso is True

    def test_resumo_traz_o_total(self):
        from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory

        for _ in range(3):
            FichaAcolhimentoFactory(acolhido=AcolhidoFactory())
        relatorio = services.acolhidos_ativos(None, None)
        assert relatorio.resumo[0]["valor"] == 3

    def test_traz_o_tempo_de_acolhimento(self):
        from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory

        acolhido = AcolhidoFactory(nome="Ana Clara")
        FichaAcolhimentoFactory(
            acolhido=acolhido, data_entrada=date.today() - timedelta(days=45)
        )
        relatorio = services.acolhidos_ativos(None, None)
        assert "45" in str(relatorio.linhas[0])


class TestMovimentacao:
    def test_conta_entradas_no_periodo(self):
        from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory

        FichaAcolhimentoFactory(
            acolhido=AcolhidoFactory(), data_entrada=date.today() - timedelta(days=10)
        )
        FichaAcolhimentoFactory(
            acolhido=AcolhidoFactory(), data_entrada=date.today() - timedelta(days=200)
        )
        relatorio = services.movimentacao(date.today() - timedelta(days=30), date.today())
        assert len(relatorio.linhas) == 1

    def test_inclui_desligamentos_no_periodo(self):
        from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory
        from acolhidos.models import StatusAcolhido

        acolhido = AcolhidoFactory(status=StatusAcolhido.DESLIGADO)
        FichaAcolhimentoFactory(
            acolhido=acolhido,
            data_entrada=date.today() - timedelta(days=300),
            data_desligamento=date.today() - timedelta(days=5),
        )
        relatorio = services.movimentacao(date.today() - timedelta(days=30), date.today())
        assert any("Desligamento" in str(linha) for linha in relatorio.linhas)


class TestDoacoesPorPeriodo:
    def test_agrupa_por_tipo(self):
        from doacoes.factories import DoacaoFactory
        from doacoes.models import TipoDoacao

        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(tipo=TipoDoacao.ALIMENTO, valor=None, descricao="Arroz")
        relatorio = services.doacoes_por_periodo(None, None)
        assert len(relatorio.linhas) == 2

    def test_nao_e_sigiloso(self):
        """Doacao nao identifica acolhido: pode circular."""
        assert services.doacoes_por_periodo(None, None).sigiloso is False

    def test_respeita_o_periodo(self):
        from doacoes.factories import DoacaoFactory
        from doacoes.models import TipoDoacao

        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(
            tipo=TipoDoacao.DINHEIRO, valor=Decimal("999.00"),
            data_recebimento=date.today() - timedelta(days=200),
        )
        relatorio = services.doacoes_por_periodo(
            date.today() - timedelta(days=30), date.today()
        )
        assert relatorio.resumo[0]["valor"] == "R$ 100,00"


class TestPrestacaoDeContas:
    def test_nao_identifica_acolhido(self):
        """Documento para publico externo: agregado, sem identificacao."""
        from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory

        acolhido = AcolhidoFactory(nome="Ana Clara Souza")
        FichaAcolhimentoFactory(acolhido=acolhido)
        relatorio = services.prestacao_de_contas(
            date.today() - timedelta(days=30), date.today()
        )
        assert "Ana Clara Souza" not in str(relatorio.linhas)
        assert relatorio.sigiloso is False

    def test_traz_o_numero_de_atendidos(self):
        from acolhidos.factories import AcolhidoFactory, FichaAcolhimentoFactory

        for _ in range(4):
            FichaAcolhimentoFactory(acolhido=AcolhidoFactory())
        relatorio = services.prestacao_de_contas(
            date.today() - timedelta(days=30), date.today()
        )
        assert any("4" in str(linha) for linha in relatorio.linhas)


class TestFrequenciaEmEscala:
    def test_conta_previsto_confirmado_e_falta(self):
        from escalas.factories import AlocacaoFactory, TurnoFactory
        from escalas.models import StatusAlocacao
        from voluntarios.factories import VoluntarioFactory

        voluntario = VoluntarioFactory(nome="Ana Souza")
        AlocacaoFactory(
            voluntario=voluntario, turno=TurnoFactory(), status=StatusAlocacao.CONFIRMADO
        )
        AlocacaoFactory(
            voluntario=voluntario,
            turno=TurnoFactory(data=date.today() + timedelta(days=1)),
            status=StatusAlocacao.FALTOU,
        )

        relatorio = services.frequencia_em_escala(None, None)
        linha = next(l for l in relatorio.linhas if l[0] == "Ana Souza")
        assert linha[1] == 2  # total
        assert linha[2] == 1  # compareceu
        assert linha[3] == 1  # faltou

    def test_calcula_o_percentual_de_comparecimento(self):
        from escalas.factories import AlocacaoFactory, TurnoFactory
        from escalas.models import StatusAlocacao
        from voluntarios.factories import VoluntarioFactory

        voluntario = VoluntarioFactory(nome="Ana Souza")
        for deslocamento in range(4):
            AlocacaoFactory(
                voluntario=voluntario,
                turno=TurnoFactory(data=date.today() + timedelta(days=deslocamento)),
                status=StatusAlocacao.CONFIRMADO if deslocamento < 3 else StatusAlocacao.FALTOU,
            )
        relatorio = services.frequencia_em_escala(None, None)
        linha = next(l for l in relatorio.linhas if l[0] == "Ana Souza")
        assert "75" in str(linha[-1])


class TestHistoricoDoDoador:
    def test_lista_as_doacoes_e_o_total(self):
        from doacoes.factories import DoacaoFactory, DoadorFactory
        from doacoes.models import TipoDoacao

        doador = DoadorFactory(nome="Padaria Central")
        DoacaoFactory(doador=doador, tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(doador=doador, tipo=TipoDoacao.DINHEIRO, valor=Decimal("50.00"))

        relatorio = services.historico_do_doador(None, None, doador_id=doador.pk)
        assert len(relatorio.linhas) == 2
        assert "150,00" in str(relatorio.resumo)


class TestVoluntariosAtivos:
    def test_lista_apenas_ativos(self):
        from voluntarios.factories import VoluntarioFactory
        from voluntarios.models import StatusVoluntario

        VoluntarioFactory(nome="Ana Souza")
        VoluntarioFactory(nome="Inativo Silva", status=StatusVoluntario.INATIVO)
        relatorio = services.voluntarios_ativos(None, None)
        nomes = [linha[0] for linha in relatorio.linhas]
        assert "Ana Souza" in nomes
        assert "Inativo Silva" not in nomes
```

`relatorios/tests/test_sigilo.py`:
```python
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

SIGILOSOS = ["acolhidos-ativos", "movimentacao"]
ABERTOS = ["doacoes-periodo", "voluntarios-ativos", "frequencia-escala"]


class TestRelatoriosSigilosos:
    @pytest.mark.parametrize("slug", SIGILOSOS)
    def test_operacional_recebe_403(self, client, usuario_operacional, slug):
        client.force_login(usuario_operacional)
        assert client.get(reverse("relatorios:ver", args=[slug])).status_code == 403

    @pytest.mark.parametrize("slug", SIGILOSOS)
    def test_tecnico_acessa(self, client, usuario_tecnico, slug):
        client.force_login(usuario_tecnico)
        assert client.get(reverse("relatorios:ver", args=[slug])).status_code == 200

    @pytest.mark.parametrize("slug", SIGILOSOS)
    def test_pdf_sai_com_marca_de_sigilo(self, client, usuario_tecnico, slug):
        client.force_login(usuario_tecnico)
        resposta = client.get(reverse("relatorios:ver", args=[slug]) + "?formato=pdf")
        assert resposta.status_code == 200
        assert resposta["Content-Type"] == "application/pdf"

    def test_tela_sigilosa_exibe_o_aviso(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        conteudo = client.get(
            reverse("relatorios:ver", args=["acolhidos-ativos"])
        ).content.decode()
        assert "informação sigilosa" in conteudo.lower()


class TestRelatoriosAbertos:
    @pytest.mark.parametrize("slug", ABERTOS)
    @pytest.mark.parametrize(
        "fixture_usuario", ["usuario_admin", "usuario_tecnico", "usuario_operacional"]
    )
    def test_todos_os_perfis_acessam(self, client, request, fixture_usuario, slug):
        client.force_login(request.getfixturevalue(fixture_usuario))
        assert client.get(reverse("relatorios:ver", args=[slug])).status_code == 200


class TestPrestacaoDeContas:
    def test_so_admin_acessa(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get(
            reverse("relatorios:ver", args=["prestacao-contas"])
        ).status_code == 403

    def test_admin_acessa(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(
            reverse("relatorios:ver", args=["prestacao-contas"])
        ).status_code == 200


class TestIndice:
    def test_operacional_nao_ve_relatorio_sigiloso_no_indice(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("relatorios:indice")).content.decode()
        assert "Acolhidos ativos" not in conteudo

    def test_tecnico_ve_relatorio_sigiloso_no_indice(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        conteudo = client.get(reverse("relatorios:indice")).content.decode()
        assert "Acolhidos ativos" in conteudo

    def test_slug_desconhecido_devolve_404(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("relatorios:ver", args=["inexistente"])).status_code == 404
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest relatorios/tests/ -v
```
Esperado: `AttributeError: module 'relatorios.services' has no attribute 'acolhidos_ativos'`.

- [ ] **Step 3: Escrever os oito relatórios**

Acrescentar a `relatorios/services.py`:

```python
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum


def _reais(valor) -> str:
    valor = valor or Decimal("0")
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _periodo(inicio, fim) -> str:
    if inicio and fim:
        return f"Período de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
    if inicio:
        return f"A partir de {inicio:%d/%m/%Y}"
    if fim:
        return f"Até {fim:%d/%m/%Y}"
    return "Todos os registros"


def acolhidos_ativos(inicio, fim, **extra) -> Relatorio:
    from acolhidos.models import Acolhido, StatusAcolhido

    consulta = (
        Acolhido.objects.filter(status=StatusAcolhido.ACOLHIDO)
        .select_related("ficha")
        .order_by("nome")
    )

    linhas = [
        [
            acolhido.nome_exibicao,
            acolhido.idade,
            acolhido.ficha.data_entrada.strftime("%d/%m/%Y") if hasattr(acolhido, "ficha") else "—",
            acolhido.tempo_acolhimento if acolhido.tempo_acolhimento is not None else "—",
            acolhido.ficha.orgao_requisitante if hasattr(acolhido, "ficha") else "—",
        ]
        for acolhido in consulta
    ]

    return Relatorio(
        titulo="Acolhidos ativos",
        subtitulo=f"Posição em {date.today():%d/%m/%Y}",
        colunas=["Nome", "Idade", "Entrada", "Dias acolhido", "Órgão requisitante"],
        linhas=linhas,
        resumo=[{"rotulo": "Total", "valor": len(linhas)}],
        sigiloso=True,
    )


def movimentacao(inicio, fim, **extra) -> Relatorio:
    from acolhidos.models import FichaAcolhimento

    entradas = FichaAcolhimento.objects.select_related("acolhido")
    if inicio:
        entradas = entradas.filter(data_entrada__gte=inicio)
    if fim:
        entradas = entradas.filter(data_entrada__lte=fim)

    saidas = FichaAcolhimento.objects.select_related("acolhido").filter(
        data_desligamento__isnull=False
    )
    if inicio:
        saidas = saidas.filter(data_desligamento__gte=inicio)
    if fim:
        saidas = saidas.filter(data_desligamento__lte=fim)

    linhas = [
        [ficha.data_entrada.strftime("%d/%m/%Y"), "Entrada",
         ficha.acolhido.nome_exibicao, ficha.motivo or "—"]
        for ficha in entradas
    ] + [
        [ficha.data_desligamento.strftime("%d/%m/%Y"), "Desligamento",
         ficha.acolhido.nome_exibicao, ficha.destino or "—"]
        for ficha in saidas
    ]
    linhas.sort(key=lambda linha: linha[0])

    return Relatorio(
        titulo="Movimentação de acolhimento",
        subtitulo=_periodo(inicio, fim),
        colunas=["Data", "Tipo", "Acolhido", "Motivo / Destino"],
        linhas=linhas,
        resumo=[
            {"rotulo": "Entradas", "valor": entradas.count()},
            {"rotulo": "Desligamentos", "valor": saidas.count()},
        ],
        sigiloso=True,
    )


def doacoes_por_periodo(inicio, fim, **extra) -> Relatorio:
    from doacoes.models import Doacao
    from doacoes.services import total_arrecadado, totais_por_tipo

    consulta = Doacao.objects.all()
    if inicio:
        consulta = consulta.filter(data_recebimento__gte=inicio)
    if fim:
        consulta = consulta.filter(data_recebimento__lte=fim)

    linhas = [
        [linha["rotulo"], linha["quantidade"], _reais(linha["soma"])]
        for linha in totais_por_tipo(consulta)
    ]

    return Relatorio(
        titulo="Doações por período",
        subtitulo=_periodo(inicio, fim),
        colunas=["Tipo", "Quantidade de registros", "Valor total"],
        linhas=linhas,
        resumo=[
            {"rotulo": "Registros", "valor": consulta.count()},
            {"rotulo": "Arrecadado", "valor": _reais(total_arrecadado(consulta))},
        ],
    )


def historico_do_doador(inicio, fim, doador_id=None, **extra) -> Relatorio:
    from doacoes.models import Doacao, Doador

    if not doador_id:
        return Relatorio(
            titulo="Histórico do doador",
            subtitulo="Escolha um doador para gerar o relatório.",
            colunas=["Data", "Tipo", "Item", "Quantidade"],
            linhas=[],
        )

    doador = Doador.objects.get(pk=doador_id)
    consulta = Doacao.objects.filter(doador=doador).order_by("-data_recebimento")
    if inicio:
        consulta = consulta.filter(data_recebimento__gte=inicio)
    if fim:
        consulta = consulta.filter(data_recebimento__lte=fim)

    linhas = [
        [
            doacao.data_recebimento.strftime("%d/%m/%Y"),
            doacao.get_tipo_display(),
            doacao.descricao or "—",
            doacao.descricao_quantidade,
        ]
        for doacao in consulta
    ]
    soma = consulta.aggregate(total=Sum("valor"))["total"]

    return Relatorio(
        titulo=f"Histórico — {doador.nome}",
        subtitulo=_periodo(inicio, fim),
        colunas=["Data", "Tipo", "Item", "Quantidade"],
        linhas=linhas,
        resumo=[
            {"rotulo": "Doações", "valor": len(linhas)},
            {"rotulo": "Total em dinheiro", "valor": _reais(soma)},
        ],
    )


def prestacao_de_contas(inicio, fim, **extra) -> Relatorio:
    """Documento para o conselho, o CMDCA e os mantenedores.

    Usa apenas dados agregados: o publico externo precisa saber quantas
    criancas foram atendidas, nao quais.
    """
    from acolhidos.models import Acolhido, FichaAcolhimento, StatusAcolhido
    from doacoes.models import Doacao
    from doacoes.services import total_arrecadado, totais_por_tipo
    from escalas.models import Alocacao, StatusAlocacao

    doacoes = Doacao.objects.all()
    entradas = FichaAcolhimento.objects.all()
    saidas = FichaAcolhimento.objects.filter(data_desligamento__isnull=False)
    presencas = Alocacao.objects.filter(status=StatusAlocacao.CONFIRMADO)

    if inicio:
        doacoes = doacoes.filter(data_recebimento__gte=inicio)
        entradas = entradas.filter(data_entrada__gte=inicio)
        saidas = saidas.filter(data_desligamento__gte=inicio)
        presencas = presencas.filter(turno__data__gte=inicio)
    if fim:
        doacoes = doacoes.filter(data_recebimento__lte=fim)
        entradas = entradas.filter(data_entrada__lte=fim)
        saidas = saidas.filter(data_desligamento__lte=fim)
        presencas = presencas.filter(turno__data__lte=fim)

    linhas = [
        ["Crianças e adolescentes atendidos no período",
         Acolhido.objects.filter(status=StatusAcolhido.ACOLHIDO).count()],
        ["Novos acolhimentos", entradas.count()],
        ["Desligamentos", saidas.count()],
        ["Doações recebidas", doacoes.count()],
        ["Total arrecadado em dinheiro", _reais(total_arrecadado(doacoes))],
        ["Participações de voluntários confirmadas", presencas.count()],
    ]
    linhas += [
        [f"Doações — {linha['rotulo'].lower()}", linha["quantidade"]]
        for linha in totais_por_tipo(doacoes)
    ]

    return Relatorio(
        titulo="Prestação de contas",
        subtitulo=_periodo(inicio, fim),
        colunas=["Indicador", "Valor"],
        linhas=linhas,
        sigiloso=False,
    )


def voluntarios_ativos(inicio, fim, **extra) -> Relatorio:
    from voluntarios.models import StatusVoluntario, Voluntario

    consulta = (
        Voluntario.objects.filter(status=StatusVoluntario.ATIVO)
        .prefetch_related("funcoes", "disponibilidades")
        .order_by("nome")
    )

    linhas = [
        [
            voluntario.nome,
            voluntario.telefone or "—",
            ", ".join(f.nome for f in voluntario.funcoes.all()) or "—",
            voluntario.resumo_disponibilidade,
            voluntario.data_cadastro.strftime("%d/%m/%Y"),
        ]
        for voluntario in consulta
    ]

    return Relatorio(
        titulo="Voluntários ativos",
        subtitulo=f"Posição em {date.today():%d/%m/%Y}",
        colunas=["Nome", "Telefone", "Funções", "Disponibilidade", "Desde"],
        linhas=linhas,
        resumo=[{"rotulo": "Total", "valor": len(linhas)}],
    )


def frequencia_em_escala(inicio, fim, **extra) -> Relatorio:
    from escalas.models import StatusAlocacao
    from voluntarios.models import Voluntario

    filtro = Q()
    if inicio:
        filtro &= Q(alocacoes__turno__data__gte=inicio)
    if fim:
        filtro &= Q(alocacoes__turno__data__lte=fim)

    consulta = (
        Voluntario.objects.annotate(
            total=Count("alocacoes", filter=filtro),
            compareceu=Count(
                "alocacoes", filter=filtro & Q(alocacoes__status=StatusAlocacao.CONFIRMADO)
            ),
            faltou=Count(
                "alocacoes", filter=filtro & Q(alocacoes__status=StatusAlocacao.FALTOU)
            ),
        )
        .filter(total__gt=0)
        .order_by("nome")
    )

    linhas = []
    for voluntario in consulta:
        registrados = voluntario.compareceu + voluntario.faltou
        percentual = round(voluntario.compareceu / registrados * 100) if registrados else 0
        linhas.append(
            [
                voluntario.nome,
                voluntario.total,
                voluntario.compareceu,
                voluntario.faltou,
                f"{percentual}%",
            ]
        )

    return Relatorio(
        titulo="Frequência em escalas",
        subtitulo=_periodo(inicio, fim),
        colunas=["Voluntário", "Escalado", "Compareceu", "Faltou", "Comparecimento"],
        linhas=linhas,
        resumo=[{"rotulo": "Voluntários escalados", "valor": len(linhas)}],
    )


def turnos_descobertos(inicio, fim, **extra) -> Relatorio:
    from escalas.services import turnos_descobertos_proximos

    consulta = turnos_descobertos_proximos(dias=30)

    linhas = [
        [
            turno.data.strftime("%d/%m/%Y"),
            f"{turno.hora_inicio:%H:%M}–{turno.hora_fim:%H:%M}",
            turno.atividade.nome,
            f"{turno.vagas_ocupadas}/{turno.vagas}",
            turno.escala.titulo,
        ]
        for turno in consulta
    ]

    return Relatorio(
        titulo="Turnos sem voluntário",
        subtitulo="Próximos 30 dias",
        colunas=["Data", "Horário", "Atividade", "Vagas preenchidas", "Escala"],
        linhas=linhas,
        resumo=[{"rotulo": "Turnos descobertos", "valor": len(linhas)}],
    )
```

- [ ] **Step 4: Escrever o catálogo, as views e as URLs**

Ao fim de `relatorios/services.py`:
```python
from accounts.models import Perfil

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
EQUIPE_TECNICA = [Perfil.ADMIN, Perfil.TECNICO]

CATALOGO = {
    "acolhidos-ativos": {
        "funcao": acolhidos_ativos,
        "rotulo": "Acolhidos ativos",
        "descricao": "Quem está em acolhimento hoje, com tempo de permanência.",
        "perfis": EQUIPE_TECNICA,
        "pede_periodo": False,
    },
    "movimentacao": {
        "funcao": movimentacao,
        "rotulo": "Movimentação de acolhimento",
        "descricao": "Entradas e desligamentos no período, com motivo e destino.",
        "perfis": EQUIPE_TECNICA,
        "pede_periodo": True,
    },
    "doacoes-periodo": {
        "funcao": doacoes_por_periodo,
        "rotulo": "Doações por período",
        "descricao": "Agrupado por tipo, com quantidade e valor.",
        "perfis": TODOS_OS_PERFIS,
        "pede_periodo": True,
    },
    "historico-doador": {
        "funcao": historico_do_doador,
        "rotulo": "Histórico do doador",
        "descricao": "Tudo que um doador já doou, com soma.",
        "perfis": [Perfil.ADMIN, Perfil.OPERACIONAL],
        "pede_periodo": True,
        "pede_doador": True,
    },
    "prestacao-contas": {
        "funcao": prestacao_de_contas,
        "rotulo": "Prestação de contas",
        "descricao": "Indicadores agregados, sem identificação, para o conselho.",
        "perfis": [Perfil.ADMIN],
        "pede_periodo": True,
    },
    "voluntarios-ativos": {
        "funcao": voluntarios_ativos,
        "rotulo": "Voluntários ativos",
        "descricao": "Cadastro, funções e disponibilidade declarada.",
        "perfis": TODOS_OS_PERFIS,
        "pede_periodo": False,
    },
    "frequencia-escala": {
        "funcao": frequencia_em_escala,
        "rotulo": "Frequência em escalas",
        "descricao": "Previsto, compareceu e faltou, por voluntário.",
        "perfis": TODOS_OS_PERFIS,
        "pede_periodo": True,
    },
    "turnos-descobertos": {
        "funcao": turnos_descobertos,
        "rotulo": "Turnos sem voluntário",
        "descricao": "Onde estão os buracos nos próximos 30 dias.",
        "perfis": TODOS_OS_PERFIS,
        "pede_periodo": False,
    },
}
```

`relatorios/forms.py`:
```python
from django import forms

from doacoes.models import Doador


class FiltroForm(forms.Form):
    inicio = forms.DateField(
        label="De", required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    fim = forms.DateField(
        label="Até", required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    doador = forms.ModelChoiceField(
        label="Doador", queryset=Doador.objects.all(), required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, pede_periodo=True, pede_doador=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not pede_periodo:
            self.fields.pop("inicio")
            self.fields.pop("fim")
        if not pede_doador:
            self.fields.pop("doador")

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("inicio"), dados.get("fim")
        if inicio and fim and fim < inicio:
            self.add_error("fim", "A data final não pode ser anterior à inicial.")
        return dados
```

`relatorios/views.py`:
```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.views import View

from relatorios.forms import FiltroForm
from relatorios.renderers import montar_contexto, renderizar
from relatorios.services import CATALOGO


class IndiceView(LoginRequiredMixin, View):
    """Indice dos relatorios, filtrado pelo perfil.

    Relatorio que o usuario nao pode abrir nao aparece, em vez de aparecer e
    retornar 403.
    """

    def get(self, request):
        disponiveis = [
            {"slug": slug, **dados}
            for slug, dados in CATALOGO.items()
            if request.user.perfil in dados["perfis"]
        ]
        return render(request, "relatorios/indice.html", {"relatorios": disponiveis})


class RelatorioView(LoginRequiredMixin, View):
    def get(self, request, slug):
        definicao = CATALOGO.get(slug)
        if definicao is None:
            raise Http404("Relatório não encontrado.")

        if request.user.perfil not in definicao["perfis"]:
            raise PermissionDenied("Seu perfil não tem acesso a este relatório.")

        formulario = FiltroForm(
            request.GET or None,
            pede_periodo=definicao.get("pede_periodo", True),
            pede_doador=definicao.get("pede_doador", False),
        )
        dados = formulario.cleaned_data if formulario.is_valid() else {}

        relatorio = definicao["funcao"](
            dados.get("inicio"),
            dados.get("fim"),
            doador_id=dados["doador"].pk if dados.get("doador") else None,
        )

        formato = request.GET.get("formato", "tela")
        if formato in ("csv", "pdf"):
            return renderizar(relatorio, formato, request)

        contexto = montar_contexto(relatorio, request)
        contexto["form"] = formulario
        contexto["slug"] = slug
        return render(request, "relatorios/base_relatorio.html", contexto)
```

`relatorios/urls.py`:
```python
from django.urls import path

from relatorios import views

app_name = "relatorios"

urlpatterns = [
    path("relatorios/", views.IndiceView.as_view(), name="indice"),
    path("relatorios/<slug:slug>/", views.RelatorioView.as_view(), name="ver"),
]
```

Em `comviver/urls.py`:
```python
    path("", include("relatorios.urls")),
```

- [ ] **Step 5: Acrescentar os filtros ao layout de tela**

Em `templates/relatorios/base_relatorio.html`, substituir `{% block filtros %}{% endblock %}`:
```html
  {% if form.fields %}
    <form method="get" class="row g-2 align-items-end mb-3">
      {% for campo in form %}
        <div class="col-auto">
          <label for="{{ campo.id_for_label }}" class="form-label small">{{ campo.label }}</label>
          {{ campo }}
          {% for erro in campo.errors %}
            <div class="form-text text-danger">{{ erro }}</div>
          {% endfor %}
        </div>
      {% endfor %}
      <div class="col-auto">
        <button class="btn btn-outline-secondary">Aplicar</button>
      </div>
    </form>
  {% endif %}
```

- [ ] **Step 6: Escrever o índice**

`templates/relatorios/indice.html`:
```html
{% extends "base.html" %}
{% block titulo %}Relatórios{% endblock %}
{% block cabecalho %}Relatórios{% endblock %}

{% block conteudo %}
  <div class="row g-3">
    {% for relatorio in relatorios %}
      <div class="col-12 col-md-6 col-xl-4">
        <a href="{% url 'relatorios:ver' relatorio.slug %}"
           class="card h-100 text-decoration-none text-dark">
          <div class="card-body">
            <h2 class="h6 mb-1">{{ relatorio.rotulo }}</h2>
            <p class="text-muted small mb-0">{{ relatorio.descricao }}</p>
          </div>
        </a>
      </div>
    {% endfor %}
  </div>
{% endblock %}
```

Em `core/context_processors.py`:
```python
    itens.append(
        {"rotulo": "Relatórios", "url": reverse("relatorios:indice"), "icone": "file-earmark-text"}
    )
```

- [ ] **Step 7: Rodar os testes**

```bash
pytest relatorios/tests/ -v
```
Esperado: todos passando.

- [ ] **Step 8: Commit**

```bash
git add relatorios templates/relatorios core comviver/urls.py
git commit -m "feat(relatorios): adiciona os oito relatorios com filtro por perfil"
```

---

## Task 4: Busca global

**Files:**
- Create: `core/search.py`
- Modify: `core/views.py`, `core/urls.py`, `templates/base.html`
- Create: `templates/core/busca.html`
- Create: `core/tests/test_busca.py`

**Interfaces:**
- Consumes: models de `acolhidos`, `doacoes`, `voluntarios`
- Produces: `core.search.buscar(termo: str, usuario) -> list[dict]` — cada grupo com `modulo`, `rotulo`, `itens`; rota `core:busca`

- [ ] **Step 1: Escrever os testes que falham**

`core/tests/test_busca.py`:
```python
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def dados():
    from acolhidos.factories import AcolhidoFactory
    from doacoes.factories import DoadorFactory
    from voluntarios.factories import VoluntarioFactory

    return {
        "acolhido": AcolhidoFactory(nome="Mariana Costa"),
        "doador": DoadorFactory(nome="Mariana Alimentos"),
        "voluntario": VoluntarioFactory(nome="Mariana Prado"),
    }


class TestBusca:
    def test_encontra_nos_tres_modulos(self, client, usuario_admin, dados):
        client.force_login(usuario_admin)
        conteudo = client.get(reverse("core:busca") + "?q=mariana").content.decode()
        assert "Mariana Costa" in conteudo
        assert "Mariana Alimentos" in conteudo
        assert "Mariana Prado" in conteudo

    def test_busca_curta_nao_consulta(self, client, usuario_admin, dados):
        client.force_login(usuario_admin)
        resposta = client.get(reverse("core:busca") + "?q=ma")
        assert resposta.context["grupos"] == []

    def test_sem_resultado_informa(self, client, usuario_admin):
        client.force_login(usuario_admin)
        conteudo = client.get(reverse("core:busca") + "?q=inexistente").content.decode()
        assert "Nenhum resultado" in conteudo

    def test_anonimo_vai_para_o_login(self, client):
        resposta = client.get(reverse("core:busca") + "?q=mariana")
        assert resposta.status_code == 302


class TestBuscaRespeitaOPerfil:
    def test_operacional_encontra_o_acolhido_pelo_nome(self, client, usuario_operacional, dados):
        """Operacional precisa localizar a crianca; o que ele nao pode e ver
        a ficha."""
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("core:busca") + "?q=mariana").content.decode()
        assert "Mariana Costa" in conteudo

    def test_resultado_de_acolhido_nao_traz_dado_sigiloso(
        self, client, usuario_operacional, dados
    ):
        from acolhidos.factories import FichaAcolhimentoFactory

        FichaAcolhimentoFactory(
            acolhido=dados["acolhido"], motivo="Negligência familiar grave"
        )
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("core:busca") + "?q=mariana").content.decode()
        assert "Negligência familiar grave" not in conteudo

    def test_tecnico_nao_ve_grupo_de_doadores(self, client, usuario_tecnico, dados):
        """Tecnico tem leitura em doacoes, mas a busca do dia a dia dele nao
        precisa poluir com doador."""
        client.force_login(usuario_tecnico)
        resposta = client.get(reverse("core:busca") + "?q=mariana")
        modulos = [grupo["modulo"] for grupo in resposta.context["grupos"]]
        assert "doadores" not in modulos
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_busca.py -v
```
Esperado: `NoReverseMatch` para `core:busca`.

- [ ] **Step 3: Escrever `core/search.py`**

```python
from django.urls import reverse

TAMANHO_MINIMO = 3
LIMITE_POR_GRUPO = 10


def buscar(termo: str, usuario) -> list[dict]:
    """Busca em acolhidos, doadores e voluntarios, respeitando o perfil.

    O resultado de acolhido traz apenas nome, idade e situacao, para qualquer
    perfil: resultado de busca e conteudo que aparece na tela de quem passa
    pela sala.
    """
    termo = (termo or "").strip()
    if len(termo) < TAMANHO_MINIMO:
        return []

    grupos = []

    grupos.append(_acolhidos(termo))

    if usuario.perfil in {"ADMIN", "OPERACIONAL"}:
        grupos.append(_doadores(termo))

    grupos.append(_voluntarios(termo))

    return [grupo for grupo in grupos if grupo["itens"]]


def _acolhidos(termo: str) -> dict:
    from django.db.models import Q

    from acolhidos.models import Acolhido

    consulta = Acolhido.objects.filter(
        Q(nome__icontains=termo) | Q(nome_social__icontains=termo)
    )[:LIMITE_POR_GRUPO]

    return {
        "modulo": "acolhidos",
        "rotulo": "Acolhidos",
        "icone": "people-fill",
        "itens": [
            {
                "titulo": acolhido.nome_exibicao,
                "detalhe": f"{acolhido.idade} anos · {acolhido.get_status_display()}",
                "url": reverse("acolhidos:detalhe", args=[acolhido.pk]),
            }
            for acolhido in consulta
        ],
    }


def _doadores(termo: str) -> dict:
    from django.db.models import Q

    from doacoes.models import Doador

    consulta = Doador.objects.filter(
        Q(nome__icontains=termo) | Q(cpf_cnpj__icontains=termo) | Q(email__icontains=termo)
    )[:LIMITE_POR_GRUPO]

    return {
        "modulo": "doadores",
        "rotulo": "Doadores",
        "icone": "heart",
        "itens": [
            {
                "titulo": doador.nome,
                "detalhe": doador.documento_formatado,
                "url": reverse("doacoes:doador_detalhe", args=[doador.pk]),
            }
            for doador in consulta
        ],
    }


def _voluntarios(termo: str) -> dict:
    from django.db.models import Q

    from voluntarios.models import Voluntario

    consulta = Voluntario.objects.filter(
        Q(nome__icontains=termo) | Q(email__icontains=termo) | Q(telefone__icontains=termo)
    )[:LIMITE_POR_GRUPO]

    return {
        "modulo": "voluntarios",
        "rotulo": "Voluntários",
        "icone": "person-badge",
        "itens": [
            {
                "titulo": voluntario.nome,
                "detalhe": voluntario.resumo_disponibilidade,
                "url": reverse("voluntarios:detalhe", args=[voluntario.pk]),
            }
            for voluntario in consulta
        ],
    }
```

- [ ] **Step 4: View, rota e template**

Em `core/views.py`:
```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from core.search import buscar


class BuscaGlobalView(LoginRequiredMixin, TemplateView):
    template_name = "core/busca.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        termo = self.request.GET.get("q", "")
        contexto["termo"] = termo
        contexto["grupos"] = buscar(termo, self.request.user)
        return contexto
```

Em `core/urls.py`:
```python
    path("busca/", views.BuscaGlobalView.as_view(), name="busca"),
```

Em `templates/base.html`, dentro da `navbar`, antes do nome do usuário:
```html
      <form method="get" action="{% url 'core:busca' %}" class="d-none d-md-block m-0">
        <input type="search" name="q" class="form-control form-control-sm"
               style="width: 18rem;" placeholder="Buscar em todo o sistema"
               value="{{ request.GET.q|default:'' }}">
      </form>
```

`templates/core/busca.html`:
```html
{% extends "base.html" %}
{% block titulo %}Busca{% endblock %}
{% block cabecalho %}Resultados da busca{% endblock %}

{% block conteudo %}
  <form method="get" class="mb-4">
    <div class="input-group" style="max-width: 32rem;">
      <input type="search" name="q" value="{{ termo }}" class="form-control"
             placeholder="Nome, documento, telefone ou e-mail" autofocus>
      <button class="btn btn-primary">Buscar</button>
    </div>
  </form>

  {% for grupo in grupos %}
    <h2 class="h6 mt-4 mb-2">
      <i class="bi bi-{{ grupo.icone }}"></i> {{ grupo.rotulo }}
    </h2>
    <div class="list-group mb-3">
      {% for item in grupo.itens %}
        <a href="{{ item.url }}" class="list-group-item list-group-item-action">
          <div class="fw-semibold">{{ item.titulo }}</div>
          <div class="text-muted small">{{ item.detalhe }}</div>
        </a>
      {% endfor %}
    </div>
  {% empty %}
    {% if termo %}
      <p class="text-muted">Nenhum resultado para “{{ termo }}”.</p>
    {% else %}
      <p class="text-muted">Digite ao menos três caracteres para buscar.</p>
    {% endif %}
  {% endfor %}
{% endblock %}
```

- [ ] **Step 5: Rodar os testes**

```bash
pytest core/tests/test_busca.py -v
```
Esperado: 7 testes passando.

- [ ] **Step 6: Commit**

```bash
git add core templates/core templates/base.html
git commit -m "feat(core): adiciona busca global filtrada por perfil"
```

---

## Task 5: Backup, manuais e entrega

**Files:**
- Create: `core/management/__init__.py`, `core/management/commands/__init__.py`
- Create: `core/management/commands/backup_dados.py`
- Create: `core/tests/test_backup.py`
- Create: `docs/manual-usuario.md`, `docs/manual-admin.md`
- Modify: `README.md`

**Interfaces:**
- Produces: comando `python manage.py backup_dados`, com opções `--saida` e `--manter`

- [ ] **Step 1: Escrever os testes que falham**

`core/tests/test_backup.py`:
```python
import json

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


class TestBackup:
    def test_gera_arquivo_json(self, tmp_path):
        from acolhidos.factories import AcolhidoFactory

        AcolhidoFactory(nome="Ana Clara")
        call_command("backup_dados", saida=str(tmp_path), verbosity=0)
        arquivos = list(tmp_path.glob("comviver-*.json"))
        assert len(arquivos) == 1

    def test_arquivo_contem_os_dados(self, tmp_path):
        from acolhidos.factories import AcolhidoFactory

        AcolhidoFactory(nome="Ana Clara")
        call_command("backup_dados", saida=str(tmp_path), verbosity=0)
        arquivo = next(tmp_path.glob("comviver-*.json"))
        conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
        assert any(
            registro["model"] == "acolhidos.acolhido" for registro in conteudo
        )

    def test_nao_inclui_sessoes(self, tmp_path):
        """Sessao e dado efemero e carrega token de autenticacao: nao deve
        viajar em arquivo de backup."""
        call_command("backup_dados", saida=str(tmp_path), verbosity=0)
        arquivo = next(tmp_path.glob("comviver-*.json"))
        conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
        assert not any(
            registro["model"].startswith("sessions.") for registro in conteudo
        )

    def test_manter_remove_backups_antigos(self, tmp_path):
        for indice in range(5):
            (tmp_path / f"comviver-2026-01-0{indice + 1}-120000.json").write_text("[]")
        call_command("backup_dados", saida=str(tmp_path), manter=3, verbosity=0)
        assert len(list(tmp_path.glob("comviver-*.json"))) == 3

    def test_nao_apaga_arquivos_de_outro_padrao(self, tmp_path):
        (tmp_path / "importante.json").write_text("{}")
        for indice in range(5):
            (tmp_path / f"comviver-2026-01-0{indice + 1}-120000.json").write_text("[]")
        call_command("backup_dados", saida=str(tmp_path), manter=2, verbosity=0)
        assert (tmp_path / "importante.json").exists()
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest core/tests/test_backup.py -v
```
Esperado: `CommandError: Unknown command: 'backup_dados'`.

- [ ] **Step 3: Escrever o comando**

```bash
mkdir -p core/management/commands
touch core/management/__init__.py core/management/commands/__init__.py
```

`core/management/commands/backup_dados.py`:
```python
from datetime import datetime
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand

PADRAO = "comviver-*.json"

# Aplicativos cujos dados nao vao para o backup.
EXCLUIDOS = ["contenttypes", "auth.Permission", "sessions", "admin.LogEntry"]


class Command(BaseCommand):
    help = "Exporta todos os dados do sistema para um arquivo JSON datado."

    def add_arguments(self, parser):
        parser.add_argument(
            "--saida", default="backups",
            help="Diretório onde o arquivo será gravado (padrão: backups/).",
        )
        parser.add_argument(
            "--manter", type=int, default=30,
            help="Quantidade de backups a preservar (padrão: 30).",
        )

    def handle(self, *args, **opcoes):
        destino = Path(opcoes["saida"])
        destino.mkdir(parents=True, exist_ok=True)

        carimbo = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        arquivo = destino / f"comviver-{carimbo}.json"

        with arquivo.open("w", encoding="utf-8") as saida:
            call_command(
                "dumpdata",
                *[f"--exclude={app}" for app in EXCLUIDOS],
                indent=2,
                stdout=saida,
            )

        self.stdout.write(self.style.SUCCESS(f"Backup gravado em {arquivo}"))
        self._remover_antigos(destino, opcoes["manter"])

    def _remover_antigos(self, destino: Path, manter: int):
        """Remove apenas arquivos que seguem o padrao de nome deste comando.

        Apagar por extensao arriscaria levar junto arquivo que alguem guardou
        na mesma pasta.
        """
        arquivos = sorted(destino.glob(PADRAO), reverse=True)
        for antigo in arquivos[manter:]:
            antigo.unlink()
            self.stdout.write(f"Backup antigo removido: {antigo.name}")
```

Acrescentar a `.gitignore`:
```
/backups/
```

- [ ] **Step 4: Escrever o manual do usuário**

`docs/manual-usuario.md`:
```markdown
# ComViver — Manual do usuário

Sistema de gestão do Lar Padre José Gumercindo.

## Entrando no sistema

Acesse o endereço do sistema, informe seu usuário e senha. No primeiro acesso, o
sistema pede a troca da senha provisória — isso é obrigatório e acontece uma vez
só.

Se errar a senha três vezes, procure a coordenação. Ninguém além da coordenação
pode redefinir senhas.

## O que cada perfil vê

| Perfil | O que faz |
|---|---|
| **Administrador** | Tudo, incluindo usuários, campanhas e prestação de contas |
| **Técnico** | Ficha completa do acolhido, saúde, situação jurídica. Lê os demais módulos |
| **Operacional** | Doações, voluntários e escalas. Do acolhido, vê o essencial do dia a dia |

Se um item não aparece no seu menu, é porque seu perfil não tem acesso a ele.
Isso não é erro: a ficha da criança é sigilosa por lei.

## Painel

A tela inicial mostra os números do dia conforme o seu perfil: acolhidos ativos,
doações do mês, turnos sem voluntário nos próximos dias.

## Acolhidos

**Para cadastrar** (Técnico e Administrador): Acolhidos → Novo acolhimento. São
quatro etapas. O que você preenche fica salvo a cada etapa — se precisar sair no
meio, pode voltar depois.

**Para consultar**: Acolhidos → clique no card da criança. O filtro no topo
alterna entre acolhidos, desligados e todos.

**Para registrar desligamento**: abra a ficha → Registrar desligamento. Informe a
data, o destino e uma observação. A criança sai da lista de ativos, mas o
histórico continua salvo e consultável pelo filtro "Desligados".

## Doações

**Para registrar**: Doações → Nova doação.

- Deixe o doador em branco se a doação for anônima
- Ao escolher "Dinheiro", o valor passa a ser obrigatório
- Ao receber várias doações seguidas, use **Salvar e registrar outra**: a data e
  o doador continuam preenchidos

**Para emitir recibo**: na lista de doações, botão Recibo. Abre na tela e tem
link para baixar em PDF.

## Voluntários

**Para cadastrar**: Voluntários → Novo voluntário. Preencha a grade de
disponibilidade ao final — é ela que faz o sistema sugerir a pessoa certa na hora
de montar a escala.

## Escalas

**Para montar**:
1. Escalas → Nova escala. Informe título e período
2. Adicione os turnos com o botão **+ Turno**
3. Clique em **+ vaga** num turno. O painel à direita mostra quem declarou
   disponibilidade naquele dia e período
4. Clique no nome para alocar

Turnos com vaga em aberto ficam destacados em amarelo — é onde falta gente.

Se tentar escalar alguém que já está em outro turno no mesmo horário, o sistema
avisa e não deixa. Isso vale mesmo entre escalas diferentes.

**Para publicar**: botão Publicar. Pode publicar com turnos ainda descobertos; o
sistema apenas avisa.

**Para registrar presença**: na escala, botão Presença. Marque compareceu ou
faltou e salve.

## Relatórios

Relatórios → escolha o relatório. Cada um tem filtro de período e três formatos:

- **Tela** — para consultar
- **CSV** — abre no Excel
- **PDF** — para imprimir ou anexar à prestação de contas

Relatórios que contêm nome de criança saem com aviso de documento sigiloso e
identificação de quem emitiu. Não os envie por aplicativo de mensagem nem os
deixe impressos sobre a mesa.

## Busca

A caixa no topo busca ao mesmo tempo em acolhidos, doadores e voluntários. Digite
ao menos três letras.

## Dúvidas frequentes

**Excluí um registro por engano.** Nada é apagado de verdade. Procure a
coordenação: o Administrador consegue recuperar.

**Não consigo abrir uma página.** Se aparecer "Acesso negado", seu perfil não tem
permissão. Fale com a coordenação se precisar daquele acesso para o seu trabalho.

**Esqueci minha senha.** Só a coordenação redefine.
```

- [ ] **Step 5: Escrever o manual do administrador**

`docs/manual-admin.md`:
```markdown
# ComViver — Manual do administrador

Procedimentos técnicos e de coordenação.

## Criar um usuário

Usuários → Novo usuário. Escolha o perfil com cuidado:

- **Técnico** vê a ficha completa da criança, incluindo motivo do acolhimento e
  processo judicial
- **Operacional** não vê nada disso

Defina uma senha provisória e informe a pessoa. O sistema obriga a troca no
primeiro acesso.

## Desativar um usuário

Usuários → Desativar. O acesso é bloqueado, mas o registro permanece: o histórico
de quem cadastrou cada doação e cada ficha precisa continuar resolvível.

Desative assim que alguém deixar a instituição. Conta ativa de quem saiu é a
falha de segurança mais comum.

## Dados da instituição

Configuração → preencha nome, CNPJ, endereço e responsável legal. Esses dados
aparecem em recibos e relatórios de prestação de contas. Confirme com a diretoria
antes de preencher.

## Backup

```bash
python manage.py backup_dados
```

Gera `backups/comviver-AAAA-MM-DD-HHMMSS.json` e mantém os 30 mais recentes.

**Agendamento no Windows** (Agendador de Tarefas):
- Frequência: diária, fora do horário de uso
- Programa: caminho do `python.exe` do ambiente virtual
- Argumentos: `manage.py backup_dados`
- Iniciar em: pasta do projeto

**Importante:** o backup fica na mesma máquina. Copie a pasta `backups/` para um
serviço de nuvem ou pendrive periodicamente. Backup que mora no mesmo disco não
protege contra a falha mais provável, que é o disco parar.

**Para restaurar:**
```bash
python manage.py loaddata backups/comviver-AAAA-MM-DD-HHMMSS.json
```

## Atualizar o sistema

```bash
git pull
pip install -r requirements/prod.txt
```

PowerShell, para as migrations:
```powershell
$env:USE_DIRECT_DB = "1"
python manage.py migrate
$env:USE_DIRECT_DB = ""
python manage.py collectstatic --noinput
```

Faça backup antes de atualizar.

## Publicar em servidor

O sistema está preparado para qualquer serviço que rode Python com PostgreSQL.

1. Criar o banco e obter a URL de conexão
2. Definir as variáveis de ambiente: `SECRET_KEY`, `DEBUG=False`,
   `ALLOWED_HOSTS`, `DATABASE_URL`, `DIRECT_URL`
3. Usar `comviver.settings.prod` como `DJANGO_SETTINGS_MODULE`
4. Rodar migrations e `collectstatic`
5. Servir com `gunicorn comviver.wsgi`

A configuração de produção já ativa HTTPS obrigatório, cookies seguros e HSTS.

**Nunca** coloque `DEBUG=True` em produção: uma página de erro exibiria a senha
do banco.

## Proteção de dados

O sistema registra toda leitura e alteração de ficha de acolhido. Para consultar,
acesse `/admin/` com um superusuário → Acessos a fichas.

Esse registro atende ao art. 143 do ECA e responde a questionamento sobre quem
acessou informação de determinada criança.

Arquivos enviados (fotos, documentos) não ficam acessíveis por URL direta: o
sistema verifica a permissão a cada download.

## Se algo der errado

1. Verificar se o serviço está no ar
2. Ver os registros de erro do servidor
3. Confirmar que o banco responde: `python manage.py check --database default`
4. Restaurar o backup mais recente, se necessário

Ao pedir ajuda, informe: o que estava fazendo, o que apareceu na tela, e o
horário aproximado.
```

- [ ] **Step 6: Rodar a suíte completa e o lint**

```bash
pytest -v
ruff check .
ruff format --check .
```

- [ ] **Step 7: Verificação manual completa**

```powershell
$env:USE_DIRECT_DB = "1"
python manage.py migrate
$env:USE_DIRECT_DB = ""
python manage.py seed_demo --limpar
python manage.py runserver
```

**Como Administrador:**
1. Configuração → preencher CNPJ e endereço → salvar
2. Doações → emitir um recibo → confirmar que o CNPJ aparece
3. Relatórios → conferir que os oito aparecem no índice
4. Abrir "Prestação de contas" → confirmar que **nenhum nome de criança** aparece
5. Baixar o CSV e abrir no Excel → confirmar acentos e colunas separadas corretamente
6. Baixar o PDF de "Acolhidos ativos" → confirmar a tarja de documento sigiloso
7. Buscar um nome na caixa do topo → confirmar os três grupos de resultado

**Como Operacional:**
8. Relatórios → confirmar que "Acolhidos ativos", "Movimentação" e "Prestação de contas" **não** aparecem
9. Acessar `/relatorios/acolhidos-ativos/` pela barra de endereços → deve retornar 403
10. Buscar um nome → confirmar que o acolhido aparece, mas sem dado sigiloso

**Backup:**
11. `python manage.py backup_dados` → conferir o arquivo em `backups/`
12. Abrir o JSON e confirmar que não há registro de sessão

Os passos 4, 6 e 9 verificam o sigilo. São os que não podem falhar.

- [ ] **Step 8: Atualizar o README**

```markdown
## Documentação

- [Manual do usuário](docs/manual-usuario.md) — operação do dia a dia
- [Manual do administrador](docs/manual-admin.md) — usuários, backup, publicação
- [Design do sistema](docs/superpowers/specs/2026-09-22-comviver-design.md) — decisões técnicas

## Backup

```bash
python manage.py backup_dados
```

Gera um JSON datado em `backups/` e mantém os 30 mais recentes. Agende a
execução diária e copie a pasta para fora da máquina periodicamente.
```

- [ ] **Step 9: Commit**

```bash
git add core docs README.md .gitignore
git commit -m "feat(core): adiciona backup, busca global e manuais de entrega"
```

---

## Verificação de conclusão da Fase 5

- [ ] `pytest` — suíte inteira passando, sem testes ignorados
- [ ] `ruff check .` e `ruff format --check .` — sem apontamentos
- [ ] Roteiro manual da Task 5, com atenção aos passos 4, 6 e 9
- [ ] CSV abre corretamente no Excel em português
- [ ] PDF sigiloso exibe a tarja e o nome do emissor
- [ ] `git status --short` — `.env` e `backups/` não listados

---

## Verificação final do sistema

Antes de considerar o ComViver entregue:

**Cobertura da spec** — cada seção tem implementação verificável:

| Spec | Onde |
|---|---|
| §3 Arquitetura e configuração | Fase 1 |
| §4 Modelo de dados | Fases 1 a 4 |
| §5 Permissões, sigilo e auditoria | Fase 1 (base), Fase 2 (log e mídia), todas (matriz) |
| §6 Telas e fluxos | Fases 1 a 4 |
| §7 Relatórios | Fase 5 |
| §8 Qualidade e operação | Todas (testes), Fase 5 (backup e manuais) |
| §9 Fora de escopo | Nada implementado, conforme decidido |

**Sigilo** — o conjunto de testes que não pode falhar:
```bash
pytest acolhidos/tests/test_permissoes.py relatorios/tests/test_sigilo.py \
       core/tests/test_media_protegida.py core/tests/test_busca.py -v
```

**Entrega à instituição:**
- [ ] Sistema publicado e acessível
- [ ] Usuários reais criados, um por pessoa — nunca conta compartilhada
- [ ] Dados da instituição preenchidos em Configuração
- [ ] Backup agendado e testado com uma restauração real
- [ ] `seed_demo --limpar` executado e os dados fictícios removidos antes do uso real
- [ ] Manuais impressos ou disponíveis para a equipe
- [ ] Treinamento com pelo menos uma pessoa de cada perfil

O último item é o que decide se o sistema continua em uso depois que o projeto
de extensão terminar.
