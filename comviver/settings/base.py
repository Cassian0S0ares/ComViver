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
    "axes",
    "simple_history",
    "formtools",
    "core",
    "accounts",
    "acolhidos",
    "doacoes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "accounts.middleware.TrocaSenhaObrigatoriaMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
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
                "core.context_processors.menu",
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

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ValueError("DATABASE_URL deve apontar para PostgreSQL.")
if str(DATABASES["default"].get("PORT")) == "6543":
    raise ValueError("Use a conexão direta PostgreSQL, não o pooler na porta 6543.")

AUTH_USER_MODEL = "accounts.Usuario"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "accounts.backends.EmailBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.5
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "accounts/bloqueado.html"
AXES_HTTP_RESPONSE_CODE = 429

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Arquivos enviados no meio do assistente de acolhimento, antes de o cadastro
# ser concluido. Fica fora de MEDIA_ROOT para nunca ser servido pela rota /media/.
ASSISTENTE_TEMP_DIR = BASE_DIR / ".assistente"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:painel"
LOGOUT_REDIRECT_URL = "accounts:login"

# Link de "esqueci minha senha" vale por 1 hora e deixa de valer assim que a
# senha e trocada.
PASSWORD_RESET_TIMEOUT = 60 * 60

# Envio de e-mail. Sem EMAIL_URL, as mensagens aparecem no terminal do servidor
# (util para desenvolvimento). Exemplo: smtp+tls://usuario:senha@smtp.gmail.com:587
vars().update(environ.Env.email_url_config(env("EMAIL_URL", default="") or "consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="") or "ComViver <nao-responda@localhost>"

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
