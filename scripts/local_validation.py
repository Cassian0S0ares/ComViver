"""Run a command against the isolated local PostgreSQL (never the user's .env).

Usage: python scripts/local_validation.py manage.py check
The generated secret only lives in the child process environment.
"""

import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    environment = os.environ.copy()
    environment.update(
        SECRET_KEY=secrets.token_urlsafe(60),
        DATABASE_URL="postgres://comviver_test@127.0.0.1:55432/postgres",
        ALLOWED_HOSTS="localhost,127.0.0.1,testserver",
        DEBUG="False",
        DJANGO_SETTINGS_MODULE="comviver.settings.base",
    )
    if sys.argv[1:3] == ["-m", "pytest"]:
        environment["DJANGO_SETTINGS_MODULE"] = "comviver.settings.test"
    raise SystemExit(subprocess.call([sys.executable, *sys.argv[1:]], cwd=ROOT, env=environment))
