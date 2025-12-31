from pathlib import Path
import re

COMMON_HINTS = [
    (re.compile(r"mscoree|dotnet", re.I), "Hint: .NET needed → try profile=dotnet"),
    (re.compile(r"vcrun|msvcp|vcruntime", re.I), "Hint: VC++ runtime missing → try vcrun2019"),
    (re.compile(r"d3d|dxgi|vulkan", re.I), "Hint: graphics issue → try runner=proton (umu-run)"),
    (re.compile(r"anti.?cheat|easy anti-cheat|battleye", re.I), "Hint: anti-cheat detected → often needs native Windows"),
]

def summarize_log(log_path: Path) -> str:
    if not log_path.exists():
        return "No log file found."
    text = log_path.read_text(errors="ignore")
    tail = "\n".join(text.splitlines()[-200:])

    hints = []
    for rx, msg in COMMON_HINTS:
        if rx.search(tail):
            hints.append(msg)

    out = []
    out.append("---- last 200 log lines ----")
    out.append(tail)
    if hints:
        out.append("\n---- hints ----")
        for h in sorted(set(hints)):
            out.append(f"- {h}")
    return "\n".join(out)
