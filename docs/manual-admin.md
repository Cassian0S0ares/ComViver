# Administração — fase 1

## Publicação

Use Python 3.12, dependências de `requirements/prod.txt`, PostgreSQL direto com
SSL e `DJANGO_SETTINGS_MODULE=comviver.settings.prod`. WSGI/ASGI usam produção
por padrão. `manage.py` usa desenvolvimento por padrão; em produção, informe
sempre o módulo de settings pelo ambiente ou `--settings`.

Configure SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL e CSRF_TRUSTED_ORIGINS no
ambiente da hospedagem. Mantenha a chave estável entre processos e publicações.

```text
python manage.py migrate --settings=comviver.settings.prod
python manage.py collectstatic --noinput --settings=comviver.settings.prod
python manage.py check --deploy --settings=comviver.settings.prod
gunicorn comviver.wsgi:application
```

Gunicorn é destinado a Linux. O proxy HTTPS deve sobrescrever
X-Forwarded-Proto e impedir acesso externo direto ao processo de aplicação.
Cookies seguros, HSTS e redirecionamento HTTPS estão habilitados em produção.
Uploads futuros não são expostos por URLs públicas de mídia.

## Acessos

Crie o administrador inicial com `createsuperuser`. A gestão diária acontece em
**Usuários**; `/admin/` é exclusiva de superusuários para manutenção. Não use
UPDATE SQL para mudar perfis: `Usuario.save()` sincroniza o grupo correspondente.
Não use exclusão física de pessoas. O Django Admin desabilita essa ação.

Para redefinir uma senha esquecida, use `python manage.py changepassword NOME`
com settings do ambiente correto. Depois, marque **precisa trocar a senha** no
cadastro de manutenção. Entregue a senha provisória de forma reservada.

O django-axes registra tentativas. Após cinco erros, o IP de origem é bloqueado
por 30 minutos; a conta continua acessível de outras conexões. Atrás de proxy
HTTPS, defina `PROXY_COUNT` (número de proxies na frente da aplicação, em geral
1) para o bloqueio usar o IP real do visitante. Sem isso, todos compartilham o
IP do proxy e seriam bloqueados juntos. O superusuário pode revisar tentativas
em `/admin/` e desbloquear um IP pelo mecanismo do Axes. Sessões expiram após uma hora sem atividade e
ao fechar o navegador.

## Backup

Agende `pg_dump` no ambiente da hospedagem usando credenciais pelo mecanismo
seguro do PostgreSQL (`pgpass`/variáveis protegidas); nunca coloque senha no
comando versionado. Guarde arquivos em diretório com acesso exclusivo da
administração. Teste restauração em banco separado com `pg_restore` antes de
considerar o procedimento operacional. Agendamento e retenção dependem da
hospedagem, ainda não configurada nesta fase.

## Manutenção da interface

As fontes, ícones e Bootstrap são locais. `scripts/fetch_assets.py` reproduz os
downloads versionados. Licenças estão em `static/vendor/LICENCAS.md` e nas
distribuições originais. Ao alterar tokens, atualize `DESIGN.md` e execute
`scripts/check_design.py`. Novos módulos devem seguir `UX-CONTRACT.md`.
