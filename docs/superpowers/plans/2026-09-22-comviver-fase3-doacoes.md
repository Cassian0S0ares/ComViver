# ComViver — Fase 3: Doações — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o controle de doações — cadastro de doadores, registro rápido de doações em lote, campanhas e emissão de recibo — sustentando a prestação de contas da instituição.

**Architecture:** App `doacoes` consumindo as classes base criadas em `core` na Fase 2. Nenhuma view genérica é reescrita: a fase declara models, formulários, perfis e templates.

**Tech Stack:** Django 5.x, Bootstrap 5 (local), HTMX para a busca de doador, WeasyPrint para o recibo em PDF.

**Spec:** `docs/superpowers/specs/2026-09-22-comviver-design.md`

**Depende de:** Fases 1 e 2 concluídas.

## Global Constraints

- Python 3.12; Django 5.x (`Django>=5.1,<6.0`).
- PostgreSQL exclusivamente, inclusive em teste.
- `.env` nunca versionado.
- Interface, mensagens e validações em português do Brasil.
- Exclusão sempre lógica (`deleted_at`).
- Controle de acesso em três camadas: view, formulário e template.
- Valores monetários em `DecimalField(max_digits=10, decimal_places=2)`. Nunca `FloatField` — arredondamento binário em prestação de contas é erro que aparece na assembleia.
- `ruff` limpo antes de cada commit.
- Teste escrito antes da implementação, falhando primeiro pelo motivo certo.

## Recorte de acesso desta fase

Pela matriz da spec §5.1:

| Ação | Admin | Técnico | Operacional |
|---|---|---|---|
| Ver doações e doadores | escreve | lê | escreve |
| Registrar doação | sim | não | sim |
| Cadastrar e editar doador | sim | não | sim |
| Criar e encerrar campanha | sim | não | não |
| Emitir recibo | sim | não | sim |

O Técnico tem apenas leitura: a equipe técnica cuida do acolhido, não da
portaria. Manter a leitura permite responder a uma pergunta sobre doação sem
precisar interromper outra pessoa.

## O que as fases anteriores deixaram pronto

- `core.views.BaseListView`, `BaseCreateView`, `BaseUpdateView`
- `core.forms.FormularioPorPerfilMixin`
- `core.mixins.PerfilRequiredMixin`
- `core.models.SoftDeleteModel`, `Endereco`
- `core.context_processors.menu` e `core.views.PainelView._montar_cartoes`
- Padrão de template de lista e formulário em `templates/acolhidos/`

---

## Estrutura de arquivos ao fim da Fase 3

```
doacoes/
├── models.py          # Doador, Campanha, Doacao
├── forms.py           # DoadorForm, DoacaoForm, CampanhaForm
├── views.py           # CRUDs + busca HTMX + recibo
├── urls.py
├── admin.py
├── factories.py
├── services.py        # totalizacoes reaproveitadas pelo painel e pela Fase 5
├── migrations/
└── tests/
    ├── test_models.py
    ├── test_permissoes.py
    ├── test_registro.py
    ├── test_totais.py
    └── test_recibo.py

templates/doacoes/
├── doacao_list.html
├── doacao_form.html
├── doador_list.html
├── doador_detail.html
├── doador_form.html
├── campanha_list.html
├── campanha_form.html
├── recibo.html                    # usado na tela e no PDF
└── partials/
    └── _resultado_busca_doador.html   # fragmento HTMX
```

---

## Task 1: Models `Doador`, `Campanha` e `Doacao`

**Files:**
- Create: `doacoes/` (app completo), `doacoes/models.py`, `doacoes/factories.py`
- Create: `doacoes/tests/__init__.py`, `doacoes/tests/test_models.py`
- Modify: `comviver/settings/base.py` (`INSTALLED_APPS`)

**Interfaces:**
- Consumes: `core.models.SoftDeleteModel`, `core.models.Endereco`
- Produces:
  - `doacoes.models.TipoPessoa` — `PF`, `PJ`
  - `doacoes.models.TipoDoacao` — `DINHEIRO`, `ALIMENTO`, `VESTUARIO`, `MATERIAL`, `SERVICO`, `OUTRO`
  - `doacoes.models.Doador` — propriedades `documento_formatado: str`, `total_doado: Decimal`
  - `doacoes.models.Campanha` — propriedades `esta_ativa: bool`, `arrecadado: Decimal`, `percentual_da_meta: int`
  - `doacoes.models.Doacao` — propriedade `descricao_quantidade: str`; `clean()` exigindo valor para doação em dinheiro

- [ ] **Step 1: Escrever os testes que falham**

`doacoes/tests/test_models.py`:
```python
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from doacoes.factories import CampanhaFactory, DoacaoFactory, DoadorFactory
from doacoes.models import Doacao, TipoDoacao, TipoPessoa

pytestmark = pytest.mark.django_db


class TestDoador:
    def test_documento_formatado_de_pessoa_fisica(self):
        doador = DoadorFactory(tipo=TipoPessoa.PF, cpf_cnpj="12345678901")
        assert doador.documento_formatado == "123.456.789-01"

    def test_documento_formatado_de_pessoa_juridica(self):
        doador = DoadorFactory(tipo=TipoPessoa.PJ, cpf_cnpj="12345678000190")
        assert doador.documento_formatado == "12.345.678/0001-90"

    def test_documento_vazio_devolve_traco(self):
        assert DoadorFactory(cpf_cnpj="").documento_formatado == "—"

    def test_total_doado_soma_apenas_dinheiro(self):
        doador = DoadorFactory()
        DoacaoFactory(doador=doador, tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(doador=doador, tipo=TipoDoacao.DINHEIRO, valor=Decimal("50.50"))
        DoacaoFactory(doador=doador, tipo=TipoDoacao.ALIMENTO, valor=None, quantidade=20)
        assert doador.total_doado == Decimal("150.50")

    def test_total_doado_zero_sem_doacao_em_dinheiro(self):
        doador = DoadorFactory()
        DoacaoFactory(doador=doador, tipo=TipoDoacao.ALIMENTO, valor=None)
        assert doador.total_doado == Decimal("0")


class TestDoacao:
    def test_doacao_anonima_e_permitida(self):
        """Doacao anonima e frequente e nao pode travar o registro."""
        doacao = DoacaoFactory(doador=None, tipo=TipoDoacao.ALIMENTO)
        assert doacao.doador is None
        assert Doacao.objects.filter(pk=doacao.pk).exists()

    def test_dinheiro_sem_valor_e_recusado(self):
        doacao = DoacaoFactory.build(tipo=TipoDoacao.DINHEIRO, valor=None)
        with pytest.raises(ValidationError) as erro:
            doacao.full_clean()
        assert "valor" in erro.value.message_dict

    def test_dinheiro_com_valor_negativo_e_recusado(self):
        doacao = DoacaoFactory.build(tipo=TipoDoacao.DINHEIRO, valor=Decimal("-10.00"))
        with pytest.raises(ValidationError):
            doacao.full_clean()

    def test_data_futura_e_recusada(self):
        doacao = DoacaoFactory.build(
            data_recebimento=date.today() + timedelta(days=1), tipo=TipoDoacao.ALIMENTO
        )
        with pytest.raises(ValidationError) as erro:
            doacao.full_clean()
        assert "data_recebimento" in erro.value.message_dict

    def test_descricao_quantidade_de_item_contavel(self):
        doacao = DoacaoFactory(
            tipo=TipoDoacao.ALIMENTO, descricao="Arroz 5kg",
            quantidade=20, unidade="pacotes", valor=None,
        )
        assert doacao.descricao_quantidade == "20 pacotes"

    def test_descricao_quantidade_de_dinheiro(self):
        doacao = DoacaoFactory(
            tipo=TipoDoacao.DINHEIRO, valor=Decimal("250.00"), quantidade=None
        )
        assert doacao.descricao_quantidade == "R$ 250,00"

    def test_exclusao_e_logica(self):
        doacao = DoacaoFactory()
        pk = doacao.pk
        doacao.delete()
        assert not Doacao.objects.filter(pk=pk).exists()
        assert Doacao.todos.filter(pk=pk).exists()


class TestCampanha:
    def test_campanha_no_periodo_esta_ativa(self):
        campanha = CampanhaFactory(
            data_inicio=date.today() - timedelta(days=5),
            data_fim=date.today() + timedelta(days=5),
        )
        assert campanha.esta_ativa is True

    def test_campanha_encerrada_nao_esta_ativa(self):
        campanha = CampanhaFactory(
            data_inicio=date.today() - timedelta(days=30),
            data_fim=date.today() - timedelta(days=1),
        )
        assert campanha.esta_ativa is False

    def test_arrecadado_soma_as_doacoes_da_campanha(self):
        campanha = CampanhaFactory(meta_valor=Decimal("1000.00"))
        DoacaoFactory(campanha=campanha, tipo=TipoDoacao.DINHEIRO, valor=Decimal("300.00"))
        DoacaoFactory(campanha=campanha, tipo=TipoDoacao.DINHEIRO, valor=Decimal("200.00"))
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("999.00"))  # outra campanha
        assert campanha.arrecadado == Decimal("500.00")

    def test_percentual_da_meta(self):
        campanha = CampanhaFactory(meta_valor=Decimal("1000.00"))
        DoacaoFactory(campanha=campanha, tipo=TipoDoacao.DINHEIRO, valor=Decimal("250.00"))
        assert campanha.percentual_da_meta == 25

    def test_percentual_zero_quando_sem_meta(self):
        campanha = CampanhaFactory(meta_valor=None)
        assert campanha.percentual_da_meta == 0
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest doacoes/tests/test_models.py -v
```
Esperado: `ModuleNotFoundError: No module named 'doacoes'`.

- [ ] **Step 3: Criar o app**

```bash
python manage.py startapp doacoes
mkdir doacoes/tests && touch doacoes/tests/__init__.py
rm doacoes/tests.py
```

`doacoes/apps.py`:
```python
from django.apps import AppConfig


class DoacoesConfig(AppConfig):
    name = "doacoes"
    verbose_name = "Doações"
```

Em `comviver/settings/base.py`, `INSTALLED_APPS`, após `"acolhidos"`:
```python
    "doacoes",
```

- [ ] **Step 4: Escrever `doacoes/models.py`**

```python
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from simple_history.models import HistoricalRecords

from core.models import Endereco, SoftDeleteModel


class TipoPessoa(models.TextChoices):
    PF = "PF", "Pessoa física"
    PJ = "PJ", "Pessoa jurídica"


class TipoDoacao(models.TextChoices):
    DINHEIRO = "DINHEIRO", "Dinheiro"
    ALIMENTO = "ALIMENTO", "Alimento"
    VESTUARIO = "VESTUARIO", "Vestuário"
    MATERIAL = "MATERIAL", "Material"
    SERVICO = "SERVICO", "Serviço"
    OUTRO = "OUTRO", "Outro"


class Doador(SoftDeleteModel, Endereco):
    tipo = models.CharField(
        "tipo", max_length=2, choices=TipoPessoa.choices, default=TipoPessoa.PF
    )
    nome = models.CharField("nome ou razão social", max_length=150)
    cpf_cnpj = models.CharField("CPF ou CNPJ", max_length=14, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    recorrente = models.BooleanField(
        "doador recorrente", default=False,
        help_text="Marque se a pessoa ou empresa doa com regularidade.",
    )
    observacoes = models.TextField("observações", blank=True)

    criado_por = models.ForeignKey(
        "accounts.Usuario", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="doadores_cadastrados",
    )

    class Meta:
        verbose_name = "doador"
        verbose_name_plural = "doadores"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    @property
    def documento_formatado(self) -> str:
        numero = "".join(filter(str.isdigit, self.cpf_cnpj))
        if len(numero) == 11:
            return f"{numero[:3]}.{numero[3:6]}.{numero[6:9]}-{numero[9:]}"
        if len(numero) == 14:
            return f"{numero[:2]}.{numero[2:5]}.{numero[5:8]}/{numero[8:12]}-{numero[12:]}"
        return "—"

    @property
    def total_doado(self) -> Decimal:
        """Soma apenas doacoes em dinheiro: 'R$ 500' e '20 kg de arroz' nao
        somam no mesmo total."""
        total = self.doacoes.filter(tipo=TipoDoacao.DINHEIRO).aggregate(
            soma=Sum("valor")
        )["soma"]
        return total or Decimal("0")


class Campanha(SoftDeleteModel):
    nome = models.CharField("nome", max_length=120)
    descricao = models.TextField("descrição", blank=True)
    data_inicio = models.DateField("início")
    data_fim = models.DateField("término", null=True, blank=True)
    meta_valor = models.DecimalField(
        "meta em reais", max_digits=10, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "campanha"
        verbose_name_plural = "campanhas"
        ordering = ["-data_inicio"]

    def __str__(self) -> str:
        return self.nome

    @property
    def esta_ativa(self) -> bool:
        hoje = date.today()
        if self.data_inicio > hoje:
            return False
        return self.data_fim is None or self.data_fim >= hoje

    @property
    def arrecadado(self) -> Decimal:
        total = self.doacoes.filter(tipo=TipoDoacao.DINHEIRO).aggregate(
            soma=Sum("valor")
        )["soma"]
        return total or Decimal("0")

    @property
    def percentual_da_meta(self) -> int:
        if not self.meta_valor:
            return 0
        return int(self.arrecadado / self.meta_valor * 100)


class Doacao(SoftDeleteModel):
    """Uma doacao recebida.

    `valor` e separado de `quantidade` porque 'R$ 500' e '20 kg de arroz' nao
    cabem no mesmo campo, e o relatorio financeiro precisa somar apenas o
    primeiro.
    """

    doador = models.ForeignKey(
        Doador, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="doacoes", help_text="Deixe vazio para doação anônima.",
    )
    campanha = models.ForeignKey(
        Campanha, null=True, blank=True, on_delete=models.SET_NULL, related_name="doacoes"
    )
    tipo = models.CharField("tipo", max_length=10, choices=TipoDoacao.choices)
    descricao = models.CharField(
        "descrição", max_length=200, blank=True, help_text="Ex.: Arroz 5kg, cobertores"
    )
    quantidade = models.DecimalField(
        "quantidade", max_digits=10, decimal_places=2, null=True, blank=True
    )
    unidade = models.CharField(
        "unidade", max_length=30, blank=True, help_text="Ex.: pacotes, caixas, peças"
    )
    valor = models.DecimalField(
        "valor em reais", max_digits=10, decimal_places=2, null=True, blank=True
    )
    data_recebimento = models.DateField("data de recebimento", default=date.today)
    recebido_por = models.ForeignKey(
        "accounts.Usuario", null=True, on_delete=models.SET_NULL, related_name="doacoes_recebidas"
    )
    recibo_emitido = models.BooleanField("recibo emitido", default=False)
    observacoes = models.TextField("observações", blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "doação"
        verbose_name_plural = "doações"
        ordering = ["-data_recebimento", "-criado_em"]
        indexes = [models.Index(fields=["-data_recebimento"])]

    def __str__(self) -> str:
        quem = self.doador.nome if self.doador else "Anônimo"
        return f"{self.get_tipo_display()} — {quem} ({self.data_recebimento:%d/%m/%Y})"

    def clean(self):
        super().clean()
        erros = {}

        if self.tipo == TipoDoacao.DINHEIRO:
            if self.valor is None:
                erros["valor"] = "Informe o valor da doação em dinheiro."
            elif self.valor <= 0:
                erros["valor"] = "O valor precisa ser maior que zero."
        elif not self.descricao:
            erros["descricao"] = "Descreva o que foi doado."

        if self.data_recebimento and self.data_recebimento > date.today():
            erros["data_recebimento"] = "A data de recebimento não pode ser no futuro."

        if erros:
            raise ValidationError(erros)

    @property
    def descricao_quantidade(self) -> str:
        if self.tipo == TipoDoacao.DINHEIRO and self.valor is not None:
            return f"R$ {self.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if self.quantidade is not None:
            quantidade = self.quantidade.normalize()
            return f"{quantidade:f} {self.unidade}".strip()
        return self.descricao or "—"
```

- [ ] **Step 5: Escrever `doacoes/factories.py`**

```python
from datetime import date
from decimal import Decimal

import factory

from doacoes.models import Campanha, Doacao, Doador, TipoDoacao, TipoPessoa


class DoadorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Doador

    tipo = TipoPessoa.PF
    nome = factory.Faker("name", locale="pt_BR")
    cpf_cnpj = ""
    telefone = factory.Faker("cellphone_number", locale="pt_BR")
    cidade = "Itajubá"
    uf = "MG"


class CampanhaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Campanha

    nome = factory.Sequence(lambda n: f"Campanha {n}")
    data_inicio = factory.LazyFunction(date.today)
    meta_valor = Decimal("1000.00")


class DoacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Doacao

    doador = factory.SubFactory(DoadorFactory)
    tipo = TipoDoacao.DINHEIRO
    valor = Decimal("100.00")
    descricao = "Doação em dinheiro"
    data_recebimento = factory.LazyFunction(date.today)
```

- [ ] **Step 6: Gerar migration e rodar**

```bash
python manage.py makemigrations doacoes
python manage.py migrate
```

```bash
pytest doacoes/tests/test_models.py -v --create-db
```
Esperado: 17 testes passando.

- [ ] **Step 7: Commit**

```bash
git add doacoes comviver/settings/base.py
git commit -m "feat(doacoes): adiciona Doador, Campanha e Doacao"
```

---

## Task 2: Tela de registro rápido de doação

A tela mais usada do módulo. Doações chegam em lote, na portaria, com fila
esperando — a otimização é para volume, não para completude.

**Files:**
- Create: `doacoes/forms.py`, `doacoes/views.py`, `doacoes/urls.py`
- Create: `templates/doacoes/doacao_form.html`, `doacao_list.html`
- Create: `templates/doacoes/partials/_resultado_busca_doador.html`
- Create: `doacoes/tests/test_registro.py`, `doacoes/tests/test_permissoes.py`
- Modify: `comviver/urls.py`, `core/context_processors.py`
- Modify: `templates/base.html` (carregar HTMX)

**Interfaces:**
- Consumes: `core.views.BaseListView`, `BaseCreateView` (Fase 2)
- Produces: rotas `doacoes:lista`, `doacoes:nova`, `doacoes:editar`, `doacoes:buscar_doador`; `doacoes.forms.DoacaoForm`

- [ ] **Step 1: Escrever os testes que falham**

`doacoes/tests/test_permissoes.py`:
```python
import pytest
from django.urls import reverse

from doacoes.factories import DoacaoFactory, DoadorFactory

pytestmark = pytest.mark.django_db

ROTAS_ESCRITA = [
    ("doacoes:nova", None),
    ("doacoes:doador_novo", None),
]


class TestLeitura:
    @pytest.mark.parametrize(
        "fixture_usuario", ["usuario_admin", "usuario_tecnico", "usuario_operacional"]
    )
    def test_todos_os_perfis_veem_a_lista(self, client, request, fixture_usuario):
        client.force_login(request.getfixturevalue(fixture_usuario))
        assert client.get(reverse("doacoes:lista")).status_code == 200


class TestEscrita:
    @pytest.mark.parametrize("rota,_", ROTAS_ESCRITA)
    def test_admin_escreve(self, client, usuario_admin, rota, _):
        client.force_login(usuario_admin)
        assert client.get(reverse(rota)).status_code == 200

    @pytest.mark.parametrize("rota,_", ROTAS_ESCRITA)
    def test_operacional_escreve(self, client, usuario_operacional, rota, _):
        client.force_login(usuario_operacional)
        assert client.get(reverse(rota)).status_code == 200

    @pytest.mark.parametrize("rota,_", ROTAS_ESCRITA)
    def test_tecnico_recebe_403(self, client, usuario_tecnico, rota, _):
        """Equipe tecnica cuida do acolhido, nao da portaria. Le, nao escreve."""
        client.force_login(usuario_tecnico)
        assert client.get(reverse(rota)).status_code == 403


class TestCampanhas:
    def test_so_admin_cria_campanha(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        assert client.get(reverse("doacoes:campanha_nova")).status_code == 403

    def test_admin_cria_campanha(self, client, usuario_admin):
        client.force_login(usuario_admin)
        assert client.get(reverse("doacoes:campanha_nova")).status_code == 200
```

`doacoes/tests/test_registro.py`:
```python
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from doacoes.factories import CampanhaFactory, DoadorFactory
from doacoes.models import Doacao, TipoDoacao

pytestmark = pytest.mark.django_db


def _dados(**extra):
    base = {
        "doador": "",
        "campanha": "",
        "tipo": TipoDoacao.ALIMENTO,
        "descricao": "Arroz 5kg",
        "quantidade": "20",
        "unidade": "pacotes",
        "valor": "",
        "data_recebimento": date.today().isoformat(),
        "observacoes": "",
    }
    return base | extra


class TestRegistroDeDoacao:
    def test_registrar_doacao_em_especie(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.post(reverse("doacoes:nova"), _dados())
        assert resposta.status_code == 302
        doacao = Doacao.objects.get(descricao="Arroz 5kg")
        assert doacao.quantidade == Decimal("20")

    def test_registra_quem_recebeu(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:nova"), _dados())
        assert Doacao.objects.get(descricao="Arroz 5kg").recebido_por == usuario_operacional

    def test_doacao_anonima(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:nova"), _dados())
        assert Doacao.objects.get(descricao="Arroz 5kg").doador is None

    def test_doacao_com_doador(self, client, usuario_operacional):
        doador = DoadorFactory(nome="Padaria Central")
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:nova"), _dados(doador=str(doador.pk)))
        assert Doacao.objects.get(descricao="Arroz 5kg").doador == doador

    def test_doacao_vinculada_a_campanha(self, client, usuario_operacional):
        campanha = CampanhaFactory(nome="Natal Solidário")
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:nova"), _dados(campanha=str(campanha.pk)))
        assert Doacao.objects.get(descricao="Arroz 5kg").campanha == campanha

    def test_dinheiro_sem_valor_mostra_erro(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("doacoes:nova"),
            _dados(tipo=TipoDoacao.DINHEIRO, valor="", descricao=""),
        )
        assert resposta.status_code == 200
        assert "Informe o valor da doação em dinheiro." in resposta.content.decode()
        assert Doacao.objects.count() == 0

    def test_salvar_e_novo_volta_ao_formulario(self, client, usuario_operacional):
        """Doacao chega em lote: voltar a listagem a cada item trava a fila."""
        client.force_login(usuario_operacional)
        resposta = client.post(reverse("doacoes:nova"), _dados(salvar_e_novo="1"))
        assert resposta.status_code == 302
        assert resposta.url.startswith(reverse("doacoes:nova"))

    def test_salvar_e_novo_preserva_data_e_doador(self, client, usuario_operacional):
        doador = DoadorFactory(nome="Padaria Central")
        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("doacoes:nova"), _dados(doador=str(doador.pk), salvar_e_novo="1")
        )
        assert f"doador={doador.pk}" in resposta.url
        assert f"data={date.today().isoformat()}" in resposta.url


class TestBuscaDeDoador:
    def test_busca_devolve_fragmento_com_o_doador(self, client, usuario_operacional):
        DoadorFactory(nome="Padaria Central")
        DoadorFactory(nome="Mercado do Bairro")
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("doacoes:buscar_doador") + "?termo=padar")
        conteudo = resposta.content.decode()
        assert "Padaria Central" in conteudo
        assert "Mercado do Bairro" not in conteudo

    def test_busca_com_menos_de_tres_letras_nao_consulta(self, client, usuario_operacional):
        DoadorFactory(nome="Padaria Central")
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("doacoes:buscar_doador") + "?termo=pa")
        assert "Padaria Central" not in resposta.content.decode()

    def test_tecnico_nao_usa_a_busca(self, client, usuario_tecnico):
        client.force_login(usuario_tecnico)
        resposta = client.get(reverse("doacoes:buscar_doador") + "?termo=padar")
        assert resposta.status_code == 403
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest doacoes/tests/ -v
```
Esperado: `NoReverseMatch: 'doacoes' is not a registered namespace`.

- [ ] **Step 3: Escrever `doacoes/forms.py`**

```python
from django import forms

from doacoes.models import Campanha, Doacao, Doador


def _aplicar_classes(campos):
    for campo in campos.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.update({"class": "form-check-input"})
        elif isinstance(campo.widget, forms.Select):
            campo.widget.attrs.update({"class": "form-select"})
        else:
            campo.widget.attrs.update({"class": "form-control"})


class DoacaoForm(forms.ModelForm):
    class Meta:
        model = Doacao
        fields = [
            "doador", "campanha", "tipo", "descricao",
            "quantidade", "unidade", "valor", "data_recebimento", "observacoes",
        ]
        widgets = {
            "data_recebimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
            "tipo": forms.RadioSelect,
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields["doador"].required = False
        self.fields["doador"].empty_label = "Anônimo"
        self.fields["campanha"].required = False
        self.fields["campanha"].queryset = Campanha.objects.all()
        self.fields["campanha"].empty_label = "Nenhuma"
        _aplicar_classes(self.fields)
        self.fields["tipo"].widget.attrs.pop("class", None)

    def clean(self):
        dados = super().clean()
        # Delega ao clean() do model: a regra vale igualmente no admin e em
        # qualquer importacao futura.
        self.instance.full_clean(exclude=[f for f in self.fields if f not in dados])
        return dados


class DoadorForm(forms.ModelForm):
    class Meta:
        model = Doador
        fields = [
            "tipo", "nome", "cpf_cnpj", "telefone", "email", "recorrente",
            "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf",
            "observacoes",
        ]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        _aplicar_classes(self.fields)

    def clean_cpf_cnpj(self):
        numero = "".join(filter(str.isdigit, self.cleaned_data.get("cpf_cnpj", "")))
        tipo = self.data.get("tipo")
        if numero and tipo == "PF" and len(numero) != 11:
            raise forms.ValidationError("CPF precisa ter 11 dígitos.")
        if numero and tipo == "PJ" and len(numero) != 14:
            raise forms.ValidationError("CNPJ precisa ter 14 dígitos.")
        return numero


class CampanhaForm(forms.ModelForm):
    class Meta:
        model = Campanha
        fields = ["nome", "descricao", "data_inicio", "data_fim", "meta_valor"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_fim": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        _aplicar_classes(self.fields)

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "O término não pode ser anterior ao início.")
        return dados
```

- [ ] **Step 4: Escrever `doacoes/views.py`**

```python
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView

from accounts.models import Perfil
from core.mixins import PerfilRequiredMixin
from core.views import BaseCreateView, BaseListView, BaseUpdateView
from doacoes.forms import CampanhaForm, DoacaoForm, DoadorForm
from doacoes.models import Campanha, Doacao, Doador

TODOS_OS_PERFIS = [Perfil.ADMIN, Perfil.TECNICO, Perfil.OPERACIONAL]
QUEM_REGISTRA = [Perfil.ADMIN, Perfil.OPERACIONAL]


class DoacaoListView(BaseListView):
    model = Doacao
    template_name = "doacoes/doacao_list.html"
    context_object_name = "doacoes"
    campos_busca = ["descricao", "doador__nome"]
    perfis_permitidos = TODOS_OS_PERFIS

    def get_queryset(self):
        qs = super().get_queryset().select_related("doador", "campanha", "recebido_por")
        tipo = self.request.GET.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)
        return qs

    def get_context_data(self, **kwargs):
        from doacoes.services import totais_por_tipo

        contexto = super().get_context_data(**kwargs)
        contexto["tipo_filtrado"] = self.request.GET.get("tipo", "")
        contexto["totais"] = totais_por_tipo(self.get_queryset())
        return contexto


class DoacaoCreateView(BaseCreateView):
    """Registro rapido. Otimizado para volume: doacao chega em lote, na
    portaria, com fila esperando."""

    model = Doacao
    form_class = DoacaoForm
    template_name = "doacoes/doacao_form.html"
    mensagem_sucesso = "Doação registrada."
    perfis_permitidos = QUEM_REGISTRA

    def get_initial(self):
        inicial = super().get_initial()
        if doador := self.request.GET.get("doador"):
            inicial["doador"] = doador
        if data := self.request.GET.get("data"):
            inicial["data_recebimento"] = data
        return inicial

    def form_valid(self, form):
        form.instance.recebido_por = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        if "salvar_e_novo" in self.request.POST:
            parametros = f"?data={self.object.data_recebimento.isoformat()}"
            if self.object.doador_id:
                parametros += f"&doador={self.object.doador_id}"
            return reverse("doacoes:nova") + parametros
        return reverse("doacoes:lista")


class DoacaoUpdateView(BaseUpdateView):
    model = Doacao
    form_class = DoacaoForm
    template_name = "doacoes/doacao_form.html"
    mensagem_sucesso = "Doação atualizada."
    success_url = reverse_lazy("doacoes:lista")
    perfis_permitidos = QUEM_REGISTRA


class BuscarDoadorView(PerfilRequiredMixin, ListView):
    """Fragmento HTMX: sugere doadores a partir de tres caracteres."""

    model = Doador
    template_name = "doacoes/partials/_resultado_busca_doador.html"
    context_object_name = "doadores"
    perfis_permitidos = QUEM_REGISTRA

    def get_queryset(self):
        termo = self.request.GET.get("termo", "").strip()
        if len(termo) < 3:
            return Doador.objects.none()
        return Doador.objects.filter(nome__icontains=termo)[:8]


class DoadorListView(BaseListView):
    model = Doador
    template_name = "doacoes/doador_list.html"
    context_object_name = "doadores"
    campos_busca = ["nome", "cpf_cnpj", "email"]
    perfis_permitidos = TODOS_OS_PERFIS


class DoadorDetailView(PerfilRequiredMixin, DetailView):
    model = Doador
    template_name = "doacoes/doador_detail.html"
    context_object_name = "doador"
    perfis_permitidos = TODOS_OS_PERFIS

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["doacoes"] = self.object.doacoes.select_related("campanha")
        return contexto


class DoadorCreateView(BaseCreateView):
    model = Doador
    form_class = DoadorForm
    template_name = "doacoes/doador_form.html"
    mensagem_sucesso = "Doador cadastrado."
    perfis_permitidos = QUEM_REGISTRA

    def get_success_url(self):
        return reverse("doacoes:doador_detalhe", args=[self.object.pk])


class DoadorUpdateView(BaseUpdateView):
    model = Doador
    form_class = DoadorForm
    template_name = "doacoes/doador_form.html"
    mensagem_sucesso = "Dados do doador atualizados."
    perfis_permitidos = QUEM_REGISTRA

    def get_success_url(self):
        return reverse("doacoes:doador_detalhe", args=[self.object.pk])


class CampanhaListView(BaseListView):
    model = Campanha
    template_name = "doacoes/campanha_list.html"
    context_object_name = "campanhas"
    campos_busca = ["nome"]
    perfis_permitidos = TODOS_OS_PERFIS


class CampanhaCreateView(BaseCreateView):
    model = Campanha
    form_class = CampanhaForm
    template_name = "doacoes/campanha_form.html"
    mensagem_sucesso = "Campanha criada."
    success_url = reverse_lazy("doacoes:campanha_lista")
    perfis_permitidos = [Perfil.ADMIN]


class CampanhaUpdateView(BaseUpdateView):
    model = Campanha
    form_class = CampanhaForm
    template_name = "doacoes/campanha_form.html"
    mensagem_sucesso = "Campanha atualizada."
    success_url = reverse_lazy("doacoes:campanha_lista")
    perfis_permitidos = [Perfil.ADMIN]
```

- [ ] **Step 5: Escrever `doacoes/services.py`**

Isolado desde já porque a Fase 5 consome as mesmas funções nos relatórios.

```python
from decimal import Decimal

from django.db.models import Count, QuerySet, Sum

from doacoes.models import Doacao, TipoDoacao


def totais_por_tipo(consulta: QuerySet[Doacao] | None = None) -> list[dict]:
    """Agrupa doacoes por tipo, com contagem e soma monetaria.

    Reaproveitado pela listagem, pelo painel e pelos relatorios da Fase 5.
    """
    base = consulta if consulta is not None else Doacao.objects.all()
    linhas = (
        base.values("tipo")
        .annotate(quantidade=Count("id"), soma=Sum("valor"))
        .order_by("tipo")
    )
    rotulos = dict(TipoDoacao.choices)
    return [
        {
            "tipo": linha["tipo"],
            "rotulo": rotulos.get(linha["tipo"], linha["tipo"]),
            "quantidade": linha["quantidade"],
            "soma": linha["soma"] or Decimal("0"),
        }
        for linha in linhas
    ]


def total_arrecadado(consulta: QuerySet[Doacao] | None = None) -> Decimal:
    base = consulta if consulta is not None else Doacao.objects.all()
    total = base.filter(tipo=TipoDoacao.DINHEIRO).aggregate(soma=Sum("valor"))["soma"]
    return total or Decimal("0")


def doadores_recorrentes_inativos(dias: int = 60):
    """Doadores marcados como recorrentes sem doacao no periodo.

    Alimenta o cartao do painel do Admin: e a lista de quem vale a pena
    procurar antes que o vinculo esfrie.
    """
    from datetime import date, timedelta

    from doacoes.models import Doador

    corte = date.today() - timedelta(days=dias)
    return Doador.objects.filter(recorrente=True).exclude(
        doacoes__data_recebimento__gte=corte
    )
```

- [ ] **Step 6: Escrever `doacoes/urls.py` e ligar ao projeto**

```python
from django.urls import path

from doacoes import views

app_name = "doacoes"

urlpatterns = [
    path("doacoes/", views.DoacaoListView.as_view(), name="lista"),
    path("doacoes/nova/", views.DoacaoCreateView.as_view(), name="nova"),
    path("doacoes/<int:pk>/editar/", views.DoacaoUpdateView.as_view(), name="editar"),
    path("doacoes/buscar-doador/", views.BuscarDoadorView.as_view(), name="buscar_doador"),

    path("doadores/", views.DoadorListView.as_view(), name="doador_lista"),
    path("doadores/novo/", views.DoadorCreateView.as_view(), name="doador_novo"),
    path("doadores/<int:pk>/", views.DoadorDetailView.as_view(), name="doador_detalhe"),
    path("doadores/<int:pk>/editar/", views.DoadorUpdateView.as_view(), name="doador_editar"),

    path("campanhas/", views.CampanhaListView.as_view(), name="campanha_lista"),
    path("campanhas/nova/", views.CampanhaCreateView.as_view(), name="campanha_nova"),
    path("campanhas/<int:pk>/editar/", views.CampanhaUpdateView.as_view(), name="campanha_editar"),
]
```

Em `comviver/urls.py`, antes de `core.urls`:
```python
    path("", include("doacoes.urls")),
```

- [ ] **Step 7: Carregar o HTMX localmente**

```bash
curl -L -o static/vendor/htmx.min.js https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js
```

Em `templates/base.html`, junto ao script do Bootstrap:
```html
  <script src="{% static 'vendor/htmx.min.js' %}" defer></script>
```

Servido localmente pela mesma razão do Bootstrap: script de terceiro sem
verificação de integridade roda no navegador que exibe dado de criança.

- [ ] **Step 8: Escrever os templates**

`templates/doacoes/doacao_form.html`:
```html
{% extends "base.html" %}
{% block titulo %}{% if object %}Editar doação{% else %}Nova doação{% endif %}{% endblock %}
{% block cabecalho %}{% if object %}Editar doação{% else %}Nova doação{% endif %}{% endblock %}

{% block conteudo %}
  <form method="post" style="max-width: 42rem;">
    {% csrf_token %}

    {% if form.non_field_errors %}
      <div class="alert alert-danger py-2">
        {% for erro in form.non_field_errors %}{{ erro }}{% endfor %}
      </div>
    {% endif %}

    <div class="mb-3">
      <label class="form-label">Doador</label>
      <div class="input-group">
        {{ form.doador }}
        <a href="{% url 'doacoes:doador_novo' %}" class="btn btn-outline-secondary">
          <i class="bi bi-plus-lg"></i> Novo
        </a>
      </div>
      <input type="search" class="form-control mt-2" name="termo"
             placeholder="Buscar doador pelo nome (3 letras ou mais)"
             hx-get="{% url 'doacoes:buscar_doador' %}"
             hx-trigger="keyup changed delay:300ms"
             hx-target="#resultado-doador">
      <div id="resultado-doador" class="list-group mt-1"></div>
      <div class="form-text">Deixe vazio para doação anônima.</div>
    </div>

    <fieldset class="mb-3">
      <legend class="form-label fs-6">Tipo</legend>
      <div class="d-flex flex-wrap gap-3">
        {% for opcao in form.tipo %}
          <div class="form-check">
            {{ opcao.tag }}
            <label class="form-check-label" for="{{ opcao.id_for_label }}">
              {{ opcao.choice_label }}
            </label>
          </div>
        {% endfor %}
      </div>
      {% for erro in form.tipo.errors %}
        <div class="form-text text-danger">{{ erro }}</div>
      {% endfor %}
    </fieldset>

    {% for campo in form %}
      {% if campo.name != 'doador' and campo.name != 'tipo' %}
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

    <div class="d-flex gap-2">
      <button type="submit" class="btn btn-primary">Salvar</button>
      {% if not object %}
        <button type="submit" name="salvar_e_novo" value="1" class="btn btn-outline-primary">
          Salvar e registrar outra
        </button>
      {% endif %}
      <a href="{% url 'doacoes:lista' %}" class="btn btn-link">Cancelar</a>
    </div>
  </form>
{% endblock %}
```

`templates/doacoes/partials/_resultado_busca_doador.html`:
```html
{% for doador in doadores %}
  <button type="button" class="list-group-item list-group-item-action"
          onclick="document.getElementById('id_doador').value='{{ doador.pk }}';
                   document.getElementById('resultado-doador').innerHTML='';">
    {{ doador.nome }}
    {% if doador.documento_formatado != '—' %}
      <span class="text-muted small">— {{ doador.documento_formatado }}</span>
    {% endif %}
  </button>
{% endfor %}
```

`templates/doacoes/doacao_list.html`:
```html
{% extends "base.html" %}
{% block titulo %}Doações{% endblock %}
{% block cabecalho %}Doações{% endblock %}

{% block acoes %}
  {% if user.perfil == 'ADMIN' or user.perfil == 'OPERACIONAL' %}
    <a href="{% url 'doacoes:nova' %}" class="btn btn-primary">
      <i class="bi bi-plus-lg"></i> Nova doação
    </a>
  {% endif %}
{% endblock %}

{% block conteudo %}
  <div class="row g-2 mb-3">
    {% for total in totais %}
      <div class="col-6 col-md-2">
        <div class="card h-100">
          <div class="card-body py-2 px-3">
            <div class="text-muted small">{{ total.rotulo }}</div>
            <div class="fw-semibold">{{ total.quantidade }}</div>
            {% if total.soma %}
              <div class="text-muted small">R$ {{ total.soma|floatformat:2 }}</div>
            {% endif %}
          </div>
        </div>
      </div>
    {% endfor %}
  </div>

  <form method="get" class="row g-2 mb-3">
    <div class="col-12 col-md-5">
      <input type="search" name="q" value="{{ busca }}" class="form-control"
             placeholder="Buscar por item ou doador">
    </div>
    <div class="col-8 col-md-3">
      <select name="tipo" class="form-select">
        <option value="">Todos os tipos</option>
        {% for valor, rotulo in form_tipos %}
          <option value="{{ valor }}" {% if tipo_filtrado == valor %}selected{% endif %}>
            {{ rotulo }}
          </option>
        {% endfor %}
      </select>
    </div>
    <div class="col-4 col-md-2">
      <button class="btn btn-outline-secondary w-100">Filtrar</button>
    </div>
  </form>

  <div class="table-responsive">
    <table class="table table-hover align-middle">
      <thead>
        <tr>
          <th>Data</th><th>Tipo</th><th>Item</th><th>Quantidade</th>
          <th>Doador</th><th>Recebido por</th><th></th>
        </tr>
      </thead>
      <tbody>
        {% for doacao in doacoes %}
          <tr>
            <td>{{ doacao.data_recebimento|date:"d/m/Y" }}</td>
            <td>{{ doacao.get_tipo_display }}</td>
            <td>{{ doacao.descricao|default:"—" }}</td>
            <td>{{ doacao.descricao_quantidade }}</td>
            <td>
              {% if doacao.doador %}
                <a href="{% url 'doacoes:doador_detalhe' doacao.doador.pk %}">
                  {{ doacao.doador.nome }}
                </a>
              {% else %}
                <span class="text-muted">Anônimo</span>
              {% endif %}
            </td>
            <td class="text-muted small">{{ doacao.recebido_por|default:"—" }}</td>
            <td class="text-end">
              {% if user.perfil == 'ADMIN' or user.perfil == 'OPERACIONAL' %}
                <a href="{% url 'doacoes:recibo' doacao.pk %}"
                   class="btn btn-sm btn-outline-secondary">Recibo</a>
                <a href="{% url 'doacoes:editar' doacao.pk %}"
                   class="btn btn-sm btn-outline-secondary">Editar</a>
              {% endif %}
            </td>
          </tr>
        {% empty %}
          <tr><td colspan="7" class="text-muted">Nenhuma doação registrada.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% endblock %}
```

Acrescentar `form_tipos` ao contexto da listagem, em `DoacaoListView.get_context_data`:
```python
        contexto["form_tipos"] = TipoDoacao.choices
```
(e importar `TipoDoacao` no topo de `doacoes/views.py`).

`templates/doacoes/doador_list.html`, `doador_form.html`, `campanha_list.html` e
`campanha_form.html` seguem o esqueleto de lista e de formulário já usado em
`templates/acolhidos/`. Escrever cada um com o conteúdo abaixo, ajustando os
pontos marcados.

Esqueleto de formulário:
```html
{% extends "base.html" %}
{% block titulo %}TITULO{% endblock %}
{% block cabecalho %}TITULO{% endblock %}

{% block conteudo %}
  <form method="post" style="max-width: 40rem;">
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

| Arquivo | TITULO | LINK_CANCELAR |
|---|---|---|
| `doador_form.html` | Doador | `{% url 'doacoes:doador_lista' %}` |
| `campanha_form.html` | Campanha | `{% url 'doacoes:campanha_lista' %}` |

`templates/doacoes/doador_detail.html`:
```html
{% extends "base.html" %}
{% block titulo %}{{ doador.nome }}{% endblock %}
{% block cabecalho %}{{ doador.nome }}{% endblock %}

{% block acoes %}
  {% if user.perfil == 'ADMIN' or user.perfil == 'OPERACIONAL' %}
    <a href="{% url 'doacoes:doador_editar' doador.pk %}"
       class="btn btn-outline-secondary">Editar</a>
  {% endif %}
{% endblock %}

{% block conteudo %}
  <div class="row g-4">
    <div class="col-12 col-lg-4">
      <div class="card">
        <div class="card-body">
          <dl class="row mb-0">
            <dt class="col-5">Tipo</dt><dd class="col-7">{{ doador.get_tipo_display }}</dd>
            <dt class="col-5">Documento</dt><dd class="col-7">{{ doador.documento_formatado }}</dd>
            <dt class="col-5">Telefone</dt><dd class="col-7">{{ doador.telefone|default:"—" }}</dd>
            <dt class="col-5">E-mail</dt><dd class="col-7">{{ doador.email|default:"—" }}</dd>
            <dt class="col-5">Endereço</dt>
            <dd class="col-7">{{ doador.endereco_formatado|default:"—" }}</dd>
            <dt class="col-5">Total em dinheiro</dt>
            <dd class="col-7 fw-semibold">R$ {{ doador.total_doado|floatformat:2 }}</dd>
          </dl>
          {% if doador.recorrente %}
            <span class="badge text-bg-primary mt-2">Doador recorrente</span>
          {% endif %}
        </div>
      </div>
    </div>

    <div class="col-12 col-lg-8">
      <div class="card">
        <div class="card-header">Histórico de doações</div>
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <thead><tr><th>Data</th><th>Tipo</th><th>Item</th><th>Quantidade</th></tr></thead>
            <tbody>
              {% for doacao in doacoes %}
                <tr>
                  <td>{{ doacao.data_recebimento|date:"d/m/Y" }}</td>
                  <td>{{ doacao.get_tipo_display }}</td>
                  <td>{{ doacao.descricao|default:"—" }}</td>
                  <td>{{ doacao.descricao_quantidade }}</td>
                </tr>
              {% empty %}
                <tr><td colspan="4" class="text-muted">Nenhuma doação registrada.</td></tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
{% endblock %}
```

`templates/doacoes/campanha_list.html`:
```html
{% extends "base.html" %}
{% block titulo %}Campanhas{% endblock %}
{% block cabecalho %}Campanhas{% endblock %}

{% block acoes %}
  {% if user.perfil == 'ADMIN' %}
    <a href="{% url 'doacoes:campanha_nova' %}" class="btn btn-primary">Nova campanha</a>
  {% endif %}
{% endblock %}

{% block conteudo %}
  <div class="row g-3">
    {% for campanha in campanhas %}
      <div class="col-12 col-md-6">
        <div class="card h-100">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
              <h2 class="h6 mb-1">{{ campanha.nome }}</h2>
              {% if campanha.esta_ativa %}
                <span class="badge text-bg-success">Ativa</span>
              {% else %}
                <span class="badge text-bg-secondary">Encerrada</span>
              {% endif %}
            </div>
            <p class="text-muted small mb-2">
              {{ campanha.data_inicio|date:"d/m/Y" }}
              {% if campanha.data_fim %}a {{ campanha.data_fim|date:"d/m/Y" }}{% endif %}
            </p>
            {% if campanha.meta_valor %}
              <div class="progress mb-1" style="height: 6px;">
                <div class="progress-bar" style="width: {{ campanha.percentual_da_meta }}%"></div>
              </div>
              <div class="small text-muted">
                R$ {{ campanha.arrecadado|floatformat:2 }} de
                R$ {{ campanha.meta_valor|floatformat:2 }}
                ({{ campanha.percentual_da_meta }}%)
              </div>
            {% endif %}
            {% if user.perfil == 'ADMIN' %}
              <a href="{% url 'doacoes:campanha_editar' campanha.pk %}"
                 class="btn btn-sm btn-outline-secondary mt-2">Editar</a>
            {% endif %}
          </div>
        </div>
      </div>
    {% empty %}
      <div class="col-12"><p class="text-muted">Nenhuma campanha cadastrada.</p></div>
    {% endfor %}
  </div>
{% endblock %}
```

`templates/doacoes/doador_list.html`:
```html
{% extends "base.html" %}
{% block titulo %}Doadores{% endblock %}
{% block cabecalho %}Doadores{% endblock %}

{% block acoes %}
  {% if user.perfil == 'ADMIN' or user.perfil == 'OPERACIONAL' %}
    <a href="{% url 'doacoes:doador_novo' %}" class="btn btn-primary">Novo doador</a>
  {% endif %}
{% endblock %}

{% block conteudo %}
  <form method="get" class="mb-3">
    <div class="input-group" style="max-width: 26rem;">
      <input type="search" name="q" value="{{ busca }}" class="form-control"
             placeholder="Buscar por nome, documento ou e-mail">
      <button class="btn btn-outline-secondary">Buscar</button>
    </div>
  </form>

  <div class="table-responsive">
    <table class="table table-hover align-middle">
      <thead><tr><th>Nome</th><th>Tipo</th><th>Documento</th><th>Telefone</th><th>Total</th></tr></thead>
      <tbody>
        {% for doador in doadores %}
          <tr>
            <td>
              <a href="{% url 'doacoes:doador_detalhe' doador.pk %}">{{ doador.nome }}</a>
              {% if doador.recorrente %}
                <span class="badge text-bg-primary ms-1">Recorrente</span>
              {% endif %}
            </td>
            <td>{{ doador.get_tipo_display }}</td>
            <td>{{ doador.documento_formatado }}</td>
            <td>{{ doador.telefone|default:"—" }}</td>
            <td>R$ {{ doador.total_doado|floatformat:2 }}</td>
          </tr>
        {% empty %}
          <tr><td colspan="5" class="text-muted">Nenhum doador cadastrado.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% endblock %}
```

- [ ] **Step 9: Acrescentar ao menu e ao painel**

Em `core/context_processors.py`, após o item de acolhidos:
```python
    itens.append(
        {"rotulo": "Doações", "url": reverse("doacoes:lista"), "icone": "box-seam"}
    )
    itens.append(
        {"rotulo": "Doadores", "url": reverse("doacoes:doador_lista"), "icone": "heart"}
    )
    if request.user.e_admin:
        itens.append(
            {"rotulo": "Campanhas", "url": reverse("doacoes:campanha_lista"), "icone": "megaphone"}
        )
```

Em `core/views.py`, `_montar_cartoes`:
```python
        from datetime import date

        from doacoes.models import Doacao
        from doacoes.services import doadores_recorrentes_inativos, total_arrecadado

        hoje = date.today()
        doacoes_do_mes = Doacao.objects.filter(
            data_recebimento__year=hoje.year, data_recebimento__month=hoje.month
        )
        cartoes.append(
            {
                "titulo": "Doações no mês",
                "valor": doacoes_do_mes.count(),
                "descricao": "registradas neste mês",
                "icone": "box-seam",
            }
        )

        if self.request.user.e_admin:
            cartoes.append(
                {
                    "titulo": "Arrecadado no mês",
                    "valor": f"R$ {total_arrecadado(doacoes_do_mes):,.2f}",
                    "descricao": "em doações financeiras",
                    "icone": "cash-coin",
                }
            )
            cartoes.append(
                {
                    "titulo": "Recorrentes ausentes",
                    "valor": doadores_recorrentes_inativos().count(),
                    "descricao": "sem doar há 60 dias",
                    "icone": "person-dash",
                }
            )
```

- [ ] **Step 10: Rodar os testes**

```bash
pytest doacoes/tests/ -v
```
Esperado: todos passando, exceto os que dependem da rota `doacoes:recibo`,
criada na Task 3.

- [ ] **Step 11: Commit**

```bash
git add doacoes templates/doacoes core static/vendor comviver/urls.py templates/base.html
git commit -m "feat(doacoes): adiciona registro rapido, doadores e campanhas"
```

---

## Task 3: Recibo em PDF

**Files:**
- Modify: `doacoes/views.py`, `doacoes/urls.py`
- Create: `core/pdf.py`
- Create: `templates/doacoes/recibo.html`
- Create: `doacoes/tests/test_recibo.py`
- Modify: `requirements/base.txt`, `comviver/settings/base.py`

**Interfaces:**
- Consumes: `doacoes.models.Doacao` (Task 1)
- Produces:
  - `core.pdf.renderizar_pdf(template: str, contexto: dict, nome_arquivo: str) -> HttpResponse`
  - rota `doacoes:recibo`, com `?formato=pdf` para download

O renderizador em `core` é escrito aqui e reaproveitado pelos oito relatórios da
Fase 5.

- [ ] **Step 1: Escrever os testes que falham**

`doacoes/tests/test_recibo.py`:
```python
from decimal import Decimal

import pytest
from django.urls import reverse

from doacoes.factories import DoacaoFactory, DoadorFactory
from doacoes.models import TipoDoacao

pytestmark = pytest.mark.django_db


class TestRecibo:
    def test_tecnico_nao_emite_recibo(self, client, usuario_tecnico):
        doacao = DoacaoFactory()
        client.force_login(usuario_tecnico)
        assert client.get(reverse("doacoes:recibo", args=[doacao.pk])).status_code == 403

    def test_operacional_emite_recibo(self, client, usuario_operacional):
        doacao = DoacaoFactory()
        client.force_login(usuario_operacional)
        assert client.get(reverse("doacoes:recibo", args=[doacao.pk])).status_code == 200

    def test_recibo_mostra_o_doador_e_o_valor(self, client, usuario_operacional):
        doador = DoadorFactory(nome="Padaria Central")
        doacao = DoacaoFactory(
            doador=doador, tipo=TipoDoacao.DINHEIRO, valor=Decimal("250.00")
        )
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("doacoes:recibo", args=[doacao.pk])).content.decode()
        assert "Padaria Central" in conteudo
        assert "250,00" in conteudo

    def test_recibo_de_doacao_anonima_informa_anonimo(self, client, usuario_operacional):
        doacao = DoacaoFactory(doador=None)
        client.force_login(usuario_operacional)
        conteudo = client.get(reverse("doacoes:recibo", args=[doacao.pk])).content.decode()
        assert "Anônimo" in conteudo

    def test_abrir_o_recibo_nao_altera_estado(self, client, usuario_operacional):
        """GET não muda estado: prefetch do navegador ou uma <img src> embutida
        em site externo marcariam recibos sem ninguém pedir."""
        doacao = DoacaoFactory(recibo_emitido=False)
        client.force_login(usuario_operacional)
        client.get(reverse("doacoes:recibo", args=[doacao.pk]))
        doacao.refresh_from_db()
        assert doacao.recibo_emitido is False

    def test_post_marca_como_entregue(self, client, usuario_operacional):
        doacao = DoacaoFactory(recibo_emitido=False)
        client.force_login(usuario_operacional)
        client.post(reverse("doacoes:recibo", args=[doacao.pk]))
        doacao.refresh_from_db()
        assert doacao.recibo_emitido is True

    def test_formato_pdf_devolve_pdf(self, client, usuario_operacional):
        doacao = DoacaoFactory()
        client.force_login(usuario_operacional)
        resposta = client.get(
            reverse("doacoes:recibo", args=[doacao.pk]) + "?formato=pdf"
        )
        assert resposta["Content-Type"] == "application/pdf"
        assert resposta.content[:4] == b"%PDF"

    def test_pdf_tem_nome_de_arquivo_legivel(self, client, usuario_operacional):
        doacao = DoacaoFactory()
        client.force_login(usuario_operacional)
        resposta = client.get(
            reverse("doacoes:recibo", args=[doacao.pk]) + "?formato=pdf"
        )
        assert f"recibo-{doacao.pk}.pdf" in resposta["Content-Disposition"]
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest doacoes/tests/test_recibo.py -v
```
Esperado: `NoReverseMatch` para `doacoes:recibo`.

- [ ] **Step 3: Instalar o WeasyPrint**

Acrescentar a `requirements/base.txt`:
```
weasyprint>=62.0,<64.0
```

```bash
pip install -r requirements/dev.txt
```

No Windows, o WeasyPrint depende das bibliotecas GTK. Se a importação falhar com
`cannot load library 'gobject-2.0-0'`, instalar o GTK3 Runtime e reabrir o
terminal. Confirmar com:

```bash
python -c "import weasyprint; print(weasyprint.__version__)"
```

- [ ] **Step 4: Escrever `core/pdf.py`**

```python
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML, default_url_fetcher


def _buscador_restrito(url: str):
    """Permite que o PDF carregue apenas arquivos estaticos do proprio projeto.

    Por padrao o WeasyPrint busca qualquer URL que apareca no HTML, inclusive
    `file:///`. Como os templates renderizam texto vindo do banco, uma
    referencia forjada leria arquivo do servidor — o `.env`, por exemplo — e o
    embutiria no PDF entregue ao usuario.
    """
    if url.startswith("file://"):
        caminho = Path(url.removeprefix("file://").lstrip("/")).resolve()
        permitidos = [Path(settings.STATIC_ROOT).resolve()]
        permitidos += [Path(d).resolve() for d in settings.STATICFILES_DIRS]
        if not any(caminho.is_relative_to(raiz) for raiz in permitidos):
            raise ValueError(f"Acesso a arquivo não autorizado: {url}")
        return default_url_fetcher(url)

    raise ValueError(f"O PDF não carrega recursos externos: {url}")


def renderizar_pdf(template: str, contexto: dict, nome_arquivo: str, request=None):
    """Gera PDF a partir do mesmo template HTML usado na tela.

    O CSS de impressao vive no proprio template, com @media print. Nao existe
    um segundo layout a manter.
    """
    html = render_to_string(template, contexto, request=request)
    pdf = HTML(
        string=html,
        base_url=str(settings.BASE_DIR),
        url_fetcher=_buscador_restrito,
    ).write_pdf()

    resposta = HttpResponse(pdf, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome_arquivo}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta
```

- [ ] **Step 5: Escrever a view do recibo**

Em `doacoes/views.py`:
```python
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from core.pdf import renderizar_pdf


class ReciboView(PerfilRequiredMixin, DetailView):
    """Recibo individual da doacao, em tela ou PDF."""

    model = Doacao
    template_name = "doacoes/recibo.html"
    context_object_name = "doacao"
    perfis_permitidos = QUEM_REGISTRA

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["emitido_em"] = timezone.localtime()
        contexto["emitido_por"] = self.request.user
        contexto["instituicao"] = {
            "nome": "Lar Padre José Gumercindo",
            "cnpj": "",
            "endereco": "",
        }
        return contexto

    def get(self, request, *args, **kwargs):
        resposta = super().get(request, *args, **kwargs)

        # A marcacao de "recibo emitido" acontece no POST, nunca aqui: um GET
        # nao deve alterar estado. Do jeito contrario, o prefetch do navegador
        # ou uma <img src> embutida em site externo marcaria recibos sozinha.
        if request.GET.get("formato") == "pdf":
            return renderizar_pdf(
                self.template_name,
                resposta.context_data,
                f"recibo-{self.object.pk}.pdf",
                request=request,
            )
        return resposta

    def post(self, request, *args, **kwargs):
        """Marca o recibo como entregue ao doador."""
        self.object = self.get_object()
        if not self.object.recibo_emitido:
            self.object.recibo_emitido = True
            self.object.save(update_fields=["recibo_emitido"])
            messages.success(request, "Recibo marcado como entregue.")
        return redirect("doacoes:recibo", pk=self.object.pk)
```

Os dados da instituição ficam vazios por ora. Preenchê-los exige CNPJ e endereço
oficiais, que devem ser confirmados com a coordenação — inventar valor em
documento de prestação de contas seria pior que deixar em branco. A Fase 5 traz
o cadastro desses dados em configuração.

Em `doacoes/urls.py`:
```python
    path("doacoes/<int:pk>/recibo/", views.ReciboView.as_view(), name="recibo"),
```

- [ ] **Step 6: Escrever `templates/doacoes/recibo.html`**

```html
{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Recibo de doação nº {{ doacao.pk }}</title>
  <style>
    @page { size: A4; margin: 2.5cm; }
    body { font-family: Georgia, "Times New Roman", serif; color: #1a1a1a; line-height: 1.6; }
    .cabecalho { text-align: center; border-bottom: 2px solid #2a6f4e; padding-bottom: 1rem; }
    .cabecalho h1 { font-size: 1.3rem; margin: 0 0 .25rem; }
    .cabecalho p { margin: 0; font-size: .85rem; color: #555; }
    .titulo { text-align: center; margin: 2rem 0 1.5rem; font-size: 1.1rem;
              letter-spacing: .08em; text-transform: uppercase; }
    .numero { text-align: center; color: #555; font-size: .9rem; margin-bottom: 2rem; }
    dl { display: grid; grid-template-columns: 11rem 1fr; gap: .4rem 1rem; }
    dt { font-weight: bold; }
    dd { margin: 0; }
    .declaracao { margin: 2rem 0; text-align: justify; }
    .assinatura { margin-top: 4rem; text-align: center; }
    .assinatura .linha { border-top: 1px solid #1a1a1a; width: 18rem;
                         margin: 0 auto .4rem; }
    .rodape { margin-top: 3rem; font-size: .75rem; color: #777; text-align: center; }
    @media print { .nao-imprimir { display: none; } }
  </style>
</head>
<body>
  <div class="cabecalho">
    <h1>{{ instituicao.nome }}</h1>
    {% if instituicao.cnpj %}<p>CNPJ {{ instituicao.cnpj }}</p>{% endif %}
    {% if instituicao.endereco %}<p>{{ instituicao.endereco }}</p>{% endif %}
  </div>

  <p class="titulo">Recibo de doação</p>
  <p class="numero">Nº {{ doacao.pk }}</p>

  <dl>
    <dt>Doador</dt>
    <dd>{% if doacao.doador %}{{ doacao.doador.nome }}{% else %}Anônimo{% endif %}</dd>

    {% if doacao.doador and doacao.doador.documento_formatado != '—' %}
      <dt>CPF / CNPJ</dt><dd>{{ doacao.doador.documento_formatado }}</dd>
    {% endif %}

    <dt>Tipo de doação</dt><dd>{{ doacao.get_tipo_display }}</dd>

    {% if doacao.descricao %}
      <dt>Descrição</dt><dd>{{ doacao.descricao }}</dd>
    {% endif %}

    <dt>Quantidade</dt><dd>{{ doacao.descricao_quantidade }}</dd>
    <dt>Data de recebimento</dt><dd>{{ doacao.data_recebimento|date:"d/m/Y" }}</dd>

    {% if doacao.campanha %}
      <dt>Campanha</dt><dd>{{ doacao.campanha.nome }}</dd>
    {% endif %}
  </dl>

  <p class="declaracao">
    Declaramos, para os devidos fins, o recebimento da doação acima
    discriminada, destinada à manutenção das atividades assistenciais desta
    instituição. Agradecemos a contribuição.
  </p>

  <div class="assinatura">
    <div class="linha"></div>
    <div>{{ instituicao.nome }}</div>
  </div>

  <p class="rodape">
    Emitido em {{ emitido_em|date:"d/m/Y H:i" }} por {{ emitido_por.get_full_name }}
    · Documento gerado pelo sistema ComViver
  </p>

  <div class="nao-imprimir" style="text-align:center; margin-top:2rem;">
    <a href="?formato=pdf">Baixar em PDF</a>
    {% if not doacao.recibo_emitido %}
      <form method="post" style="display:inline; margin-left:1rem;">
        {% csrf_token %}
        <button type="submit">Marcar como entregue ao doador</button>
      </form>
    {% else %}
      <span style="margin-left:1rem; color:#555;">Já entregue ao doador.</span>
    {% endif %}
  </div>
</body>
</html>
```

- [ ] **Step 7: Rodar a suíte completa**

```bash
pytest -v
ruff check .
```

- [ ] **Step 8: Verificação manual**

```bash
python manage.py runserver
```

1. Entrar como **Operacional** → Doações → Nova doação
2. Escolher tipo Alimento; confirmar que o campo de valor não é obrigatório
3. Digitar três letras na busca de doador; confirmar que a sugestão aparece
4. Usar "Salvar e registrar outra"; confirmar que a data e o doador continuam preenchidos
5. Registrar uma doação em Dinheiro sem valor; confirmar a mensagem de erro
6. Emitir o recibo na tela e baixar o PDF
7. Entrar como **Técnico** → confirmar que a listagem abre, mas o botão "Nova doação" não aparece
8. Como Técnico, acessar `/doacoes/nova/` pela barra de endereços → deve retornar 403

- [ ] **Step 9: Commit**

```bash
git add doacoes core/pdf.py templates/doacoes requirements/base.txt
git commit -m "feat(doacoes): adiciona recibo em tela e em PDF"
```

---

## Task 4: Dados de demonstração e fechamento

**Files:**
- Modify: `acolhidos/management/commands/seed_demo.py`
- Create: `doacoes/admin.py`
- Create: `doacoes/tests/test_totais.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `doacoes.services` (Task 2)
- Produces: `seed_demo` populando também doações, doadores e campanhas

- [ ] **Step 1: Escrever os testes de totalização**

`doacoes/tests/test_totais.py`:
```python
from datetime import date, timedelta
from decimal import Decimal

import pytest

from doacoes.factories import DoacaoFactory, DoadorFactory
from doacoes.models import TipoDoacao
from doacoes.services import (
    doadores_recorrentes_inativos,
    total_arrecadado,
    totais_por_tipo,
)

pytestmark = pytest.mark.django_db


class TestTotaisPorTipo:
    def test_agrupa_e_conta(self):
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("50.00"))
        DoacaoFactory(tipo=TipoDoacao.ALIMENTO, valor=None, descricao="Arroz")
        resultado = {linha["tipo"]: linha for linha in totais_por_tipo()}
        assert resultado["DINHEIRO"]["quantidade"] == 2
        assert resultado["DINHEIRO"]["soma"] == Decimal("150.00")
        assert resultado["ALIMENTO"]["quantidade"] == 1
        assert resultado["ALIMENTO"]["soma"] == Decimal("0")

    def test_respeita_a_consulta_recebida(self):
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(
            tipo=TipoDoacao.DINHEIRO, valor=Decimal("50.00"),
            data_recebimento=date.today() - timedelta(days=365),
        )
        from doacoes.models import Doacao

        deste_ano = Doacao.objects.filter(data_recebimento__year=date.today().year)
        resultado = {linha["tipo"]: linha for linha in totais_por_tipo(deste_ano)}
        assert resultado["DINHEIRO"]["soma"] == Decimal("100.00")

    def test_ignora_doacao_excluida_logicamente(self):
        doacao = DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        doacao.delete()
        assert totais_por_tipo() == []


class TestTotalArrecadado:
    def test_soma_apenas_dinheiro(self):
        DoacaoFactory(tipo=TipoDoacao.DINHEIRO, valor=Decimal("100.00"))
        DoacaoFactory(tipo=TipoDoacao.ALIMENTO, valor=None, descricao="Arroz")
        assert total_arrecadado() == Decimal("100.00")

    def test_zero_sem_doacao(self):
        assert total_arrecadado() == Decimal("0")


class TestDoadoresRecorrentesInativos:
    def test_recorrente_sem_doacao_recente_aparece(self):
        doador = DoadorFactory(recorrente=True)
        DoacaoFactory(doador=doador, data_recebimento=date.today() - timedelta(days=90))
        assert doador in doadores_recorrentes_inativos()

    def test_recorrente_com_doacao_recente_nao_aparece(self):
        doador = DoadorFactory(recorrente=True)
        DoacaoFactory(doador=doador, data_recebimento=date.today() - timedelta(days=10))
        assert doador not in doadores_recorrentes_inativos()

    def test_doador_nao_recorrente_nunca_aparece(self):
        doador = DoadorFactory(recorrente=False)
        DoacaoFactory(doador=doador, data_recebimento=date.today() - timedelta(days=200))
        assert doador not in doadores_recorrentes_inativos()

    def test_recorrente_que_nunca_doou_aparece(self):
        doador = DoadorFactory(recorrente=True)
        assert doador in doadores_recorrentes_inativos()
```

- [ ] **Step 2: Rodar e confirmar a falha**

```bash
pytest doacoes/tests/test_totais.py -v
```

Se `test_ignora_doacao_excluida_logicamente` falhar devolvendo a linha com
contagem zero em vez de lista vazia, o manager padrão não está filtrando — é
exatamente o que o teste existe para pegar.

- [ ] **Step 3: Acrescentar doações ao `seed_demo`**

Em `acolhidos/management/commands/seed_demo.py`, ao fim de `handle`:

```python
        from datetime import timedelta
        from decimal import Decimal

        from doacoes.models import Campanha, Doacao, Doador, TipoDoacao, TipoPessoa

        if opcoes["limpar"]:
            Doacao.todos.all().delete()
            Doador.todos.all().delete()
            Campanha.todos.all().delete()

        campanha = Campanha.objects.create(
            nome="Campanha do Agasalho",
            descricao="Arrecadação de roupas de inverno.",
            data_inicio=date.today() - timedelta(days=30),
            data_fim=date.today() + timedelta(days=30),
            meta_valor=Decimal("5000.00"),
        )

        doadores = [
            Doador.objects.create(
                tipo=TipoPessoa.PJ, nome="Padaria Central",
                cpf_cnpj="12345678000190", telefone="3599999001",
                cidade="Itajubá", uf="MG", recorrente=True,
            ),
            Doador.objects.create(
                tipo=TipoPessoa.PF, nome="Joana Martins",
                cpf_cnpj="12345678901", telefone="3599999002",
                cidade="Itajubá", uf="MG", recorrente=True,
            ),
            Doador.objects.create(
                tipo=TipoPessoa.PJ, nome="Mercado do Bairro",
                cpf_cnpj="98765432000155", cidade="Itajubá", uf="MG",
            ),
        ]

        exemplos = [
            (TipoDoacao.DINHEIRO, "Doação mensal", None, "", Decimal("500.00"), 0),
            (TipoDoacao.DINHEIRO, "Doação avulsa", None, "", Decimal("150.00"), 1),
            (TipoDoacao.ALIMENTO, "Arroz 5kg", Decimal("20"), "pacotes", None, 0),
            (TipoDoacao.ALIMENTO, "Feijão 1kg", Decimal("30"), "pacotes", None, 2),
            (TipoDoacao.VESTUARIO, "Casacos infantis", Decimal("45"), "peças", None, 2),
            (TipoDoacao.MATERIAL, "Cadernos", Decimal("60"), "unidades", None, 1),
            (TipoDoacao.SERVICO, "Consulta odontológica", None, "", None, None),
        ]

        for indice, (tipo, descricao, quantidade, unidade, valor, doador_i) in enumerate(exemplos):
            Doacao.objects.create(
                doador=doadores[doador_i] if doador_i is not None else None,
                campanha=campanha if tipo == TipoDoacao.VESTUARIO else None,
                tipo=tipo,
                descricao=descricao,
                quantidade=quantidade,
                unidade=unidade,
                valor=valor,
                data_recebimento=date.today() - timedelta(days=indice * 6),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(doadores)} doadores, {len(exemplos)} doações e 1 campanha criados."
            )
        )
```

- [ ] **Step 4: Registrar no admin**

`doacoes/admin.py`:
```python
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from doacoes.models import Campanha, Doacao, Doador


@admin.register(Doacao)
class DoacaoAdmin(SimpleHistoryAdmin):
    list_display = ["data_recebimento", "tipo", "descricao", "doador", "valor"]
    list_filter = ["tipo", "recibo_emitido", "campanha"]
    search_fields = ["descricao", "doador__nome"]
    date_hierarchy = "data_recebimento"


@admin.register(Doador)
class DoadorAdmin(admin.ModelAdmin):
    list_display = ["nome", "tipo", "documento_formatado", "recorrente"]
    list_filter = ["tipo", "recorrente"]
    search_fields = ["nome", "cpf_cnpj"]


admin.site.register(Campanha)
```

- [ ] **Step 5: Rodar a suíte e o lint**

```bash
pytest -v
ruff check .
ruff format --check .
```

- [ ] **Step 6: Verificação manual**

```bash
python manage.py seed_demo --limpar
python manage.py runserver
```

1. Painel como **Admin** → confirmar os cartões de doações do mês, arrecadado e recorrentes ausentes
2. Doações → conferir os totais por tipo no topo
3. Campanhas → confirmar a barra de progresso da Campanha do Agasalho
4. Abrir um doador → conferir o histórico e o total em dinheiro

- [ ] **Step 7: Atualizar o README**

```markdown
### Módulo de doações

- **Doações** — registro rápido, otimizado para recebimento em lote
- **Doadores** — pessoa física ou jurídica, com histórico e total doado
- **Campanhas** — período, meta e acompanhamento da arrecadação
- **Recibo** — emitido em tela ou PDF, por doação

Doações em dinheiro e em espécie são contabilizadas separadamente: o total
financeiro soma apenas as primeiras.
```

- [ ] **Step 8: Commit**

```bash
git add doacoes acolhidos README.md
git commit -m "feat(doacoes): adiciona dados de demonstracao e registro no admin"
```

---

## Verificação de conclusão da Fase 3

- [ ] `pytest` — suíte inteira passando
- [ ] `ruff check .` — sem apontamentos
- [ ] Roteiro manual das Tasks 3 e 4
- [ ] PDF do recibo abre corretamente fora do navegador

**O que a Fase 5 encontra pronto:**
- `core.pdf.renderizar_pdf` — usado pelos oito relatórios
- `doacoes.services.totais_por_tipo`, `total_arrecadado`, `doadores_recorrentes_inativos`
- Padrão de template de documento para impressão (`recibo.html`)

**Pendências desta fase, com destino:**

| Item | Fase |
|---|---|
| Dados da instituição no recibo (CNPJ, endereço) | 5, via configuração — exigem confirmação da coordenação |
| Relatórios de doações por período e prestação de contas | 5 |
| Exportação CSV do histórico de doador | 5 |
| Controle de estoque com baixa automática | Fora de escopo (spec §9) |
