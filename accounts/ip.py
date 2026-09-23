from django.conf import settings


def ip_do_visitante(request):
    """IP de origem usado pelo bloqueio de login.

    Cada proxy acrescenta ao fim do X-Forwarded-For o IP de quem o chamou, entao
    so as ultimas `PROXY_COUNT` entradas sao confiaveis. O inicio do cabecalho
    vem do navegador e pode ser forjado para escapar do bloqueio; por isso a
    leitura e feita da direita para a esquerda.
    """
    proxies = settings.PROXY_COUNT
    if proxies:
        encaminhados = [
            ip.strip()
            for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
            if ip.strip()
        ]
        if len(encaminhados) >= proxies:
            return encaminhados[-proxies]
    return request.META.get("REMOTE_ADDR")
