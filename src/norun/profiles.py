from __future__ import annotations

PROFILES: dict[str, dict] = {
    "general": {
        "winver": "win10",
        "winetricks": ["corefonts", "vcrun2019"],
        # Safer default: don't force DXVK for general apps
        "graphics": [],
    },
    "dotnet": {
        "winver": "win10",
        "winetricks": ["corefonts", "vcrun2019"],
        "graphics": [],
    },
    "games": {
        "winver": "win10",
        "winetricks": ["corefonts", "vcrun2019"],
        "graphics": ["dxvk", "vkd3d"],
    },
}

