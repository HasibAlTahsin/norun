from __future__ import annotations

import typer
from rich import print

from norun.core import (
    create_app,
    init_prefix,
    install,
    run_app,
    uninstall_app,
    list_apps,
    doctor,
    choose_runner,
    open_installer,
)

app = typer.Typer(help="NORUN - GUI+CLI Windows app runner (Wine + umu-run)")


@app.command()
def add(
    name: str = typer.Argument(..., help="App name"),
    installer: str = typer.Argument(..., help="Path to .exe/.msi"),
    profile: str = typer.Option("general", "--profile", "-p", help="Profile (general/games/...)"),
    runner: str = typer.Option("auto", "--runner", "-r", help="Runner: auto|wine|proton"),
    portable: bool = typer.Option(False, "--portable", help="Portable exe mode (copy exe into app dir)"),
    sandbox: bool = typer.Option(False, "--sandbox", help="Enable sandbox for RUN only (recommended)"),
    sandbox_mode: str = typer.Option("full", "--sandbox-mode", help="Sandbox mode for RUN: full|strict"),
    sandbox_install: bool = typer.Option(False, "--sandbox-install", help="Sandbox the INSTALLER too (may break installers)"),
):
    """
    Create app, init prefix, apply profile, run installer (or copy portable exe).
    """
    if runner == "auto":
        runner = choose_runner(profile, installer)

    cfg = create_app(name, profile, runner, sandbox=sandbox, sandbox_mode=sandbox_mode)
    init_prefix(cfg)
    install(cfg, installer, portable=portable, sandbox_install=sandbox_install)

    from norun.shortcuts import create_desktop_shortcut
    p = create_desktop_shortcut(name)
    print(
        f"[green]Installed.[/green] Runner={runner} Sandbox={sandbox} Mode={sandbox_mode} "
        f"Portable={portable} Shortcut: {p}"
    )


@app.command()
def run(
    name: str = typer.Argument(..., help="App name"),
    exe: str = typer.Option("", "--exe", help=r'Windows path like C:\Program Files\App\app.exe'),
):
    """Run installed app. If --exe is empty, uses last saved exe / autodetect."""
    run_app(name, exe if exe else None)


@app.command()
def open(
    installer: str = typer.Argument(..., help="Path to .exe/.msi"),
):
    """Open a .exe/.msi via NORUN (adds app if needed)."""
    open_installer(installer)


@app.command()
def uninstall(
    name: str = typer.Argument(..., help="App name"),
):
    """Uninstall app (remove prefix, logs, shortcut, config)."""
    uninstall_app(name)


@app.command("ls")
def _ls():
    """List apps."""
    for a in list_apps():
        print(a)


@app.command()
def diag():
    """Check required tools availability."""
    info = doctor()
    for k, v in info.items():
        print(f"{k}: {'OK' if v else 'MISSING'}")


@app.command()
def logs(
    name: str = typer.Argument(..., help="App name"),
):
    """Show logs paths (quick hint)."""
    from pathlib import Path
    from norun.config import LOG_DIR

    ldir = LOG_DIR / name
    print(f"[cyan]Logs dir:[/cyan] {ldir}")
    runlog = ldir / "run.log"
    instlog = ldir / "install.log"
    if runlog.exists():
        print(f"[green]Run log:[/green] {runlog}")
    if instlog.exists():
        print(f"[green]Install log:[/green] {instlog}")


@app.command()
def pick():
    """GUI list: pick an app and run."""
    from norun.gui import pick_and_run
    pick_and_run()


@app.command()
def gui():
    """Pure GUI flow (no typing add/run)."""
    from norun.gui import gui_flow
    gui_flow()


if __name__ == "__main__":
    app()
