"""Tests for src.utils.vscode_opener."""

from __future__ import annotations

from typing import List

import pytest

from src.utils import vscode_opener as vo
from src.utils.vscode_opener import (
    ERROR_EMPTY,
    ERROR_MISSING_DIR,
    ERROR_NO_CODE,
    Result,
)


class FakePopen:
    def __init__(self):
        self.calls: List[dict] = []

    def __call__(self, args, shell=False, stdout=None, stderr=None, close_fds=False):
        self.calls.append({
            "args": list(args),
            "shell": shell,
            "stdout": stdout,
            "stderr": stderr,
            "close_fds": close_fds,
        })
        return self  # placeholder Popen-like object


def _which_returns(path):
    """Return a finder that always reports the same path for any name."""
    def finder(name):
        return path
    return finder


def _which_none(_name):
    return None


# ---------- validation ----------


def test_empty_path_returns_error_without_spawning(tmp_path):
    popen = FakePopen()
    res = vo.open_project("", opener=popen, finder=_which_returns("/fake/code"))
    assert isinstance(res, Result)
    assert not res.ok
    assert res.error == ERROR_EMPTY
    assert popen.calls == []


def test_blank_path_returns_error(tmp_path):
    popen = FakePopen()
    res = vo.open_project("   ", opener=popen, finder=_which_returns("/fake/code"))
    assert not res.ok
    assert res.error == ERROR_EMPTY
    assert popen.calls == []


def test_missing_directory_returns_error(tmp_path):
    popen = FakePopen()
    missing = str(tmp_path / "does-not-exist")
    res = vo.open_project(missing, opener=popen, finder=_which_returns("/fake/code"))
    assert not res.ok
    assert res.error == ERROR_MISSING_DIR
    assert popen.calls == []


def test_path_is_file_not_dir_returns_error(tmp_path):
    popen = FakePopen()
    f = tmp_path / "a.txt"
    f.write_text("x")
    res = vo.open_project(str(f), opener=popen, finder=_which_returns("/fake/code"))
    assert not res.ok
    assert res.error == ERROR_MISSING_DIR
    assert popen.calls == []


def test_code_not_on_path_returns_error(tmp_path):
    popen = FakePopen()
    res = vo.open_project(str(tmp_path), opener=popen, finder=_which_none)
    assert not res.ok
    assert res.error == ERROR_NO_CODE
    assert popen.calls == []


# ---------- happy path ----------


def test_happy_path_spawns_code_with_path(tmp_path):
    popen = FakePopen()
    res = vo.open_project(str(tmp_path), opener=popen, finder=_which_returns("/fake/code"))
    assert res.ok
    assert res.error is None
    assert len(popen.calls) == 1
    call = popen.calls[0]
    assert call["args"][0] == "/fake/code"
    assert call["args"][1] == str(tmp_path)
    assert call["shell"] is False
    assert call["close_fds"] is True


def test_happy_path_falls_back_to_code_cmd(tmp_path):
    """`shutil.which("code")` returns None on Windows when only code.cmd exists."""
    popen = FakePopen()

    def finder(name):
        return "/fake/code.cmd" if name == "code.cmd" else None

    res = vo.open_project(str(tmp_path), opener=popen, finder=finder)
    assert res.ok
    assert popen.calls[0]["args"][0] == "/fake/code.cmd"


# ---------- exception passthrough ----------


def test_popen_raises_filenotfound_returns_result(tmp_path):
    def boom(*args, **kwargs):
        raise FileNotFoundError("no such program")

    res = vo.open_project(str(tmp_path), opener=boom, finder=_which_returns("/fake/code"))
    assert isinstance(res, Result)
    assert not res.ok
    assert "failed to spawn code" in (res.error or "")


def test_popen_raises_oserror_returns_result(tmp_path):
    def boom(*args, **kwargs):
        raise OSError("permission denied")

    res = vo.open_project(str(tmp_path), opener=boom, finder=_which_returns("/fake/code"))
    assert isinstance(res, Result)
    assert not res.ok


def test_opener_never_raises(tmp_path):
    def boom(*args, **kwargs):
        raise OSError("anything")

    # Should return Result, not raise
    res = vo.open_project(str(tmp_path), opener=boom, finder=_which_returns("/fake/code"))
    assert isinstance(res, Result)
