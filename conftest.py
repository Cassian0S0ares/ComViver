import pytest

from accounts.factories import UsuarioFactory
from accounts.models import Perfil


@pytest.fixture
def cliente_anonimo(client):
    """Cliente HTTP sem autenticacao."""
    return client


@pytest.fixture
def usuario_admin(db):
    return UsuarioFactory(perfil=Perfil.ADMIN)


@pytest.fixture
def usuario_tecnico(db):
    return UsuarioFactory(perfil=Perfil.TECNICO)


@pytest.fixture
def usuario_operacional(db):
    return UsuarioFactory(perfil=Perfil.OPERACIONAL)
