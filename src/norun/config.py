from __future__ import annotations

from pathlib import Path
import yaml

BASE = Path.home() / ".local" / "share" / "norun"
APPS_DIR = BASE / "apps"
PFX_DIR = BASE / "prefixes"
CACHE_DIR = BASE / "cache"
LOG_DIR = BASE / "logs"

def ensure_dirs():
    for d in (APPS_DIR, PFX_DIR, CACHE_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

def app_dir(name: str) -> Path:
    return APPS_DIR / name

def prefix_dir(name: str) -> Path:
    return PFX_DIR / name

def config_path(name: str) -> Path:
    return app_dir(name) / "config.yaml"

def load_config(name: str) -> dict:
    p = config_path(name)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()) or {}

def save_config(name: str, data: dict):
    d = app_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    config_path(name).write_text(yaml.safe_dump(data, sort_keys=False))

