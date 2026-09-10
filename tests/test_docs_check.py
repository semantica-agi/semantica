"""Regression tests for the standalone documentation checker."""

import runpy
import subprocess
import sys
from pathlib import Path

def test_mintlify_export_uses_utf8_lossy_capture(monkeypatch):
    """Mintlify output remains available regardless of the host code page."""
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="cleanup EPERM",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "platform", "win32")

    runpy.run_path(
        str(Path(__file__).parents[1] / "docs_check.py"),
        run_name="__main__",
    )

    assert calls, "the Mintlify export check did not invoke subprocess.run"
    _, kwargs = calls[-1]
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
