from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable

from norun.desktop import DesktopSpec


def _env_with_overrides(base_env: dict[str, str], *, dxvk_enabled: bool) -> dict[str, str]:
    env = dict(base_env)

    # If DXVK disabled => force builtin d3d stack (native disabled)
    # This is the safest default for general GUI apps (7-Zip, Notepad++, etc.)
    if not dxvk_enabled:
        overrides = "dxgi,d3d11,d3d10core,d3d9=n"
        prev = env.get("WINEDLLOVERRIDES")
        env["WINEDLLOVERRIDES"] = overrides if not prev else f"{overrides};{prev}"

    return env


def build_wine_command(
    win_exe: str,
    *,
    desktop: DesktopSpec | None = None,
) -> list[str]:
    # If desktop specified: use explorer virtual desktop wrapper
    if desktop is not None:
        return ["wine", "explorer", desktop.to_wine_arg(), win_exe]
    return ["wine", win_exe]


def launch_wine(
    *,
    wineprefix: str,
    win_exe: str,
    desktop: DesktopSpec | None,
    dxvk_enabled: bool,
    wait: bool,
    extra_args: Iterable[str] = (),
) -> int:
    env = _env_with_overrides(os.environ, dxvk_enabled=dxvk_enabled)
    env["WINEPREFIX"] = wineprefix

    cmd = build_wine_command(win_exe, desktop=desktop)
    cmd.extend(list(extra_args))

    try:
        proc = subprocess.Popen(cmd, env=env)
    except OSError:
        # failed to spawn wine
        return 10

    if not wait:
        print(f"[norun] started pid={proc.pid}")
        return 0

    return int(proc.wait())
