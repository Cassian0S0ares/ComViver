from django.apps import AppConfig


class EscalasConfig(AppConfig):
    name = "escalas"
    verbose_name = "Escalas"

    def ready(self):
        from . import signals  # noqa: F401
