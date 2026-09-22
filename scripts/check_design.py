"""Check documented colors, fonts and spacing against the canonical CSS tokens."""

import re
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
document = (root / "DESIGN.md").read_text(encoding="utf-8")
tokens = (root / "static/css/tokens.css").read_text(encoding="utf-8")
metadata = yaml.safe_load(document.split("---", 2)[1])
for name, value in metadata["colors"].items():
    assert f"--color-{name}: {value};" in tokens, name
for name, value in metadata["spacing"].items():
    actual = re.search(rf"--space-{name}:\s*([^;]+);", tokens)[1]
    assert float(actual.removesuffix("rem")) == float(value.removesuffix("rem")), name
for name, value in metadata["typography"].items():
    assert value["fontFamily"].split(",")[0] in tokens, name
print("Design: cores, tipografia e espaçamento sem divergências.")
