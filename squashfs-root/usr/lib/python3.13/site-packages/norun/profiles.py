PROFILES = {
    "general": {
        "winver": "win10",
        "winetricks": ["corefonts", "vcrun2019"],
        "graphics": ["dxvk", "vkd3d"],
    },
    "dotnet": {
        "winver": "win10",
        "winetricks": ["corefonts", "vcrun2019", "dotnet48"],
        "graphics": ["dxvk", "vkd3d"],
    },
    "games": {
        "winver": "win10",
        "winetricks": ["corefonts"],
        "graphics": ["dxvk", "vkd3d"],
    },
}
