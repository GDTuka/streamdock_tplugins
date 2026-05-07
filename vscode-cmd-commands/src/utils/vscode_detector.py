"""Detect the workspace path of the currently active VS Code window.

Strategy:
1. Foreground (priority): Win32 GetForegroundWindow → verify process name == Code.exe
   → parse window title for the folder name → cross-reference against the
   recent-workspaces list to obtain the absolute path.
2. Fallback: return the most recent entry from the recent-workspaces list,
   regardless of foreground.

If both fail, return None — caller surfaces the error to the user.
"""

from __future__ import annotations

import ctypes
import json
import os
import sqlite3
from typing import List, Optional
from urllib.parse import unquote, urlparse


_VSCODE_PROCESS_NAMES = {"code.exe"}
_TITLE_SUFFIX = "Visual Studio Code"


def _foreground_window_info() -> tuple[Optional[str], Optional[int]]:
    """Return (window_title, pid) of the foreground window, or (None, None)."""
    if os.name != "nt":
        return None, None
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return None, None

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None

    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return title, pid.value or None


def _is_vscode_process(pid: int) -> bool:
    try:
        import psutil  # local import: only needed when foreground check runs
    except ImportError:
        return False
    try:
        return psutil.Process(pid).name().lower() in _VSCODE_PROCESS_NAMES
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False


def _parse_folder_from_title(title: str) -> Optional[str]:
    """VS Code default title ends with ' - Visual Studio Code'.

    The folder name is the segment right before that suffix. Use rsplit with
    maxsplit=2 so folder names containing hyphens (e.g. 'fast-tausik-init')
    are preserved — only the two surrounding ' - ' delimiters are split.
    """
    if not title or not title.endswith(_TITLE_SUFFIX):
        return None
    parts = title.rsplit(" - ", 2)
    if len(parts) < 2:
        return None
    folder = parts[-2].strip()
    return folder or None


def _file_uri_to_path(uri: str) -> Optional[str]:
    try:
        parsed = urlparse(uri)
    except ValueError:
        return None
    if parsed.scheme != "file":
        return None
    path = unquote(parsed.path)
    if os.name == "nt" and path.startswith("/"):
        path = path[1:]
    return os.path.normpath(path) if path else None


def _read_vscdb(db_path: str) -> List[str]:
    if not os.path.isfile(db_path):
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            ("history.recentlyOpenedPathsList",),
        )
        row = cur.fetchone()
        conn.close()
    except sqlite3.DatabaseError:
        return []
    if not row:
        return []
    try:
        data = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return []
    result: List[str] = []
    for entry in data.get("entries", []):
        uri = entry.get("folderUri") if isinstance(entry, dict) else None
        if uri:
            p = _file_uri_to_path(uri)
            if p:
                result.append(p)
    return result


def _read_storage_json(json_path: str) -> List[str]:
    """Parse storage.json across VSCode versions.

    Modern VSCode (current) stores recent/open workspaces under
    `windowsState` (currently/most-recently open) and `backupWorkspaces`
    (history). Older versions used `openedPathsList`; both shapes are
    accepted, with modern keys taking precedence so that the lastActive
    window appears first in the result.
    """
    if not os.path.isfile(json_path):
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []

    result: List[str] = []
    seen: set = set()

    def _add(uri) -> None:
        if not isinstance(uri, str) or not uri:
            return
        p = _file_uri_to_path(uri)
        if p is None:
            p = os.path.normpath(uri)
        if p and p not in seen:
            seen.add(p)
            result.append(p)

    ws = data.get("windowsState")
    if isinstance(ws, dict):
        last_active = ws.get("lastActiveWindow")
        if isinstance(last_active, dict):
            _add(last_active.get("folder"))
        for win in ws.get("openedWindows") or []:
            if isinstance(win, dict):
                _add(win.get("folder"))

    bw = data.get("backupWorkspaces")
    if isinstance(bw, dict):
        for folder in bw.get("folders") or []:
            if isinstance(folder, dict):
                _add(folder.get("folderUri"))

    opened = data.get("openedPathsList")
    if isinstance(opened, dict):
        for key in ("workspaces3", "workspaces2", "workspaces"):
            for entry in opened.get(key) or []:
                if isinstance(entry, dict):
                    _add(entry.get("folderUri"))
                elif isinstance(entry, str):
                    _add(entry)

    return result


def _candidate_storage_paths(appdata: str) -> List[str]:
    code_dir = os.path.join(appdata, "Code")
    return [
        os.path.join(code_dir, "User", "globalStorage", "state.vscdb"),
        os.path.join(code_dir, "User", "globalStorage", "storage.json"),
        os.path.join(code_dir, "storage.json"),
    ]


def read_recent_workspaces(appdata: Optional[str] = None) -> List[str]:
    """Read the ordered list of recent VS Code workspace paths.

    Tries (1) state.vscdb, (2) globalStorage/storage.json, (3) Code/storage.json.
    Returns the first non-empty result.
    """
    appdata = appdata if appdata is not None else os.environ.get("APPDATA")
    if not appdata:
        return []
    for path in _candidate_storage_paths(appdata):
        entries = _read_vscdb(path) if path.endswith(".vscdb") else _read_storage_json(path)
        if entries:
            return entries
    return []


def detect_foreground_folder_name() -> Optional[str]:
    """Return the folder name of the focused VS Code window, or None."""
    title, pid = _foreground_window_info()
    if not pid or not title:
        return None
    if not _is_vscode_process(pid):
        return None
    return _parse_folder_from_title(title)


def detect_workspace(appdata: Optional[str] = None) -> Optional[str]:
    """Return the absolute path of the project currently open in VS Code.

    Args:
        appdata: Override for %APPDATA% (used by tests).

    Returns:
        Absolute folder path, or None if neither foreground nor storage
        provides a usable workspace.
    """
    fg_folder = detect_foreground_folder_name()
    paths = read_recent_workspaces(appdata=appdata)
    if fg_folder:
        for p in paths:
            if os.path.basename(p).lower() == fg_folder.lower():
                return p
        return None
    return paths[0] if paths else None
