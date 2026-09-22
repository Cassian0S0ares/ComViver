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
