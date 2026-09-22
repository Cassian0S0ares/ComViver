"""Explicit browser gate: pytest tests/browser_smoke.py (requires Edge)."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from accounts.factories import UsuarioFactory
from accounts.models import Perfil, Usuario

pytestmark = pytest.mark.django_db(transaction=True)


def test_fluxo_e_responsividade(live_server):
    UsuarioFactory(
        email="coordenacao@exemplo.org",
        first_name="Marina",
        last_name="Almeida",
        perfil=Perfil.ADMIN,
        password="teste-browser-789",
    )
    for nome, sobrenome, perfil in [
        ("Ana", "Ribeiro", Perfil.TECNICO),
        ("Carlos", "Oliveira", Perfil.OPERACIONAL),
        ("Beatriz", "Santos", Perfil.TECNICO),
        ("João", "Ferreira", Perfil.OPERACIONAL),
    ]:
        UsuarioFactory(first_name=nome, last_name=sobrenome, perfil=perfil)
    output = Path("test-results")
    output.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="pt-BR")
        failures = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.goto(f"{live_server.url}/entrar/")
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(output / "login-desktop.png"), full_page=True)
        page.locator("#id_username").fill("coordenacao@exemplo.org")
        page.locator("#id_password").fill("errada")
        page.get_by_role("button", name="Entrar no sistema").click()
        expect(page.get_by_text("E-mail ou senha incorretos.")).to_be_visible()
        page.locator("#id_password").fill("teste-browser-789")
        page.get_by_role("button", name="Mostrar senha", exact=True).click()
        expect(page.locator("#id_password")).to_have_attribute("type", "text")
        page.get_by_role("button", name="Entrar no sistema").click()
        expect(page.get_by_role("heading", name="Olá, Marina.")).to_be_visible()
        page.screenshot(path=str(output / "painel-desktop.png"), full_page=True)
        page.get_by_role("link", name="Usuários", exact=True).click()
        page.screenshot(path=str(output / "usuarios-desktop.png"), full_page=True)
        page.get_by_role("link", name="Novo usuário", exact=True).click()
        page.get_by_role("button", name="Criar usuário", exact=True).click()
        expect(page.locator("[aria-invalid=true]").first).to_be_focused()
        page.locator("#id_first_name").fill("Luiza")
        page.locator("#id_last_name").fill("Costa")
        page.locator("#id_email").fill("luiza@example.org")
        page.locator("#id_perfil").select_option(Perfil.TECNICO)
        page.locator("#id_password1").fill("senha-nova-pessoa-789")
        page.locator("#id_password2").fill("senha-nova-pessoa-789")
        page.get_by_role("link", name="Cancelar", exact=True).click()
        expect(page.get_by_role("dialog", name="Sair sem salvar?")).to_be_visible()
        page.get_by_role("button", name="Continuar editando").click()
        page.get_by_role("button", name="Criar usuário", exact=True).click()
        expect(page.get_by_text("Usuário Luiza Costa criado.", exact=False)).to_be_visible()
        page.get_by_label("Buscar por nome ou e-mail").fill("sem-resultado")
        page.get_by_role("button", name="Filtrar", exact=True).click()
        expect(page.get_by_role("heading", name="Nenhum usuário encontrado")).to_be_visible()
        page.get_by_role("button", name="Limpar busca", exact=True).click()
        page.get_by_role("link", name="Editar Luiza Costa").click()
        page.locator("#id_perfil").select_option(Perfil.OPERACIONAL)
        page.get_by_role("button", name="Salvar alterações").click()
        expect(page.get_by_role("dialog", name="Alterar permissões de acesso?")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.get_by_role("button", name="Salvar alterações")).to_be_focused()
        page.get_by_role("button", name="Salvar alterações").click()
        page.get_by_role("button", name="Confirmar alterações").click()
        page.get_by_role("link", name="Desativar Luiza Costa").click()
        page.get_by_role("button", name="Desativar acesso", exact=True).click()
        expect(page.get_by_text("Acesso de Luiza Costa desativado.")).to_be_visible()
        for width in (320, 375, 414, 768):
            page.set_viewport_size({"width": width, "height": 900})
            for route in ("/", "/usuarios/", "/usuarios/novo/", "/trocar-senha/"):
                page.goto(f"{live_server.url}{route}")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                    width,
                    route,
                )
            page.goto(f"{live_server.url}/")
            page.screenshot(path=str(output / f"painel-{width}.png"), full_page=True)
        page.set_viewport_size({"width": 375, "height": 900})
        page.get_by_role("button", name="Abrir navegação").click()
        expect(page.get_by_role("link", name="Usuários", exact=True)).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.get_by_role("button", name="Abrir navegação")).to_be_focused()
        page.get_by_role("button", name="Sair do sistema").click()
        expect(page.get_by_role("heading", name="Bom ter você aqui.")).to_be_visible()
        page.screenshot(path=str(output / "login-mobile.png"), full_page=True)
        assert not failures, failures
        browser.close()
    assert not Usuario.objects.get(email="luiza@example.org").is_active
