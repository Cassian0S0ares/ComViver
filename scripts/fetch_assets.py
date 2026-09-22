"""Download versioned vendor files for local serving, without runtime CDNs."""

from pathlib import Path
from urllib.request import urlopen

ASSETS = {
    "bootstrap.min.css": "bootstrap@5.3.3/dist/css/bootstrap.min.css",
    "bootstrap.min.css.map": "bootstrap@5.3.3/dist/css/bootstrap.min.css.map",
    "bootstrap.bundle.min.js": "bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
    "bootstrap.bundle.min.js.map": "bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js.map",
    "bootstrap-icons.css": "bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    "fonts/bootstrap-icons.woff2": "bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2",
    "fonts/bootstrap-icons.woff": "bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff",
    "fonts/manrope.woff2": (
        "@fontsource-variable/manrope@5.2.6/files/manrope-latin-wght-normal.woff2"
    ),
    "fonts/source-sans-3.woff2": (
        "@fontsource-variable/source-sans-3@5.2.8/files/source-sans-3-latin-wght-normal.woff2"
    ),
}

for name, remote in ASSETS.items():
    path = Path("static/vendor", name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(f"https://cdn.jsdelivr.net/npm/{remote}", timeout=30) as response:
        path.write_bytes(response.read())
    print(name)
