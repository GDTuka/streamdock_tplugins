"""Run a user-defined sequence of shell commands fail-fast in a target cwd.

Each entry in `commands` is a shell command string (passed via shell=True so
pipes, redirects, and shell builtins work — Windows uses cmd.exe, POSIX uses
/bin/sh). The chain stops at the first non-zero return code; the failing
command's 1-based index is returned in `Result.failed_index` for UI feedback.

The runner never raises — failures (subprocess errors, timeouts, missing cwd,
empty list) are returned as a Result.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Callable, List, Optional

DEFAULT_TIMEOUT = 300

ERROR_EMPTY = "no commands configured"
ERROR_MISSING_CWD = "cwd does not exist"


@dataclass
class Result:
    ok: bool
    failed_index: Optional[int] = None  # 1-based index of failing command
    returncode: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    executed: int = 0  # how many commands were actually invoked


def run_commands(
    commands: List[str],
    cwd: str,
    timeout: int = DEFAULT_TIMEOUT,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Result:
    """Execute commands sequentially in cwd, fail-fast.

    Args:
        commands: ordered list of shell command strings.
        cwd: working directory for every command.
        timeout: per-command timeout in seconds.
        runner: subprocess.run-compatible callable, overridable for tests.

    Returns:
        Result. On full success: ok=True, failed_index=None, executed=len(commands).
        On failure: ok=False, failed_index=N (1-based), with stdout/stderr from
        the failing command and the chain stopped.
        On empty list or missing cwd: ok=False with descriptive error,
        executed=0, failed_index=None.
    """
    if not commands:
        return Result(ok=False, error=ERROR_EMPTY)

    if not cwd or not os.path.isdir(cwd):
        return Result(ok=False, error=ERROR_MISSING_CWD)

    for idx, cmd in enumerate(commands, start=1):
        if not isinstance(cmd, str) or not cmd.strip():
            return Result(
                ok=False,
                failed_index=idx,
                error=f"command {idx} is empty",
                executed=idx - 1,
            )
        try:
            proc = runner(
                cmd,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return Result(
                ok=False,
                failed_index=idx,
                error=f"timeout after {timeout}s",
                stdout=exc.stdout if isinstance(exc.stdout, str) else "",
                stderr=exc.stderr if isinstance(exc.stderr, str) else "",
                executed=idx,
            )
        except (FileNotFoundError, OSError) as exc:
            return Result(
                ok=False,
                failed_index=idx,
                error=f"failed to spawn shell: {exc}",
                executed=idx,
            )

        if proc.returncode != 0:
            return Result(
                ok=False,
                failed_index=idx,
                returncode=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                error=f"command {idx} exited with {proc.returncode}",
                executed=idx,
            )

    return Result(ok=True, executed=len(commands), returncode=0)
