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
