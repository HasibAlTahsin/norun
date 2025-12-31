from pathlib import Path
import subprocess

def create_desktop_shortcut(app_name: str) -> Path:
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)

    p = apps / f"norun-{app_name}.desktop"
    p.write_text(f"""[Desktop Entry]
Type=Application
Name={app_name} (NORUN)
Exec=norun run "{app_name}"
Terminal=false
Categories=Utility;
""")
    subprocess.run(["update-desktop-database", str(apps)], check=False)
    return p
