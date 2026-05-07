"""Run action — executes a user-defined shell-command chain in the
VS Code workspace currently in focus.

Wired to action UUID `com.vscode.cmd.run`. The class name is irrelevant to
the SDK loader — only the module name (`run`) must match the UUID's last
segment.

Settings shape:
    {
        "commands": List[str],  # ordered shell commands run fail-fast
    }

The button's title is owned by StreamDock's standard key panel
(UserTitleEnabled=true in manifest.json). We cache the user-set value via
self.title (populated by titleParametersDidChange in the base Plugin) and
restore it after busy/error overrides.
"""

from __future__ import annotations

import threading
from typing import Dict

from src.core.action import Action
from src.core.logger import Logger
from src.utils.command_runner import Result, run_commands
from src.utils.vscode_detector import detect_workspace

# Manifest States indices.
STATE_IDLE = 0
STATE_BUSY = 1
STATE_ERROR = 2


class Run(Action):
    def __init__(self, action: str, context: str, settings: Dict, plugin):
        super().__init__(action, context, settings, plugin)
        self._busy = False
        self._lock = threading.Lock()
        Logger.info(f"[Run] init context={context}")

    def on_did_receive_settings(self, settings: dict):
        self.settings = settings or {}
        commands = self.settings.get("commands") or []
        Logger.info(f"[Run] settings updated: commands={len(commands)}")

    def on_key_up(self, payload: dict):
        with self._lock:
            if self._busy:
                Logger.info("[Run] ignoring press — task already running")
                return
            self._busy = True

        thread = threading.Thread(target=self._execute, daemon=True)
        thread.start()

    def _execute(self):
        try:
            self._run_pipeline()
        except Exception as exc:
            Logger.error(f"[Run] unexpected error: {exc}")
            self._fail("CRASH")
        finally:
            with self._lock:
                self._busy = False

    def _run_pipeline(self):
        settings = self.settings or {}
        commands = settings.get("commands") or []

        if not commands:
            Logger.error("[Run] commands list is empty — configure in property inspector")
            self._fail("NO CMD")
            return

        self.set_state(STATE_BUSY)
        self.set_title("...")

        workspace = detect_workspace()
        if not workspace:
            Logger.error("[Run] No VS Code workspace detected")
            self._fail("NO VSC")
            return
        Logger.info(f"[Run] workspace={workspace}, commands={len(commands)}")

        result: Result = run_commands(commands, cwd=workspace)
        if result.ok:
            Logger.info(f"[Run] success: {result.executed} commands on {workspace}")
            self.set_state(STATE_IDLE)
            # Restore the user-set title (cached by base Plugin from
            # titleParametersDidChange). Empty string falls back to manifest
            # State[0].Title default.
            self.set_title(self.title or "")
            self.show_ok()
            return

        idx = result.failed_index or 0
        Logger.error(
            f"[Run] failed at command #{idx}: {result.error}\nstderr: {result.stderr}"
        )
        self._fail(f"ERR {idx}" if idx else "ERR")

    def _fail(self, short_title: str):
        self.set_state(STATE_ERROR)
        self.set_title(short_title)
        self.show_alert()
