# ComViver — Documento de Design

**Data:** 2026-09-22
**Projeto:** Sistema de gestão administrativa do Lar Padre José Gumercindo
**Natureza:** Projeto de extensão universitária, com entrega para uso real na instituição
**Status:** Design aprovado

---

## 1. Contexto e objetivo

O Lar Padre José Gumercindo é uma instituição de acolhimento de crianças e
adolescentes. Seus processos administrativos hoje são conduzidos em papel e
planilhas, o que dificulta consulta, gera retrabalho e não oferece controle
sobre quem acessa informação sigilosa.

O ComViver centraliza esses processos em um sistema web único: cadastro de
acolhidos, controle de doações, gestão de voluntários, organização de escalas e
geração de relatórios para prestação de contas.

O critério de sucesso não é a entrega acadêmica. É a instituição continuar
usando o sistema depois que o projeto de extensão terminar. Toda decisão de
design abaixo serve a esse critério.

### 1.1 Restrições do domínio

Acolhimento infanto-juvenil impõe requisitos que não são opcionais:

- **Art. 143 do ECA** — é vedada a divulgação de ato judicial ou administrativo
  que permita identificar criança ou adolescente acolhido. Isso determina a
  arquitetura de permissões, não é um detalhe posterior.
- **Art. 14 da LGPD** — tratamento de dado de criança exige consentimento
  específico do responsável e observância do melhor interesse do menor.
- **Prestação de contas** — conselhos, CMDCA e mantenedores exigem relatórios
  periódicos, normalmente com dados agregados e sem identificação.

---

## 2. Abordagem escolhida

**Monolito Django com apps por domínio e telas próprias.**

Foram consideradas três alternativas:

| Abordagem | Decisão | Motivo |
|---|---|---|
| Monolito Django, apps por domínio, telas próprias | **Escolhida** | Melhor usabilidade para operador leigo; permite esconder campo sensível por perfil; menor custo de manutenção após a entrega |
| Django Admin customizado como backoffice | Recusada | Interface pensada para desenvolvedor. Fluxos multi-passo ficam ruins e permissão por campo vira remendo |
| DRF + SPA React | Recusada | Dobra a superfície de trabalho e torna a manutenção inviável para a instituição. Só compensaria com aplicativo móvel no plano |

O prazo não é restrição neste projeto, então a economia de tempo oferecida pelo
Django Admin não tem valor frente à perda de usabilidade.

---

## 3. Arquitetura

### 3.1 Estrutura

```
comviver/
├── comviver/              # settings (base/dev/prod), urls raiz, wsgi
├── core/                  # base compartilhada — não depende de nenhum app
│   ├── models.py          # TimeStampedModel, SoftDeleteModel, Endereco
│   ├── mixins.py          # PerfilRequiredMixin, AuditoriaMixin
│   ├── views.py           # painel, busca global
│   └── templates/base.html
├── accounts/              # Usuario custom, perfis, auditoria, login
├── acolhidos/             # beneficiários, responsáveis, ficha, saúde, jurídico
├── doacoes/               # doadores, doações, campanhas, recibos
├── voluntarios/           # voluntários, disponibilidade, funções
├── escalas/               # escalas, turnos, alocações, presença
├── relatorios/            # agregações e exportação
├── templates/             # templates globais
├── static/
└── requirements/          # base.txt, dev.txt, prod.txt
```

### 3.2 Grafo de dependência

```
core  ←  accounts  ←  acolhidos, doacoes, voluntarios
                              ↑            ↑
                           escalas ────────┘
                              ↑
                         relatorios  (lê todos; ninguém depende dele)
```

Regra: um app não importa model de app irmão sem que a dependência esteja
declarada neste grafo. `core` não depende de ninguém. `relatorios` é folha, o
que permite adicionar relatório novo sem risco de quebrar módulo existente.

### 3.3 Stack

- Django 5.x, Python 3.12
- PostgreSQL (Supabase em desenvolvimento; banco da hospedagem em produção)
- Bootstrap 5, HTMX para interações pontuais
- WhiteNoise (estáticos), Gunicorn (produção)
- `django-environ` (configuração por ambiente)
- `django-simple-history` (auditoria)
- WeasyPrint (PDF)
- pytest, pytest-django, factory_boy (testes)
- ruff, pre-commit (padronização)

### 3.4 Configuração e ambientes

Settings divididos em `base.py`, `dev.py` e `prod.py`. Todo valor sensível vem
de variável de ambiente, lida de um arquivo `.env` que **nunca é versionado**.
O repositório contém apenas `.env.example`, com os nomes das variáveis e
valores vazios.

O ambiente de desenvolvimento usa um projeto Supabase (região `sa-east-1`). A
produção usará o banco da hospedagem contratada. Como ambos são PostgreSQL, a
migração é uma troca de valor de variável, não uma refatoração.

**Conexão com Supabase — duas portas, dois papéis:**

| Uso | Variável | Porta | Observação |
|---|---|---|---|
| Aplicação em execução | `DATABASE_URL` | 6543 | Transaction pooler (PgBouncer) |
| Migrations | `DIRECT_URL` | 5432 | Conexão direta |

O transaction pooler exige dois ajustes no Django, sem os quais consultas
grandes falham:

```python
DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        "CONN_MAX_AGE": 0,                     # o pooler gerencia o pool
        "DISABLE_SERVER_SIDE_CURSORS": True,   # transaction mode não suporta cursor nomeado
        "OPTIONS": {"sslmode": "require"},     # Supabase recusa conexão sem SSL
    }
}
```

---

## 4. Modelo de dados

Bases abstratas em `core`, aplicadas a todos os models de domínio:

- `TimeStampedModel` — `criado_em`, `atualizado_em`, `criado_por`
- `SoftDeleteModel` — `deleted_at` e manager que filtra excluídos
- `Endereco` — `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`

Exclusão é sempre lógica. Prestação de contas e histórico de acolhimento não
podem ter lacuna, e usuário leigo aciona exclusão por engano.

### 4.1 accounts

```
Usuario (AbstractUser)   perfil [ADMIN|TECNICO|OPERACIONAL], telefone, ativo
LogAcessoFicha           usuario, acolhido, data_hora, acao [VIEW|EDIT]
```

O usuário customizado é criado no primeiro commit, antes de qualquer migration
de domínio. Trocar o model de usuário depois é custoso.

`LogAcessoFicha` registra **leitura**, não apenas escrita. Histórico de
alteração não revela quem apenas abriu e leu a ficha de uma criança, e em
instituição de acolhimento isso é informação necessária.

### 4.2 acolhidos

```
Acolhido            nome, nome_social, nascimento, sexo, foto, naturalidade,
                    cpf, rg, certidao_nascimento, cartao_sus,
                    status [ACOLHIDO|DESLIGADO], observacoes
Responsavel         nome, cpf, rg, telefone, email, +Endereco, observacoes
VinculoFamiliar     acolhido ─ responsavel, parentesco, e_guardiao,
                    autorizado_visita, autorizado_retirar
FichaAcolhimento    1:1 acolhido | data_entrada, motivo, orgao_requisitante,
                    processo_numero, vara, medida_protetiva,
                    data_desligamento, destino
DadosSaude          1:1 acolhido | tipo_sanguineo, alergias, condicoes, plano
Medicacao           N:1 acolhido | nome, dosagem, frequencia, inicio, fim
Escolaridade        N:1 acolhido | escola, serie, turno, ano_letivo
DocumentoAcolhido   N:1 acolhido | arquivo, tipo, descricao
```

`VinculoFamiliar` é uma relação muitos-para-muitos com atributos próprios. Um
responsável pode ter vínculo com dois irmãos acolhidos, e um acolhido tem
vários responsáveis com papéis distintos — mãe, avó guardiã, tio autorizado a
visitar. Uma chave estrangeira simples quebraria nesse caso, que é o comum.

### 4.3 doacoes

```
Doador     tipo [PF|PJ], nome, cpf_cnpj, telefone, email, +Endereco, recorrente
Campanha   nome, descricao, data_inicio, data_fim, meta_valor
Doacao     doador (nulo = anônima), campanha (nulo), tipo [DINHEIRO|ALIMENTO|
           VESTUARIO|MATERIAL|SERVICO|OUTRO], descricao, quantidade, unidade,
           valor (nulo), data_recebimento, recebido_por → Usuario, recibo_emitido
```

`doador` aceita nulo porque doação anônima é frequente. `valor` é separado de
`quantidade` porque "R$ 500" e "20 kg de arroz" não cabem no mesmo campo, e o
relatório financeiro precisa somar apenas o primeiro.

### 4.4 voluntarios

```
Voluntario        nome, cpf, rg, nascimento, telefone, email, +Endereco,
                  data_cadastro, status [ATIVO|INATIVO], funcoes (M2M), observacoes
Funcao            nome, descricao
Disponibilidade   N:1 voluntario | dia_semana [0-6], turno [MANHA|TARDE|NOITE]
DocumentoVol      N:1 voluntario | arquivo, tipo
```

### 4.5 escalas

```
Atividade   nome, descricao, ativa
Escala      titulo, data_inicio, data_fim, status [RASCUNHO|PUBLICADA], criada_por
Turno       N:1 escala | data, hora_inicio, hora_fim, atividade, vagas
Alocacao    turno ─ voluntario, status [PREVISTO|CONFIRMADO|FALTOU], observacao
            unique(turno, voluntario)
            clean(): recusa voluntário alocado em turnos sobrepostos
```

Escala em `RASCUNHO` pode ser remontada livremente; ao ser publicada, torna-se
registro. A checagem de sobreposição fica no `clean()` do model, e não na view,
para valer igualmente em formulários, no admin e em qualquer importação futura.

### 4.6 relatorios

Sem models. Apenas consultas e exportação.

### 4.7 Relações principais

```
Usuario ──cria──> [todos os registros]
Usuario ──recebe──> Doacao <──faz── Doador ──> Campanha

Acolhido ──1:1──> FichaAcolhimento, DadosSaude
         ──1:N──> Medicacao, Escolaridade, DocumentoAcolhido
         ──N:M──> Responsavel (via VinculoFamiliar)

Voluntario ──1:N──> Disponibilidade, DocumentoVol
           ──N:M──> Funcao
           ──N:M──> Turno (via Alocacao)

Escala ──1:N──> Turno ──N:1──> Atividade
```

---

## 5. Permissões, sigilo e auditoria

### 5.1 Matriz de acesso

| Módulo | Admin | Técnico | Operacional |
|---|---|---|---|
| Acolhidos — lista básica (nome, foto, status) | escreve | escreve | lê |
| Acolhidos — ficha completa (motivo, processo, vara) | escreve | escreve | sem acesso |
| Acolhidos — saúde e medicação | escreve | escreve | lê apenas medicação do dia |
| Acolhidos — criar e editar | escreve | escreve | sem acesso |
| Responsáveis e vínculos | escreve | escreve | lê apenas "autorizado a retirar" |
| Doações e doadores | escreve | lê | escreve |
| Voluntários | escreve | lê | escreve |
| Escalas | escreve | lê | escreve |
| Relatórios operacionais | escreve | escreve | escreve |
| Relatórios com dado de acolhido | escreve | escreve | sem acesso |
| Gerenciar usuários | escreve | sem acesso | sem acesso |

O perfil Operacional precisa saber que uma criança toma medicação às 14h e quem
está autorizado a buscá-la, mas não precisa saber o motivo do acolhimento nem o
número do processo. Esse é o recorte exigido pelo art. 143 do ECA.

### 5.2 Implementação em três camadas

Uma única camada de proteção sempre acaba vazando. São três:

1. **Porta da view** — `PerfilRequiredMixin` em `core/mixins.py`, declarando
   `perfis_permitidos`. Sem o perfil, retorna 403 antes de consultar o banco.
2. **Campo do formulário** — o `ModelForm` monta seus campos conforme o perfil.
   O campo restrito não existe no formulário, então um POST forjado não o
   alcança.
3. **Template** — o que não pode ser visto não é renderizado. Esconder via CSS
   deixaria o dado presente no HTML.

Os grupos do Django são criados por migration de dados, não manualmente. O
sistema nasce com os perfis corretos em qualquer instalação, inclusive na
hospedagem futura.

### 5.3 Auditoria

`django-simple-history` nos models sensíveis: `Acolhido`, `FichaAcolhimento`,
`DadosSaude` e `Doacao`. Guarda a versão anterior, o autor e o momento da
alteração. Atende dois casos reais: reconstituir dado alterado por engano e
responder a questionamento do Ministério Público sobre quem alterou um
registro.

`LogAcessoFicha` complementa registrando as leituras.

### 5.4 Proteções de base

- Arquivos enviados (foto, documento) não ficam em diretório público. São
  servidos por uma view que verifica permissão. Caso contrário, quem descobrisse
  a URL veria a foto de uma criança acolhida sem autenticação.
- Sessão expira por inatividade, pois o computador da recepção é compartilhado.
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` ativos
  em produção.
- Validadores de senha do Django; troca obrigatória no primeiro acesso.
- Exclusão sempre lógica; apenas o Admin acessa a lixeira.

### 5.5 LGPD

Escopo deliberadamente enxuto, limitado ao que a instituição consegue sustentar:

- Termo de consentimento do responsável, datado e anexado ao cadastro
- Campo de finalidade declarada no registro
- Exportação dos dados por titular, para atender pedido do responsável
- Política de retenção documentada

Não será construído módulo de compliance.

---

## 6. Telas e fluxos

O padrão para a maior parte do sistema é `ListView` com busca e filtro,
`DetailView`, `CreateView` e `UpdateView`, a partir de classes base em `core`.
Os fluxos descritos abaixo são os que fogem desse padrão.

### 6.1 Navegação

Barra superior com busca global e menu lateral com os módulos. O menu é montado
conforme o perfil: item sem permissão não é exibido, em vez de exibido e
retornar 403.

### 6.2 Acolhimento de nova criança (assistente em 4 etapas)

```
[1 Identificação] → [2 Acolhimento] → [3 Saúde e escola] → [4 Responsáveis]
   nome, nascimento   data de entrada   alergias             vínculos
   foto, documentos   motivo, órgão     medicação            autorização de
   naturalidade       processo, vara    escola, série        visita e retirada
```

Assistente em etapas, e não formulário único, por dois motivos: são cerca de 30
campos, e a etapa 2 é a única restrita ao perfil Técnico. O rascunho é salvo a
cada etapa, para que uma interrupção não descarte o trabalho.

### 6.3 Registro de doação

Tela otimizada para volume: doações chegam em lote, na portaria, com fila
esperando. Busca de doador com HTMX por sugestão a partir de três caracteres.
Botão "Salvar e novo" preserva data e doador. Os campos de valor e quantidade
aparecem conforme o tipo de doação escolhido.

### 6.4 Montagem de escala

Grade semanal com turnos nas linhas e dias nas colunas. Clicar em uma vaga abre
a lista de voluntários já filtrada pela disponibilidade declarada para aquele
dia e turno. Conflito de horário é bloqueado pelo `clean()` do model. Turnos
descobertos recebem destaque visual, porque a pergunta real do coordenador é
onde está a lacuna, e não quem já está escalado.

### 6.5 Desligamento

Ação explícita, não edição de campo. Solicita data, destino (reintegração
familiar, adoção, maioridade, transferência) e observação. Altera o status para
`DESLIGADO`, remove das listagens ativas e preserva o histórico completo.
Restrito a Técnico e Admin.

### 6.6 Busca global

Campo único que consulta acolhidos, doadores e voluntários, com resultados
agrupados por tipo e filtrados pelo perfil do usuário.

### 6.7 Painel inicial

Cartões variam por perfil:

- **Todos** — acolhidos ativos, doações do mês, voluntários ativos
- **Técnico** — aniversariantes da semana, medicações do dia, fichas incompletas
- **Operacional** — escala de hoje, turnos descobertos nos próximos sete dias
- **Admin** — resumo financeiro do mês, doadores recorrentes sem doação há 60 dias

---

## 7. Relatórios

Cada relatório é uma função em `relatorios/services.py` que devolve dados
estruturados. Três renderizadores genéricos consomem essa saída: tela, CSV e
PDF. Um relatório novo é uma função, não uma tela inteira.

| Relatório | Conteúdo | Acesso |
|---|---|---|
| Acolhidos ativos | Nome, idade, entrada, tempo de acolhimento | Admin, Técnico |
| Movimentação | Entradas e desligamentos no período, com motivo | Admin, Técnico |
| Doações por período | Agrupado por tipo, com totais | Todos |
| Histórico do doador | Doações de um doador, com soma | Admin, Operacional |
| Prestação de contas mensal | Financeiro e doações em espécie | Admin |
| Voluntários ativos | Cadastro, função, disponibilidade | Todos |
| Frequência em escala | Previsto, confirmado e faltas por voluntário | Admin, Operacional |
| Recibo de doação | Documento individual para o doador | Admin, Operacional |

Os três formatos atendem necessidades distintas: a tela serve à consulta
diária, o CSV é o que a contabilidade consegue usar, e o PDF é exigido na
prestação de contas ao conselho e aos mantenedores.

O PDF é gerado pelo WeasyPrint a partir do mesmo template HTML da tela, com CSS
de impressão. Não há um segundo layout a manter.

**Sigilo em relatórios:** todo PDF que contenha nome de acolhido é emitido com
marca de documento sigiloso, identificação do emissor e data. Relatórios
destinados a público externo usam dados agregados, sem identificação.

---

## 8. Qualidade e operação

### 8.1 Testes

pytest, pytest-django e factory_boy. Três frentes, em ordem de valor:

1. **Regras de negócio**, com testes escritos antes da implementação:
   sobreposição de turno, exclusão lógica ausente das listagens, cálculo de
   tempo de acolhimento, totalização de doações por tipo.
2. **Matriz de permissão**: cada célula da tabela da seção 5.1 corresponde a um
   teste. São muitos testes pequenos, e constituem o investimento mais rentável
   do projeto — uma regressão de permissão significa expor dado de criança, e é
   o tipo de falha que passa despercebido em teste manual.
3. **Fluxos críticos**: assistente de acolhimento, registro de doação,
   publicação de escala.

A meta não é cobertura total, e sim cobertura das regras de negócio e das
permissões.

### 8.2 Padronização

`ruff` para lint e formatação, executado via `pre-commit`.

### 8.3 Tratamento de erros

Páginas 403, 404 e 500 próprias, em português, dentro do layout do sistema.
Mensagens de validação escritas para usuário leigo: "CPF já cadastrado para
João Silva", e não a exceção do banco.

### 8.4 Dados de demonstração

Comando `python manage.py seed_demo` popula o banco com dados fictícios
coerentes. Serve à apresentação do projeto de extensão e permite que qualquer
pessoa suba o sistema e compreenda seu funcionamento rapidamente.

### 8.5 Backup

Comando de exportação agendado e procedimento escrito. O Supabase de
desenvolvimento possui backup próprio, mas a instituição operará em outro banco,
e backup de sistema de organização social só acontece quando está documentado e
automatizado.

### 8.6 Documentação entregue

- `README.md` — instalação e execução
- `docs/manual-usuario.md` — operação, com telas
- `docs/manual-admin.md` — backup, gestão de usuários, publicação
- `docs/superpowers/specs/` — decisões técnicas

O manual do usuário não é exigência acadêmica: sem ele, o sistema é abandonado
quando o projeto de extensão se encerra.

---

## 9. Fora de escopo

Registrado explicitamente para evitar expansão não planejada:

- Aplicativo móvel
- Portal de acesso para doadores ou responsáveis
- Integração com sistemas públicos (SIPIA, CadÚnico)
- Controle de estoque de doações com baixa automática
- Módulo financeiro contábil completo
- Notificação por e-mail ou mensagem
- API pública

Itens desta lista podem ser incorporados em fases futuras, mediante nova
avaliação com a instituição.
