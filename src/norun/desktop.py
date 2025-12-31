from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DesktopSpec:
    name: str = "norun"
    width: int = 1024
    height: int = 768

    @staticmethod
    def parse(size: str, *, name: str = "norun") -> "DesktopSpec":
        m = re.match(r"^\s*(\d+)\s*x\s*(\d+)\s*$", size.lower())
        if not m:
            raise ValueError('Invalid desktop size. Use like "1024x768".')
        w = int(m.group(1))
        h = int(m.group(2))
        if w < 200 or h < 200:
            raise ValueError("Desktop size too small.")
        return DesktopSpec(name=name, width=w, height=h)

    def to_wine_arg(self) -> str:
        return f"/desktop={self.name},{self.width}x{self.height}"

