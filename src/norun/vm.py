from __future__ import annotations

from pathlib import Path
import os

def is_wayland_session() -> bool:
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    if (os.environ.get("XDG_SESSION_TYPE") or "").lower() == "wayland":
        return True
    return False

def default_xauthority() -> str:
    return os.environ.get("XAUTHORITY") or str(Path.home() / ".Xauthority")

def extra_binds_for_gui() -> list[str]:
    binds: list[str] = []
    xauth = default_xauthority()
    if xauth and Path(xauth).exists():
        binds += ["--ro-bind", xauth, xauth]
    return binds

def recommend_virtual_desktop() -> str:
    # aggressive default
    return "1024x768"

