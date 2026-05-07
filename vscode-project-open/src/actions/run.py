"""Run action — opens VS Code on a configured project path.

Wired to action UUID `com.vscode.open.run`. The class name is irrelevant
to the SDK loader — only the module name (`run`) must match the UUID's
last segment.

Settings shape:
    {
        "path": str,   # absolute folder path to open in VS Code
    }

Title is owned by StreamDock's standard key panel (UserTitleEnabled=true).
We restore self.title (cached by base Plugin from titleParametersDidChange)
after error overrides.
"""

from __future__ import annotations

import threading
from typing import Dict

from src.core.action import Action
from src.core.logger import Logger
from src.utils.vscode_opener import (
    ERROR_EMPTY,
    ERROR_MISSING_DIR,
    ERROR_NO_CODE,
    Result,
    open_project,
)

# Manifest States indices.
STATE_IDLE = 0
STATE_ERROR = 1


_ERROR_TITLE = {
    ERROR_EMPTY: "NO PATH",
    ERROR_MISSING_DIR: "NO DIR",
    ERROR_NO_CODE: "NO CODE",
}


class Run(Action):
    def __init__(self, action: str, context: str, settings: Dict, plugin):
        super().__init__(action, context, settings, plugin)
        self._busy = False
        self._lock = threading.Lock()
        Logger.info(f"[Run] init context={context}")

    def on_did_receive_settings(self, settings: dict):
        self.settings = settings or {}
        path = self.settings.get("path") or ""
        Logger.info(f"[Run] settings updated: path='{path}'")

    def on_key_up(self, payload: dict):
        with self._lock:
            if self._busy:
                Logger.info("[Run] ignoring press — already in flight")
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
        path = (self.settings or {}).get("path", "")

        result: Result = open_project(path)
        if result.ok:
            Logger.info(f"[Run] opened {path}")
            self.set_state(STATE_IDLE)
            # Restore the user-set title (cached from titleParametersDidChange).
            # Empty string falls back to manifest State[0].Title default.
            self.set_title(self.title or "")
            self.show_ok()
            return

        title = _ERROR_TITLE.get(result.error or "", "ERR")
        Logger.error(f"[Run] open failed: {result.error}")
        self._fail(title)

    def _fail(self, short_title: str):
        self.set_state(STATE_ERROR)
        self.set_title(short_title)
        self.show_alert()
