"""Aguarda o servidor local antes de abrir a página do sistema."""

import sys
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
url = f"http://127.0.0.1:{porta}/entrar/"
for _ in range(120):
    try:
        with urlopen(url, timeout=1) as resposta:
            if resposta.status == 200:
                webbrowser.open(url)
                break
    except (URLError, TimeoutError, OSError):
        pass
    time.sleep(0.5)
