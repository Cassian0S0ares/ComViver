"""Extrai as DLLs oficiais sem instalar runtime global no Windows.

Requer: python -m pip install 'pyinstaller>=6,<7'
"""

import hashlib
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

from PyInstaller.archive.readers import CArchiveReader

BASE = Path(__file__).resolve().parent.parent / ".tools"
URL = "https://github.com/Kozea/WeasyPrint/releases/download/v63.1/weasyprint-windows.zip"
arquivo = BASE / "weasyprint-windows.zip"
arquivo.parent.mkdir(parents=True, exist_ok=True)
if not arquivo.exists():
    with urlopen(URL, timeout=120) as resposta:
        arquivo.write_bytes(resposta.read())
hash_esperado = "db996021f6aacbaea5da26c8e4f6799a88117cd7739e6b2689afd1d16eec4fd2"
if hashlib.sha256(arquivo.read_bytes()).hexdigest() != hash_esperado:
    raise RuntimeError("O pacote não corresponde ao WeasyPrint v63.1 verificado.")
print("Pacote oficial v63.1 verificado.")
destino = BASE / "weasyprint"
destino.mkdir(exist_ok=True)
with ZipFile(arquivo) as pacote:
    # Extração com lista explícita; nenhum caminho do ZIP é usado como destino.
    (destino / "weasyprint.exe").write_bytes(pacote.read("dist/weasyprint.exe"))
    (destino / "LICENSE").write_bytes(pacote.read("LICENSE"))
runtime = destino / "runtime"
runtime.mkdir(exist_ok=True)
pacote = CArchiveReader(str(destino / "weasyprint.exe"))
for nome in pacote.toc:
    if "/" in nome or "\\" in nome:
        continue
    if nome.lower().endswith(".dll") and nome.lower().startswith(
        ("lib", "zlib", "msvcp", "vcruntime")
    ):
        (runtime / nome).write_bytes(pacote.extract(nome))
print("Bibliotecas de PDF prontas em", runtime)
