# norun/desktop.py
from __future__ import annotations

import re
from dataclasses import dataclass

_DESKTOP_RE = re.compile(r"^(?P<w>\d+)x(?P<h>\d+)$")


@dataclass(frozen=True)
class DesktopSpec:
    width: int
    height: int
    name: str = "norun"

    def to_wine_arg(self) -> str:
        # explorer /desktop=<name>,<WxH>
        return f"/desktop={self.name},{self.width}x{self.height}"


def parse_desktop(spec: str | None, *, name: str = "norun") -> DesktopSpec | None:
    if not spec:
        return None
    m = _DESKTOP_RE.match(spec.strip())
    if not m:
        raise ValueError("Invalid --desktop. Use like: 1024x768")
    w = int(m.group("w"))
    h = int(m.group("h"))
    if w < 320 or h < 200:
        raise ValueError("Desktop size too small. Use something like 800x600 or higher.")
    return DesktopSpec(width=w, height=h, name=name)

