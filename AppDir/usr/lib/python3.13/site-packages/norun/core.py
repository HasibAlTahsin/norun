from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import time
import glob
import re

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
from norun import vm


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
        "--dev-bind", "/dev", "/dev",
        "--ro-bind", "/", "/",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
    ]

    if Path("/dev/dri").exists():
        binds += ["--dev-bind", "/dev/dri", "/dev/dri"]

    xdg_rt = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_rt and Path(xdg_rt).exists():
        binds += ["--bind", xdg_rt, xdg_rt]

    if os.environ.get("DISPLAY"):
        if Path("/tmp/.X11-unix").exists():
            binds += ["--bind", "/tmp/.X11-unix", "/tmp/.X11-unix"]
        if Path("/tmp/.ICE-unix").exists():
            binds += ["--bind", "/tmp/.ICE-unix", "/tmp/.ICE-unix"]

    if mode == "full":
        binds += ["--bind", home, home]
        if allow_downloads and Path(downloads).exists():
            binds += ["--bind", downloads, downloads]
    else:
        if Path(norun_root).exists():
            binds += ["--bind", norun_root, norun_root]
        if allow_downloads and Path(downloads).exists():
            binds += ["--bind", downloads, downloads]

        xauth = os.environ.get("XAUTHORITY") or str(Path.home() / ".Xauthority")
        if xauth and Path(xauth).exists():
            binds += ["--ro-bind", xauth, xauth]

    if extra_binds:
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
    wait: bool = True,
) -> int:
    run_env = (env or os.environ.copy()).copy()

    if sandbox:
        if not shutil.which("bwrap"):
            raise RuntimeError(
                "Sandbox requested but bubblewrap (bwrap) not installed. "
                "Run: sudo apt install -y bubblewrap"
            )

        if cmd and not os.path.isabs(cmd[0]):
            resolved = shutil.which(cmd[0])
            if not resolved:
                raise RuntimeError(f"Command not found: {cmd[0]}")
            cmd = [resolved, *cmd[1:]]

        base = os.path.basename(cmd[0])
        if base in {"wine", "wine64"}:
            ws = shutil.which("wineserver")
            if ws:
                run_env["WINESERVER"] = ws

        cmd = _wrap_bwrap(
            cmd,
            mode=sandbox_mode,
            allow_downloads=allow_downloads,
            extra_binds=(vm.extra_binds_for_gui() + (extra_binds or [])),
        )

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
            f.write(f"\n\n$ {' '.join(cmd)}\n--- {time.ctime()} ---\n")
            p = subprocess.Popen(cmd, env=run_env, stdout=f, stderr=f)
            if wait:
                return p.wait()
            return 0

    if wait:
        return subprocess.call(cmd, env=run_env)

    subprocess.Popen(cmd, env=run_env)
    return 0


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
        "7z": bool(shutil.which("7z")),
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
        "sandbox": bool(sandbox),
        "sandbox_mode": sandbox_mode,
        "desktop": "",
        "desktop_name": "norun",
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


def install(cfg: dict, installer_path: str, portable: bool = False, sandbox_install: bool = False):
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
        sandbox_mode="full",
        wait=True,
    )
    if rc != 0:
        raise RuntimeError(f"Installer failed ({rc}). See: {log}")


def _autodetect_exe(prefix: Path) -> str:
    drive_c = prefix / "drive_c"
    candidates: list[Path] = []

    for root in (drive_c / "Program Files", drive_c / "Program Files (x86)"):
        if root.exists():
            candidates.extend(root.rglob("*.exe"))

    if not candidates:
        return ""

    skip_names = {
        "iexplore.exe", "wmplayer.exe", "notepad.exe", "wordpad.exe",
        "explorer.exe", "rundll32.exe", "regedit.exe", "taskmgr.exe",
        "mshta.exe", "cmd.exe", "powershell.exe", "conhost.exe",
        "winecfg.exe", "uninstaller.exe", "setup.exe",
    }

    filtered = [p for p in candidates if p.name.lower() not in skip_names]
    if not filtered:
        return ""

    prefer_names = {"7zfm.exe", "launcher.exe", "start.exe", "app.exe"}

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


def _parse_desktop_size(size: str) -> tuple[int, int]:
    m = re.match(r"^\s*(\d+)\s*x\s*(\d+)\s*$", size.lower())
    if not m:
        raise RuntimeError('Invalid --desktop size. Use like "1024x768".')
    w = int(m.group(1))
    h = int(m.group(2))
    if w < 200 or h < 200:
        raise RuntimeError("Desktop size too small.")
    return w, h


def run_app(
    name: str,
    exe: str | None = None,
    *,
    desktop: str | None = None,
    desktop_name: str = "norun",
    wait: bool = True,
    disable_dxvk: bool = False,
    disable_d3d: bool = False,
    set_default_desktop: bool = False,
    clear_default_desktop: bool = False,
):
    cfg = load_config(name)
    if not cfg:
        raise RuntimeError("App not found. Use: norun add ...")

    pfx = Path(cfg["prefix"])
    env = _env_for(pfx)
    log = LOG_DIR / name / "run.log"
    sandbox = bool(cfg.get("sandbox", False))
    sandbox_mode = str(cfg.get("sandbox_mode", "full"))

    if clear_default_desktop:
        cfg["desktop"] = ""
        save_config(name, cfg)

    if not desktop:
        saved = (cfg.get("desktop") or "").strip()
        if saved:
            desktop = saved
        desktop_name = str(cfg.get("desktop_name") or desktop_name)

    if not desktop and vm.is_wayland_session():
        desktop = vm.recommend_virtual_desktop()
        print(f"[yellow]Wayland detected -> auto virtual desktop enabled: {desktop}[/yellow]")

    if desktop and set_default_desktop:
        cfg["desktop"] = desktop
        cfg["desktop_name"] = desktop_name
        save_config(name, cfg)

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

    if disable_dxvk:
        env["WINEDLLOVERRIDES"] = "dxgi,d3d11,d3d10core=n"
    if disable_d3d:
        env["WINEDLLOVERRIDES"] = "dxgi,d3d11,d3d10core,d3d9=n"

    if cfg.get("runner") == "wine":
        if desktop:
            w, h = _parse_desktop_size(desktop)
            print(f"[cyan]Running with Wine desktop:[/cyan] {desktop_name} {w}x{h} -> {target}")
            rc = _run(
                ["wine", "explorer", f"/desktop={desktop_name},{w}x{h}", target],
                env=env,
                log_path=log,
                sandbox=sandbox,
                allow_downloads=False,
                sandbox_mode=sandbox_mode,
                wait=wait,
            )
        else:
            print(f"[cyan]Running with Wine:[/cyan] {target}")
            rc = _run(
                ["wine", target],
                env=env,
                log_path=log,
                sandbox=sandbox,
                allow_downloads=False,
                sandbox_mode=sandbox_mode,
                wait=wait,
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
        wait=wait,
    )
    if rc != 0:
        raise RuntimeError(f"Run failed ({rc}). See: {log}")

