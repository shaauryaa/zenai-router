"""Load config.yaml and .env from the repo root."""
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .paths import CONFIG_FILE, DATA, ENV_FILE  # noqa: F401  (see paths.py)


def load_config(path: Path | None = None) -> dict:
    load_dotenv(ENV_FILE)
    with open(path or CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)
