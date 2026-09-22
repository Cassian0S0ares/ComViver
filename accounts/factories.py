import factory

from accounts.models import Perfil, Usuario


class UsuarioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Usuario
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"usuario{n}")
    first_name = factory.Faker("first_name", locale="pt_BR")
    last_name = factory.Faker("last_name", locale="pt_BR")
    email = factory.LazyAttribute(lambda o: f"{o.username}@exemplo.org")
    perfil = Perfil.OPERACIONAL
    precisa_trocar_senha = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if create:
            obj.set_password(extracted or "senha-de-teste-123")
            obj.save()
