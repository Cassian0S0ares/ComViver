"""Calendário semanal: menu, inclusão pelo horário, validação e responsividade."""
from pathlib import Path

import pytest
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.factories import UsuarioFactory
from accounts.models import Perfil
from escalas.models import Atividade, Turno
from voluntarios.factories import VoluntarioFactory

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("tipo", ["voluntario", "usuario"])
def test_calendario_no_navegador(live_server, tipo):
    UsuarioFactory(email="calendario@exemplo.org", perfil=Perfil.ADMIN,
                   password="calendario-browser-123")
    if tipo == "usuario":
        pessoa = UsuarioFactory(first_name="Ana", last_name="Souza")
        escolha = f"usuario:{pessoa.pk}"
    else:
        pessoa = VoluntarioFactory(nome="Ana Souza")
        escolha = str(pessoa.pk)
    atividade, _ = Atividade.objects.get_or_create(nome="Acompanhamento escolar")
    output = Path("test-results")
    output.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="pt-BR")
        erros = []
        page.on("pageerror", lambda error: erros.append(str(error)))
        page.goto(f"{live_server.url}/entrar/")
        page.locator("#id_username").fill("calendario@exemplo.org")
        page.locator("#id_password").fill("calendario-browser-123")
        page.get_by_role("button", name="Entrar no sistema").click()
        page.get_by_role("link", name="Escalas", exact=True).click()
        expect(page.locator(".cronograma-dia")).to_have_count(7)
        expect(page.get_by_role("link", name="Nova escala", exact=True)).to_have_count(0)
        expect(page.get_by_role("region", name="Horários da semana")).to_be_visible()
        page.goto(live_server.url + reverse("escalas:lista") + "?semana=2026-09-23")
        page.get_by_role("link", name="Próxima semana", exact=True).click()
        expect(page.get_by_role("heading", name="27/09 a 03/10/2026")).to_be_visible()
        page.get_by_role("link", name="Semana anterior", exact=True).click()
        slot = page.get_by_role("link", name="Adicionar turno em 23/09/2026 às 09:00")
        slot.focus()
        slot.press("Enter")
        dialog = page.get_by_role("dialog", name="Adicionar turno", exact=True)
        expect(dialog).to_be_visible()
        expect(dialog.locator("#id_data")).to_have_value("2026-09-23")
        expect(dialog.locator("#id_hora_inicio")).to_have_value("09:00")
        dialog.locator("#id_responsavel").select_option(escolha)
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog", name="Sair sem salvar?")).to_be_visible()
        page.get_by_role("button", name="Continuar editando").click()
        expect(dialog.locator("#id_responsavel")).to_have_value(escolha)
        dialog.locator("#id_hora_fim").select_option("12:30")
        dialog.locator("#id_atividade").select_option(str(atividade.pk))
        dialog.get_by_role("button", name="Salvar turno", exact=True).click()
        expect(page.locator(".cronograma-evento")).to_have_count(1)
        expect(page.locator(".cronograma-evento")).to_contain_text("Ana Souza")
        expect(page.locator(".cronograma-evento")).to_contain_text("09:00–12:30")
        page.reload()
        expect(page.locator(".cronograma-evento")).to_contain_text("Ana Souza")
        page.screenshot(path=str(output / "escalas-calendario-desktop.png"), full_page=True)
        page.get_by_role("link", name="Adicionar turno", exact=True).click()
        dialog.locator("#id_data").fill("2026-09-23")
        dialog.locator("#id_hora_inicio").select_option("10:00")
        dialog.locator("#id_hora_fim").select_option("11:00")
        dialog.locator("#id_responsavel").select_option(escolha)
        dialog.locator("#id_atividade").select_option(str(atividade.pk))
        dialog.get_by_role("button", name="Salvar turno", exact=True).click()
        expect(page.locator("#id_responsavel_error")).to_contain_text("já está escalada")
        expect(page.locator("#id_responsavel")).to_be_focused()
        page.get_by_role("link", name="Cancelar", exact=True).click()
        page.emulate_media(reduced_motion="reduce")
        for width in (320, 390, 768):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            expect(page.get_by_role("region", name="Horários da semana")).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(output / "escalas-calendario-mobile.png"), full_page=True)
        page.get_by_role("link", name="Adicionar turno", exact=True).click()
        expect(dialog).to_be_visible()
        page.screenshot(path=str(output / "escalas-turno-mobile.png"), full_page=True)
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(page.get_by_role("link", name="Adicionar turno", exact=True)).to_be_focused()
        assert not erros
        browser.close()
    assert Turno.objects.count() == 1
