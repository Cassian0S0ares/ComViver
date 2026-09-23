from django.test import RequestFactory

from accounts.ip import ip_do_visitante


def _requisicao(**meta):
    return RequestFactory().get("/", **meta)


def test_sem_proxy_usa_remote_addr_e_ignora_cabecalho(settings):
    settings.PROXY_COUNT = 0
    requisicao = _requisicao(HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="10.0.0.9")
    assert ip_do_visitante(requisicao) == "10.0.0.9"


def test_com_proxy_usa_ip_acrescentado_pelo_proxy(settings):
    settings.PROXY_COUNT = 1
    requisicao = _requisicao(HTTP_X_FORWARDED_FOR="200.10.20.30", REMOTE_ADDR="10.0.0.9")
    assert ip_do_visitante(requisicao) == "200.10.20.30"


def test_ip_forjado_no_inicio_do_cabecalho_e_ignorado(settings):
    settings.PROXY_COUNT = 1
    requisicao = _requisicao(
        HTTP_X_FORWARDED_FOR="1.2.3.4, 200.10.20.30", REMOTE_ADDR="10.0.0.9"
    )
    assert ip_do_visitante(requisicao) == "200.10.20.30"


def test_dois_proxies_pula_o_ip_do_proxy_intermediario(settings):
    settings.PROXY_COUNT = 2
    requisicao = _requisicao(
        HTTP_X_FORWARDED_FOR="1.2.3.4, 200.10.20.30, 172.16.0.5", REMOTE_ADDR="10.0.0.9"
    )
    assert ip_do_visitante(requisicao) == "200.10.20.30"


def test_cabecalho_ausente_cai_para_remote_addr(settings):
    settings.PROXY_COUNT = 1
    assert ip_do_visitante(_requisicao(REMOTE_ADDR="10.0.0.9")) == "10.0.0.9"
