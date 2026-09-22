"""Fluxo real da fase 3, executado explicitamente com Edge e PostgreSQL local."""

from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from accounts.factories import UsuarioFactory
from accounts.models import Perfil
from doacoes.factories import DoadorFactory
from doacoes.models import Doacao

pytestmark = pytest.mark.django_db(transaction=True)


def test_doacoes_no_navegador(live_server):
    UsuarioFactory(
        email="doacoes@exemplo.org",
        perfil=Perfil.ADMIN,
        password="doacao-browser-123",
        first_name="Marina",
    )
    doador = DoadorFactory(nome="Padaria Exemplo")
    output = Path("test-results")
    output.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="pt-BR")
        erros = []
        page.on("pageerror", lambda error: erros.append(str(error)))
        page.goto(f"{live_server.url}/entrar/")
        page.locator("#id_username").fill("doacoes@exemplo.org")
        page.locator("#id_password").fill("doacao-browser-123")
        page.get_by_role("button", name="Entrar no sistema").click()
        page.get_by_role("link", name="Doações", exact=True).click()
        page.get_by_role("link", name="Registrar doação", exact=True).click()
        page.locator("#id_tipo").select_option("DINHEIRO")
        page.get_by_role("button", name="Salvar doação", exact=True).click()
        expect(page.get_by_text("Informe o valor da doação em dinheiro.")).to_be_visible()
        page.locator("#doador-busca").fill("Inexistente")
        expect(page.get_by_text("Nenhum doador encontrado.")).to_be_visible()
        page.get_by_role("button", name="Limpar busca de doador").click()
        expect(page.locator("#doador-busca")).to_be_focused()
        page.route("**/doacoes/buscar-doador/**", lambda route: route.abort(), times=1)
        page.locator("#doador-busca").fill("Falha")
        expect(page.get_by_text("Não foi possível buscar.", exact=False)).to_be_visible()
        page.locator("#doador-busca").fill("Padaria")
        expect(page.locator("[data-donor-id]").first).to_be_visible()
        page.locator("#doador-busca").press("ArrowDown")
        page.locator("#doador-busca").press("Enter")
        expect(page.locator("#id_doador")).to_have_value(str(doador.pk))
        page.locator("#id_valor").fill("250,50")
        page.get_by_role("button", name="Salvar e registrar outra", exact=True).click()
        expect(page).to_have_url(__import__("re").compile(r"/doacoes/nova/\?data=.*doador="))
        expect(page.locator("#id_doador")).to_have_value(str(doador.pk))
        page.locator("#id_tipo").select_option("ALIMENTO")
        page.locator("#id_descricao").fill("Arroz 5 kg")
        page.locator("#id_quantidade").fill("10")
        page.locator("#id_unidade").fill("pacotes")
        page.screenshot(path=str(output / "doacao-form-desktop.png"), full_page=True)
        page.get_by_role("button", name="Salvar doação", exact=True).click()
        expect(page.get_by_text("10 pacotes", exact=True)).to_be_visible()
        page.screenshot(path=str(output / "doacoes-desktop.png"), full_page=True)
        page.get_by_role("link", name=__import__("re").compile(r"Recibo da doação")).first.click()
        expect(page.get_by_role("heading", name="Recibo de doação")).to_be_visible()
        with page.expect_download() as download_info:
            page.get_by_role("link", name="Baixar PDF").click()
        download_info.value.save_as(str(output / "recibo-fase3.pdf"))
        page.screenshot(path=str(output / "recibo-desktop.png"), full_page=True)
        page.get_by_role("button", name="Marcar como entregue").click()
        expect(page.get_by_text("Recibo entregue", exact=True)).to_be_visible()
        page.get_by_role("link", name="Voltar para doações", exact=False).click()
        page.get_by_role("link", name="Doadores", exact=True).click()
        page.get_by_role("link", name="Novo doador", exact=True).click()
        page.locator("#id_nome").fill("Instituto Exemplo UI")
        page.locator("#id_tipo").select_option("PJ")
        page.get_by_role("button", name="Salvar doador", exact=True).click()
        expect(page.get_by_role("heading", name="Instituto Exemplo UI")).to_be_visible()
        page.get_by_role("link", name="Editar cadastro").click()
        page.locator("#id_email").fill("instituto@example.org")
        page.get_by_role("button", name="Salvar doador", exact=True).click()
        expect(page.get_by_text("instituto@example.org", exact=True)).to_be_visible()
        page.screenshot(path=str(output / "doador-desktop.png"), full_page=True)
        page.get_by_role("link", name="Campanhas", exact=True).click()
        page.get_by_role("link", name="Nova campanha", exact=True).click()
        page.locator("#id_nome").fill("Campanha Exemplo UI")
        page.locator("#id_data_inicio").fill((timezone.localdate() - timedelta(days=2)).isoformat())
        page.locator("#id_meta_valor").fill("1500.00")
        page.get_by_role("button", name="Salvar campanha", exact=True).click()
        expect(page.get_by_role("heading", name="Campanha Exemplo UI")).to_be_visible()
        page.get_by_role("link", name="Editar campanha e período", exact=False).click()
        page.locator("#id_data_fim").fill((timezone.localdate() - timedelta(days=1)).isoformat())
        page.get_by_role("button", name="Salvar campanha", exact=True).click()
        expect(page.get_by_text("FORA DO PERÍODO", exact=True)).to_be_visible()
        page.screenshot(path=str(output / "campanhas-desktop.png"), full_page=True)
        page.get_by_role("link", name="Doações", exact=True).click()
        page.emulate_media(reduced_motion="reduce")
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(output / "doacoes-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("link", name="Registrar doação", exact=True).click()
        page.screenshot(path=str(output / "doacao-form-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not erros
        browser.close()
    assert Doacao.objects.count() == 2
    assert Doacao.objects.filter(recibo_emitido=True).count() == 1
