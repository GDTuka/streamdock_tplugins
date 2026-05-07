"""Open a folder in VS Code by spawning the `code` CLI non-blocking.

VS Code's CLI is idempotent: invoking `code <path>` on a folder that is
already open in some window simply focuses that window instead of opening
a duplicate.

The opener never raises — failures (missing path, missing dir, missing
`code` on PATH, spawn errors) are returned as a Result.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

ERROR_EMPTY = "path is empty"
ERROR_MISSING_DIR = "path does not exist or is not a directory"
ERROR_NO_CODE = "code executable not found on PATH"


@dataclass
class Result:
    ok: bool
    error: Optional[str] = None


def open_project(
    path: str,
    opener: Callable[..., subprocess.Popen] = subprocess.Popen,
    finder: Callable[[str], Optional[str]] = shutil.which,
) -> Result:
    """Open `path` in VS Code via the `code` CLI.

    Args:
        path: absolute folder path to open.
        opener: subprocess.Popen-compatible callable (overridable for tests).
        finder: shutil.which-compatible callable (overridable for tests).

    Returns:
        Result. ok=True after the spawn returns (non-blocking — VS Code
        keeps running in its own process). ok=False with descriptive error
        for empty path, missing directory, missing `code` executable, or
        spawn failure (FileNotFoundError, OSError).
    """
    if not path or not path.strip():
        return Result(ok=False, error=ERROR_EMPTY)

    if not os.path.isdir(path):
        return Result(ok=False, error=ERROR_MISSING_DIR)

    code = finder("code") or finder("code.cmd") or finder("code.exe")
    if not code:
        return Result(ok=False, error=ERROR_NO_CODE)

    try:
        opener(
            [code, path],
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except (FileNotFoundError, OSError) as exc:
        return Result(ok=False, error=f"failed to spawn code: {exc}")

    return Result(ok=True)
