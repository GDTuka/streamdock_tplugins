"""Tests for src.utils.vscode_detector."""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from src.utils import vscode_detector as vd


# ---------- title parsing ----------


@pytest.mark.parametrize(
    "title, expected",
    [
        ("file.py - my-project - Visual Studio Code", "my-project"),
        ("file.py - fast-tausik-init - Visual Studio Code", "fast-tausik-init"),
        ("file.py - my project - Visual Studio Code", "my project"),
        ("my-project - Visual Studio Code", "my-project"),
        ("Welcome - Visual Studio Code", "Welcome"),
        ("Visual Studio Code", None),
        ("Random text without suffix", None),
        ("", None),
    ],
)
def test_parse_folder_from_title(title, expected):
    assert vd._parse_folder_from_title(title) == expected


# ---------- file:// URI ----------


@pytest.mark.parametrize(
    "uri, on_nt, expected_suffix",
    [
        ("file:///c:/Users/foo/bar", True, os.path.normpath("c:/Users/foo/bar")),
        ("file:///d:/test%20dir", True, os.path.normpath("d:/test dir")),
        ("file:///home/user/proj", False, os.path.normpath("/home/user/proj")),
    ],
)
def test_file_uri_to_path(monkeypatch, uri, on_nt, expected_suffix):
    monkeypatch.setattr(vd.os, "name", "nt" if on_nt else "posix")
    assert vd._file_uri_to_path(uri) == expected_suffix


def test_file_uri_to_path_rejects_non_file_scheme():
    assert vd._file_uri_to_path("https://example.com/foo") is None
    assert vd._file_uri_to_path("not-a-uri") is None


# ---------- storage.json ----------


def _write_storage_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def test_read_storage_json_with_workspaces3(tmp_path):
    storage = tmp_path / "Code" / "User" / "globalStorage" / "storage.json"
    _write_storage_json(
        str(storage),
        {
            "openedPathsList": {
                "workspaces3": [
                    {"folderUri": "file:///d:/most-recent"},
                    {"folderUri": "file:///c:/older"},
                ]
            }
        },
    )
    paths = vd._read_storage_json(str(storage))
    assert len(paths) == 2
    assert paths[0].lower().endswith("most-recent")
    assert paths[1].lower().endswith("older")


def test_read_storage_json_missing_file_returns_empty(tmp_path):
    assert vd._read_storage_json(str(tmp_path / "missing.json")) == []


def test_read_storage_json_invalid_json_returns_empty(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json at all", encoding="utf-8")
    assert vd._read_storage_json(str(bad)) == []


def test_read_storage_json_modern_windows_state(tmp_path):
    """Current VSCode keeps open windows under windowsState — lastActiveWindow first."""
    storage = tmp_path / "Code" / "User" / "globalStorage" / "storage.json"
    _write_storage_json(
        str(storage),
        {
            "windowsState": {
                "lastActiveWindow": {
                    "folder": "file:///f%3A/Work/Tuka/programming_keyboard_utils"
                },
                "openedWindows": [
                    {"folder": "file:///f%3A/Work/other-project"},
                    {
                        "folder": "file:///f%3A/Work/Tuka/programming_keyboard_utils"
                    },
                ],
            }
        },
    )
    paths = vd._read_storage_json(str(storage))
    assert len(paths) == 2
    assert paths[0].lower().endswith("programming_keyboard_utils")
    assert paths[1].lower().endswith("other-project")


def test_read_storage_json_modern_backup_workspaces(tmp_path):
    """backupWorkspaces.folders is parsed when windowsState is absent."""
    storage = tmp_path / "Code" / "User" / "globalStorage" / "storage.json"
    _write_storage_json(
        str(storage),
        {
            "backupWorkspaces": {
                "folders": [
                    {"folderUri": "file:///d:/proj-a"},
                    {"folderUri": "file:///d:/proj-b"},
                ]
            }
        },
    )
    paths = vd._read_storage_json(str(storage))
    assert [os.path.basename(p).lower() for p in paths] == ["proj-a", "proj-b"]


def test_read_storage_json_modern_takes_precedence_over_legacy(tmp_path):
    storage = tmp_path / "Code" / "User" / "globalStorage" / "storage.json"
    _write_storage_json(
        str(storage),
        {
            "windowsState": {"lastActiveWindow": {"folder": "file:///d:/from-modern"}},
            "openedPathsList": {
                "workspaces3": [{"folderUri": "file:///d:/from-legacy"}]
            },
        },
    )
    paths = vd._read_storage_json(str(storage))
    assert paths[0].lower().endswith("from-modern")
    assert any(p.lower().endswith("from-legacy") for p in paths)


# ---------- state.vscdb ----------


def _write_vscdb(path: str, entries: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    payload = json.dumps({"entries": entries})
    conn.execute(
        "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
        ("history.recentlyOpenedPathsList", payload),
    )
    conn.commit()
    conn.close()


def test_read_vscdb_returns_ordered_paths(tmp_path):
    db = tmp_path / "Code" / "User" / "globalStorage" / "state.vscdb"
    _write_vscdb(
        str(db),
        [
            {"folderUri": "file:///d:/proj-a"},
            {"folderUri": "file:///c:/proj-b"},
        ],
    )
    paths = vd._read_vscdb(str(db))
    assert len(paths) == 2
    assert paths[0].lower().endswith("proj-a")


def test_read_vscdb_missing_file_returns_empty(tmp_path):
    assert vd._read_vscdb(str(tmp_path / "no.vscdb")) == []


# ---------- read_recent_workspaces chain ----------


def test_read_recent_workspaces_prefers_vscdb_over_json(tmp_path):
    db = tmp_path / "Code" / "User" / "globalStorage" / "state.vscdb"
    _write_vscdb(str(db), [{"folderUri": "file:///d:/from-vscdb"}])
    _write_storage_json(
        str(tmp_path / "Code" / "User" / "globalStorage" / "storage.json"),
        {"openedPathsList": {"workspaces3": [{"folderUri": "file:///d:/from-json"}]}},
    )
    paths = vd.read_recent_workspaces(appdata=str(tmp_path))
    assert len(paths) == 1
    assert paths[0].lower().endswith("from-vscdb")


def test_read_recent_workspaces_falls_back_to_storage_json(tmp_path):
    _write_storage_json(
        str(tmp_path / "Code" / "User" / "globalStorage" / "storage.json"),
        {"openedPathsList": {"workspaces3": [{"folderUri": "file:///d:/json-only"}]}},
    )
    paths = vd.read_recent_workspaces(appdata=str(tmp_path))
    assert len(paths) == 1
    assert paths[0].lower().endswith("json-only")


def test_read_recent_workspaces_empty_appdata_returns_empty(tmp_path):
    assert vd.read_recent_workspaces(appdata=str(tmp_path)) == []


def test_read_recent_workspaces_none_appdata_returns_empty(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    assert vd.read_recent_workspaces(appdata=None) == []


# ---------- detect_workspace ----------


def test_detect_workspace_foreground_match(tmp_path, monkeypatch):
    db = tmp_path / "Code" / "User" / "globalStorage" / "state.vscdb"
    _write_vscdb(
        str(db),
        [
            {"folderUri": "file:///d:/other"},
            {"folderUri": "file:///d:/fast-tausik-init"},
        ],
    )
    monkeypatch.setattr(vd, "detect_foreground_folder_name", lambda: "fast-tausik-init")
    result = vd.detect_workspace(appdata=str(tmp_path))
    assert result is not None
    assert result.lower().endswith("fast-tausik-init")


def test_detect_workspace_foreground_no_storage_match_returns_none(tmp_path, monkeypatch):
    db = tmp_path / "Code" / "User" / "globalStorage" / "state.vscdb"
    _write_vscdb(str(db), [{"folderUri": "file:///d:/unrelated"}])
    monkeypatch.setattr(vd, "detect_foreground_folder_name", lambda: "fast-tausik-init")
    assert vd.detect_workspace(appdata=str(tmp_path)) is None


def test_detect_workspace_no_foreground_returns_first(tmp_path, monkeypatch):
    db = tmp_path / "Code" / "User" / "globalStorage" / "state.vscdb"
    _write_vscdb(
        str(db),
        [
            {"folderUri": "file:///d:/most-recent"},
            {"folderUri": "file:///c:/older"},
        ],
    )
    monkeypatch.setattr(vd, "detect_foreground_folder_name", lambda: None)
    result = vd.detect_workspace(appdata=str(tmp_path))
    assert result is not None
    assert result.lower().endswith("most-recent")


def test_detect_workspace_nothing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(vd, "detect_foreground_folder_name", lambda: None)
    assert vd.detect_workspace(appdata=str(tmp_path)) is None
