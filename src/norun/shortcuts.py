from __future__ import annotations

from pathlib import Path
import shutil
import sys

def _find_norun_exec() -> str:
    exe = shutil.which("norun")
    if exe:
        return exe
    py = sys.executable
    return f"{py} -m norun.cli"

def create_desktop_shortcut(name: str) -> Path:
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)

    desktop = apps / f"norun-{name}.desktop"
    exec_cmd = _find_norun_exec()

    content = f"""[Desktop Entry]
Type=Application
Name=NORUN - {name}
Exec={exec_cmd} run {name}
Terminal=false
Categories=Utility;
"""
    desktop.write_text(content, encoding="utf-8")
    return desktop

