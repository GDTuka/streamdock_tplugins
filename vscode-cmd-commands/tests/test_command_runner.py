"""Tests for src.utils.command_runner."""

from __future__ import annotations

import subprocess
from typing import List

import pytest

from src.utils import command_runner as cr
from src.utils.command_runner import ERROR_EMPTY, ERROR_MISSING_CWD, Result


class FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class RecordingRunner:
    """Stand-in for subprocess.run — records calls and returns scripted procs."""

    def __init__(self, scripted=None):
        self.calls: List[dict] = []
        self._scripted = list(scripted) if scripted else []

    def __call__(self, cmd, cwd=None, shell=False, capture_output=False,
                 text=False, timeout=None):
        self.calls.append({
            "cmd": cmd,
            "cwd": cwd,
            "shell": shell,
            "capture_output": capture_output,
            "text": text,
            "timeout": timeout,
        })
        if self._scripted:
            outcome = self._scripted.pop(0)
        else:
            outcome = FakeProc()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.fixture
def cwd(tmp_path):
    return str(tmp_path)


# ---------- empty / cwd validation ----------


def test_empty_commands_returns_error_without_invoking_runner(cwd):
    runner = RecordingRunner()
    res = cr.run_commands([], cwd, runner=runner)
    assert isinstance(res, Result)
    assert not res.ok
    assert res.error == ERROR_EMPTY
    assert res.failed_index is None
    assert res.executed == 0
    assert runner.calls == []


def test_missing_cwd_returns_error(tmp_path):
    runner = RecordingRunner()
    missing = str(tmp_path / "does-not-exist")
    res = cr.run_commands(["echo hi"], missing, runner=runner)
    assert not res.ok
    assert res.error == ERROR_MISSING_CWD
    assert runner.calls == []


def test_blank_command_in_chain_returns_failed_index(cwd):
    runner = RecordingRunner()
    res = cr.run_commands(["echo first", "   ", "echo third"], cwd, runner=runner)
    assert not res.ok
    assert res.failed_index == 2
    # First command runs, blank is detected before subprocess invocation
    assert len(runner.calls) == 1
    assert runner.calls[0]["cmd"] == "echo first"


# ---------- happy path ----------


def test_successful_two_command_chain(cwd):
    runner = RecordingRunner(scripted=[FakeProc(stdout="a"), FakeProc(stdout="b")])
    res = cr.run_commands(["echo a", "echo b"], cwd, runner=runner)
    assert res.ok
    assert res.failed_index is None
    assert res.executed == 2
    assert res.returncode == 0
    assert len(runner.calls) == 2
    # Each call uses shell=True, the configured cwd, capture_output, text.
    for call in runner.calls:
        assert call["shell"] is True
        assert call["cwd"] == cwd
        assert call["capture_output"] is True
        assert call["text"] is True


def test_passes_timeout_to_subprocess(cwd):
    runner = RecordingRunner(scripted=[FakeProc()])
    cr.run_commands(["echo a"], cwd, timeout=42, runner=runner)
    assert runner.calls[0]["timeout"] == 42


# ---------- fail-fast ----------


def test_fail_on_first_command_stops_chain(cwd):
    runner = RecordingRunner(scripted=[FakeProc(returncode=1, stderr="boom")])
    res = cr.run_commands(["false", "echo never", "echo never2"], cwd, runner=runner)
    assert not res.ok
    assert res.failed_index == 1
    assert res.returncode == 1
    assert res.stderr == "boom"
    assert res.executed == 1
    assert len(runner.calls) == 1
    assert runner.calls[0]["cmd"] == "false"


def test_fail_on_second_command_skips_third(cwd):
    runner = RecordingRunner(scripted=[
        FakeProc(returncode=0, stdout="ok"),
        FakeProc(returncode=2, stderr="fail"),
        # third FakeProc would never be consumed
        FakeProc(returncode=0),
    ])
    res = cr.run_commands(
        ["echo a", "exit 2", "echo never"],
        cwd,
        runner=runner,
    )
    assert not res.ok
    assert res.failed_index == 2
    assert res.returncode == 2
    assert res.stderr == "fail"
    assert res.executed == 2
    # Only two subprocess invocations
    assert len(runner.calls) == 2
    assert runner.calls[0]["cmd"] == "echo a"
    assert runner.calls[1]["cmd"] == "exit 2"


# ---------- exception passthrough ----------


def test_timeout_during_command_returns_failed_index(cwd):
    timeout_exc = subprocess.TimeoutExpired(cmd="sleep 999", timeout=10)
    timeout_exc.stderr = "partial stderr"
    runner = RecordingRunner(scripted=[FakeProc(), timeout_exc, FakeProc()])
    res = cr.run_commands(["echo a", "sleep 999", "echo never"], cwd, runner=runner)
    assert not res.ok
    assert res.failed_index == 2
    assert "timeout" in (res.error or "").lower()
    assert res.stderr == "partial stderr"
    assert res.executed == 2
    assert len(runner.calls) == 2


def test_runner_raises_filenotfound_returns_result(cwd):
    runner = RecordingRunner(scripted=[FileNotFoundError("shell missing")])
    res = cr.run_commands(["echo hi"], cwd, runner=runner)
    assert isinstance(res, Result)
    assert not res.ok
    assert res.failed_index == 1
    assert "failed to spawn shell" in (res.error or "")


def test_runner_never_raises(cwd):
    """Even when subprocess raises a generic OSError, run_commands returns Result."""
    runner = RecordingRunner(scripted=[OSError("disk full")])
    res = cr.run_commands(["echo hi"], cwd, runner=runner)
    assert isinstance(res, Result)
    assert not res.ok
