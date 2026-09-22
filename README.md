# ComViver

Gestão administrativa do Lar Padre José Gumercindo.

Fase 1 implementada: autenticação, troca obrigatória de senha, três perfis,
controle de acesso, painel e gestão de usuários. A interface tem identidade
própria, responsiva, em português, com fontes e Bootstrap servidos localmente.

## Instalação

Requisitos: Python 3.12 e PostgreSQL com conexão direta e SSL. O banco de testes
é separado automaticamente pelo pytest; a conta precisa poder criar bancos.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/dev.txt
Copy-Item .env.example .env
```

Preencha `.env` localmente:

- `SECRET_KEY`: chave aleatória longa e exclusiva.
- `DEBUG`: `True` no desenvolvimento.
- `ALLOWED_HOSTS`: `localhost,127.0.0.1` no desenvolvimento.
- `DATABASE_URL`: URI PostgreSQL direta, porta 5432, fornecida pelo Supabase.
- `CSRF_TRUSTED_ORIGINS`: domínio HTTPS em produção.

Uma chave pode ser gerada no seu terminal com:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Não versione nem compartilhe `.env`. A conexão Supabase ficou para configuração
posterior, conforme solicitado. Nenhuma credencial remota foi criada.

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abra `http://127.0.0.1:8000/`. O superusuário inicial tem perfil Administrador.
Novas pessoas cadastradas pela interface precisam trocar a senha no primeiro acesso.

## Qualidade

```powershell
python -m pytest
ruff check .
ruff format --check .
python scripts/check_design.py
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
```

Os testes usam **PostgreSQL**, inclusive os modelos abstratos. Depois de mudar
models/migrations, execute `python -m pytest --create-db`.

O teste de navegador é explícito e exige Edge instalado:

```powershell
python -m pytest tests/browser_smoke.py
```

Ele usa o banco de testes, cria dados fictícios e salva capturas em `test-results/`
(ignorado pelo Git). Não executá-lo ao mesmo tempo que outra suíte no mesmo banco.

Para ativar verificações antes de commits: `pre-commit install`.

## Ambiente local desta implementação

O ambiente `.venv312/` usa Python 3.12.14. `.tools/` contém ferramentas isoladas
de validação, sem dependência de instalação global. O PostgreSQL local escuta
somente em `127.0.0.1:55432`, usa dados fictícios e certificado temporário.

```powershell
.venv312/Scripts/python scripts/local_validation.py -m pytest
.venv312/Scripts/python scripts/local_validation.py manage.py check
```

O wrapper substitui variáveis **apenas no processo filho**, sem alterar `.env`.
Esse banco é descartável e não deve receber dados reais. O certificado de
validação dura sete dias; `scripts/local_certificate.py` requer `cryptography`
(ferramenta opcional de desenvolvimento, fora das dependências da aplicação).

## Documentação

- [Identidade visual](DESIGN.md)
- [Contrato de interface](UX-CONTRACT.md)
- [Manual da equipe](docs/manual-usuario.md)
- [Manual de administração](docs/manual-admin.md)
- [Verificação da fase 1](docs/fase1-verificacao.md)
- [Plano original](docs/superpowers/plans/2026-09-22-comviver-fase1-fundacao.md)

Os módulos de acolhidos, doações, voluntários, escalas e relatórios são fases
posteriores. O painel desta fase usa somente a contagem real de usuários ativos.
