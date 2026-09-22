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
AXES_ENABLED = False
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
