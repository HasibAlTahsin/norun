from __future__ import annotations

import subprocess
from pathlib import Path
from rich import print

from norun.core import run_app, list_apps, choose_runner, create_app, init_prefix, install
from norun.config import load_config


def _zenity_ok() -> bool:
    return bool(subprocess.run(["which", "zenity"], capture_output=True).returncode == 0)


def _z(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(["zenity", *args], capture_output=True, text=True)
    return p.returncode, (p.stdout or "").strip()


def _badge(cfg: dict) -> str:
    runner = cfg.get("runner", "wine")
    sandbox = "🛡" if cfg.get("sandbox") else ""
    mode = cfg.get("sandbox_mode", "full")
    if sandbox:
        sandbox += mode
    return f"{runner} {sandbox}".strip()


def pick_and_run():
    if not _zenity_ok():
        raise RuntimeError("zenity not found. Install: sudo apt install -y zenity")

    rows: list[list[str]] = []
    for name in list_apps():
        cfg = load_config(name) or {}
        rows.append([
            name,
            cfg.get("profile", ""),
            _badge(cfg),
            cfg.get("last_exe", ""),
        ])

    if not rows:
        _z(["--info", "--text=No apps found. Use: norun add ... or norun gui"])
        return

    args = [
        "--list",
        "--title=NORUN — Pick & Run",
        "--width=900",
        "--height=520",
        "--search-column=1",
        "--print-column=1",
        "--column=App",
        "--column=Profile",
        "--column=Runner/Sandbox",
        "--column=Last EXE",
    ]
    for r in rows:
        args += r

    rc, out = _z(args)
    if rc != 0 or not out:
        return

    try:
        run_app(out, None)
    except Exception as e:
        _z(["--error", f"--text={str(e)}"])


def gui_flow():
    """
    GUI flow:
      1) choose installer
      2) name
      3) profile
      4) sandbox + mode
      5) portable?
      6) install + run
    """
    if not _zenity_ok():
        raise RuntimeError("zenity not found. Install: sudo apt install -y zenity")

    rc, installer = _z(["--file-selection", "--title=Pick EXE/MSI", "--file-filter=Windows installers | *.exe *.msi"])
    if rc != 0 or not installer:
        return

    default_name = Path(installer).stem.lower().replace(" ", "_")[:32]
    rc, name = _z(["--entry", "--title=App name", f"--text=Name:", f"--entry-text={default_name}"])
    if rc != 0 or not name:
        return

    rc, profile = _z([
        "--list",
        "--title=Profile",
        "--height=240",
        "--print-column=1",
        "--column=Profile",
        "general",
        "games",
        "dotnet",
    ])
    if rc != 0 or not profile:
        profile = "general"

    runner = choose_runner(profile, installer)

    rc, sandbox_choice = _z([
        "--list",
        "--title=Sandbox",
        "--height=240",
        "--print-column=1",
        "--column=Mode",
        "no-sandbox",
        "sandbox(full)",
        "sandbox(strict)",
    ])
    if rc != 0 or not sandbox_choice:
        sandbox_choice = "no-sandbox"

    sandbox = sandbox_choice.startswith("sandbox")
    sandbox_mode = "strict" if "strict" in sandbox_choice else "full"

    rc, portable_choice = _z([
        "--list",
        "--title=Portable?",
        "--height=200",
        "--print-column=1",
        "--column=Type",
        "normal-installer",
        "portable-exe",
    ])
    if rc != 0 or not portable_choice:
        portable_choice = "normal-installer"
    portable = (portable_choice == "portable-exe")

    cfg = create_app(name, profile, runner, sandbox=sandbox, sandbox_mode=sandbox_mode)

    try:
        init_prefix(cfg)
        install(cfg, installer, portable=portable)
        _z(["--info", f"--text=Installed: {name}\nRunner={runner}\nSandbox={sandbox} ({sandbox_mode})"])
    except Exception as e:
        _z(["--error", f"--text={str(e)}"])
        return

    rc, _ = _z([
        "--question",
        "--title=Run now?",
        "--text=Run the app now?",
        "--ok-label=Run",
        "--cancel-label=Close",
    ])
    if rc == 0:
        try:
            run_app(name, None)
        except Exception as e:
            _z(["--error", f"--text={str(e)}"])

