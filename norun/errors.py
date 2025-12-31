# norun/errors.py
from __future__ import annotations

import sys
from dataclasses import dataclass


class ExitCode:
    OK = 0
    USAGE = 2           # bad cli usage / unknown app
    NOT_FOUND = 3       # exe/prefix missing
    LAUNCH_FAILED = 10  # subprocess failed to start


@dataclass
class NorunError(Exception):
    message: str
    code: int = ExitCode.USAGE


def die(msg: str, code: int = ExitCode.USAGE) -> "NoReturn":  # type: ignore[name-defined]
    print(msg, file=sys.stderr)
    raise SystemExit(code)

