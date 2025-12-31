from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import time
import glob

from rich import print

from norun.config import (
    ensure_dirs,
    prefix_dir,
    save_config,
    load_config,
    LOG_DIR,
    CACHE_DIR,
    APPS_DIR,
)
from norun.profiles import PROFILES


def _env_for(prefix: Path) -> dict:
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    env.setdefault("WINEDEBUG", "-all")
    env["DXVK_STATE_CACHE_PATH"] = str(CACHE_DIR / "dxvk")
    env["VKD3D_SHADER_CACHE_PATH"] = str(CACHE_DIR / "vkd3d")
    return env


def _wrap_bwrap(
    cmd: list[str],
    *,
    mode: str = "full",
    allow_downloads: bool = True,
    extra_binds: list[str] | None = None,
) -> list[str]:
    """
    Bubblewrap sandbox wrapper.

    mode:
      - "full"   : read-only bind host / + bind HOME (compatibility)
      - "strict" : read-only bind host / + NO HOME bind; only allow prefix+norun dirs (+ optional Downloads)

    Notes:
    - We ro-bind "/" to avoid "execvp wine: No such file or directory" loader/symlink issues on many distros.
    - "strict" still improves security a lot by not exposing $HOME.
    """
    if mode not in {"full", "strict"}:
        raise RuntimeError("sandbox mode must be one of: full, strict")

    home = str(Path.home())
    norun_root = str(Path.home() / ".local" / "share" / "norun")
    downloads = str(Path.home() / "Downloads")

    binds = [
        "--unshare-all",
        "--share-net",
        "--die-with-parent",
        "--new-session",
        "--dev-bind",
        "/dev",
        "/dev",
        # IMPORTANT: whole root filesystem read-only (reliable wine exec across distros)
        "--ro-bind",
        "/",
        "/",
        "--proc",
        "/proc",
        "--tmpfs",
        "/tmp",
    ]

    # GPU accel (DXVK/VKD3D)
    if Path("/dev/dri").exists():
        binds += ["--dev-bind", "/dev/dri", "/dev/dri"]

    # Session runtimes (XDG portals/dbus/etc)
    xdg_rt = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_rt and Path(xdg_rt).exists():
        binds += ["--bind", xdg_rt, xdg_rt]

    # X11 sockets
    if os.environ.get("DISPLAY"):
        if Path("/tmp/.X11-unix").exists():
            binds += ["--bind", "/tmp/.X11-unix", "/tmp/.X11-unix"]
        if Path("/tmp/.ICE-unix").exists():
            binds += ["--bind", "/tmp/.ICE-unix", "/tmp/.ICE-unix"]

    # Wayland runtime already covered via XDG_RUNTIME_DIR bind above

    # policy: full mode binds home; strict does not
    if mode == "full":
        binds += ["--bind", home, home]
        if allow_downloads and Path(downloads).exists():
            binds += ["--bind", downloads, downloads]
    else:
        # strict: only norun dirs + optional Downloads
        if Path(norun_root).exists():
            binds += ["--bind", norun_root, norun_root]
        if allow_downloads and Path(downloads).exists():
            binds += ["--bind", downloads, downloads]

        # If app needs Xauthority, bind it (common on X11)
        xauth = os.environ.get("XAUTHORITY") or str(Path.home() / ".Xauthority")
        if xauth and Path(xauth).exists():
            binds += ["--ro-bind", xauth, xauth]

    if extra_binds:
        # extra_binds must already be valid bwrap args like: ["--bind", "/a", "/a", "--ro-bind", "/b", "/b"]
        binds += extra_binds

    return ["bwrap", *binds, "--", *cmd]


def _run(
    cmd: list[str],
    env: dict | None = None,
    log_path: Path | None = None,
    sandbox: bool = False,
    allow_downloads: bool = True,
    sandbox_mode: str = "full",
    extra_binds: list[str] | None = None,
) -> int:
    """
    Run a command optionally inside bubblewrap sandbox and log output.

    Hardenings:
    - resolve cmd[0] to absolute path before sandboxing (prevents PATH issues)
    - for wine, set WINESERVER absolute path (wine spawns wineserver internally)
    """
    run_env = (env or os.environ.copy()).copy()

    if sandbox:
        if not shutil.which("bwrap"):
            raise RuntimeError(
                "Sandbox requested but bubblewrap (bwrap) not installed. "
                "Run: sudo apt install -y bubblewrap"
            )

        # resolve main executable to absolute path
        if cmd and not os.path.isabs(cmd[0]):
            resolved = shutil.which(cmd[0])
            if not resolved:
                raise RuntimeError(f"Command not found: {cmd[0]}")
            cmd = [resolved, *cmd[1:]]

        # Wine spawns wineserver; in sandbox it may fail to locate it
        base = os.path.basename(cmd[0])
        if base in {"wine", "wine64"}:
            ws = shutil.which("wineserver")
            if ws:
                run_env["WINESERVER"] = ws

        cmd = _wrap_bwrap(
            cmd,
            mode=sandbox_mode,
            allow_downloads=allow_downloads,
            extra_binds=extra_binds,
        )

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
            f.write(f"\n\n$ {' '.join(cmd)}\n--- {time.ctime()} ---\n")
            p = subprocess.Popen(cmd, env=run_env, stdout=f, stderr=f)
            return p.wait()

    return subprocess.call(cmd, env=run_env)


def list_apps() -> list[str]:
    if not APPS_DIR.exists():
        return []
    return sorted([p.name for p in APPS_DIR.iterdir() if p.is_dir()])


def doctor() -> dict:
    return {
        "wine": bool(shutil.which("wine")),
        "winetricks": bool(shutil.which("winetricks")),
        "umu-run": bool(shutil.which("umu-run")),
        "zenity": bool(shutil.which("zenity")),
        "bwrap": bool(shutil.which("bwrap")),
    }


def choose_runner(profile: str, installer_path: str) -> str:
    low = installer_path.lower()
    if profile == "games":
        return "proton"
    if any(x in low for x in ["steam", "epic", "gog", "unity", "unreal", "dx12", "vulkan"]):
        return "proton"
    return "wine"


def create_app(
    name: str,
    profile: str,
    runner: str,
    sandbox: bool = False,
    sandbox_mode: str = "full",
) -> dict:
    ensure_dirs()
    if profile not in PROFILES:
        raise RuntimeError(f"Unknown profile: {profile} (choose from {', '.join(PROFILES)})")
    if runner not in ("wine", "proton"):
        raise RuntimeError("runner must be wine or proton")
    if sandbox_mode not in {"full", "strict"}:
        raise RuntimeError("sandbox_mode must be one of: full, strict")

    pfx = prefix_dir(name)
    pfx.mkdir(parents=True, exist_ok=True)

    cfg = {
        "name": name,
        "profile": profile,
        "runner": runner,
        "prefix": str(pfx),
        "last_exe": "",
        "sandbox": bool(sandbox),  # RUN sandbox toggle
        "sandbox_mode": sandbox_mode,  # full|strict
    }
    save_config(name, cfg)
    return cfg


def init_prefix(cfg: dict):
    pfx = Path(cfg["prefix"])
    env = _env_for(pfx)
    log = LOG_DIR / cfg["name"] / "install.log"

    print("[green]Initializing prefix...[/green]")
    _run(["wineboot", "-u"], env=env, log_path=log, sandbox=False)

    prof = PROFILES[cfg["profile"]]

    print("[green]Setting Windows version...[/green]")
    _run(["winetricks", "-q", prof["winver"]], env=env, log_path=log, sandbox=False)

    if prof["winetricks"]:
        print(f"[green]Installing deps:[/green] {', '.join(prof['winetricks'])}")
        _run(["winetricks", "-q", *prof["winetricks"]], env=env, log_path=log, sandbox=False)

    if prof["graphics"]:
        print(f"[green]Enabling graphics:[/green] {', '.join(prof['graphics'])}")
        _run(["winetricks", "-q", *prof["graphics"]], env=env, log_path=log, sandbox=False)


def _resolve_installer_path(installer_path: str) -> str:
    raw = str(Path(installer_path).expanduser())

    if any(ch in raw for ch in ["*", "?", "["]):
        matches = sorted(glob.glob(raw))
        if not matches:
            raise RuntimeError(f"No installer matched pattern: {raw}")
        raw = matches[0]

    p = Path(raw)
    installer = str(p.resolve())
    if not Path(installer).exists():
        raise RuntimeError(f"Installer file not found: {installer}")
    return installer


def install(
    cfg: dict,
    installer_path: str,
    portable: bool = False,
    sandbox_install: bool = False,
):
    pfx = Path(cfg["prefix"])
    env = _env_for(pfx)
    log = LOG_DIR / cfg["name"] / "install.log"

    installer = _resolve_installer_path(installer_path)

    if portable:
        appdir = APPS_DIR / cfg["name"]
        appdir.mkdir(parents=True, exist_ok=True)
        dst = appdir / Path(installer).name
        print(f"[green]Portable mode:[/green] copying {installer} -> {dst}")
        shutil.copy2(installer, dst)

        conv = subprocess.run(["winepath", "-w", str(dst)], env=env, capture_output=True, text=True)
        winpath = conv.stdout.strip() if conv.returncode == 0 else ""
        if winpath:
            cfg["last_exe"] = winpath
            save_config(cfg["name"], cfg)
        return

    print(f"[green]Running installer:[/green] {installer}")
    rc = _run(
        ["wine", installer],
        env=env,
        log_path=log,
        sandbox=sandbox_install,
        allow_downloads=True,
        sandbox_mode="full",  # installers are fragile; keep full if sandboxed
    )
    if rc != 0:
        raise RuntimeError(f"Installer failed ({rc}). See: {log}")


def _autodetect_exe(prefix: Path) -> str:
    r"""
    Try to find a reasonable GUI exe inside common install locations.
    Returns Windows path like C:\\Program Files\\App\\app.exe, else "".

    Filters out common Windows/system executables inside prefix.
    """
    drive_c = prefix / "drive_c"
    candidates: list[Path] = []

    scan_roots = [
        drive_c / "Program Files",
        drive_c / "Program Files (x86)",
    ]
    for root in scan_roots:
        if root.exists():
            candidates.extend(root.rglob("*.exe"))

    if not candidates:
        return ""

    skip_names = {
        "iexplore.exe",
        "wmplayer.exe",
        "notepad.exe",
        "wordpad.exe",
        "explorer.exe",
        "rundll32.exe",
        "regedit.exe",
        "taskmgr.exe",
        "mshta.exe",
        "cmd.exe",
        "powershell.exe",
        "conhost.exe",
        "winecfg.exe",
        "uninstaller.exe",
        "setup.exe",
    }

    skip_dir_tokens = [
        "Internet Explorer",
        "Windows Media Player",
        "Windows NT",
        "Common Files",
    ]

    filtered: list[Path] = []
    for p in candidates:
        if p.name.lower() in skip_names:
            continue
        p_str = str(p)
        if any(tok in p_str for tok in skip_dir_tokens):
            continue
        filtered.append(p)

    if not filtered:
        return ""

    prefer_names = {
        "7zfm.exe",
        "notepad++.exe",
        "launcher.exe",
        "start.exe",
        "app.exe",
    }

    def score(path: Path):
        name = path.name.lower()
        preferred = 0 if name in prefer_names else 1
        depth = len(path.parts)
        length = len(str(path))
        return (preferred, depth, length)

    best = sorted(filtered, key=score)[0]
    rel = best.relative_to(drive_c)
    return "C:\\" + str(rel).replace("/", "\\")


def open_installer(installer_path: str):
    installer = _resolve_installer_path(installer_path)
    name = Path(installer).stem.lower().replace(" ", "_")[:32]
    base = name
    i = 2
    while load_config(name):
        name = f"{base}_{i}"
        i += 1

    cfg = create_app(name, "general", "wine", sandbox=False, sandbox_mode="full")
    init_prefix(cfg)
    install(cfg, installer)

    from norun.shortcuts import create_desktop_shortcut
    p = create_desktop_shortcut(name)
    print(f"[green]Installed via Open.[/green] App: {name} Shortcut: {p}")


def uninstall_app(name: str):
    cfg = load_config(name)
    if not cfg:
        raise RuntimeError("App not found.")

    pfx = Path(cfg["prefix"])
    if pfx.exists():
        shutil.rmtree(pfx, ignore_errors=True)

    appdir = APPS_DIR / name
    if appdir.exists():
        shutil.rmtree(appdir, ignore_errors=True)

    ldir = LOG_DIR / name
    if ldir.exists():
        shutil.rmtree(ldir, ignore_errors=True)

    desktop = Path.home() / ".local/share/applications" / f"norun-{name}.desktop"
    if desktop.exists():
        desktop.unlink()

    print(f"[green]Uninstalled:[/green] {name}")


def run_app(name: str, exe: str | None = None):
    cfg = load_config(name)
    if not cfg:
        raise RuntimeError("App not found. Use: norun add ...")

    pfx = Path(cfg["prefix"])
    env = _env_for(pfx)
    log = LOG_DIR / name / "run.log"
    sandbox = bool(cfg.get("sandbox", False))
    sandbox_mode = str(cfg.get("sandbox_mode", "full"))

    target = exe or cfg.get("last_exe") or ""
    if not target:
        guessed = _autodetect_exe(pfx)
        if guessed:
            target = guessed
            cfg["last_exe"] = target
            save_config(name, cfg)
        else:
            raise RuntimeError(r'No EXE provided. Use: norun run <app> --exe "C:\\Path\\app.exe"')

    cli_names = {"7z.exe", "cmd.exe", "powershell.exe"}
    if Path(target).name.lower() not in cli_names:
        cfg["last_exe"] = target
        save_config(name, cfg)

    if cfg["runner"] == "wine":
        print(f"[cyan]Running with Wine:[/cyan] {target}")
        rc = _run(
            ["wine", target],
            env=env,
            log_path=log,
            sandbox=sandbox,
            allow_downloads=False,
            sandbox_mode=sandbox_mode,
        )
        if rc != 0:
            raise RuntimeError(f"Run failed ({rc}). See: {log}")
        return

    if not shutil.which("umu-run"):
        raise RuntimeError("umu-run not found. Install umu-launcher first.")

    unix_path = target
    if ":" in target and "\\" in target:
        conv = subprocess.run(["winepath", "-u", target], env=env, capture_output=True, text=True)
        if conv.returncode == 0 and conv.stdout.strip():
            unix_path = conv.stdout.strip()

    print(f"[cyan]Running with Proton (umu-run):[/cyan] {unix_path}")
    rc = _run(
        ["umu-run", unix_path],
        env=env,
        log_path=log,
        sandbox=sandbox,
        allow_downloads=False,
        sandbox_mode=sandbox_mode,
    )
    if rc != 0:
        raise RuntimeError(f"Run failed ({rc}). See: {log}")
