"""Regression tests for the standalone documentation checker."""

import runpy
import subprocess
import sys
from pathlib import Path


def test_mintlify_export_uses_utf8_lossy_capture(monkeypatch):
    """Mintlify output remains available regardless of the host code page.

    Verifies that:
    - subprocess.run is called with encoding="utf-8" and errors="replace"
    - The Windows EPERM noise filter fires correctly when output is captured
      (i.e. result.stdout is non-empty and "EPERM" reaches the filter)
    """
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

    # docs_check.py calls sys.exit(1) when any check fails.  If the EPERM
    # noise filter cannot see stdout (because it was None / lost), the
    # Mintlify check reports a failure and sys.exit(1) is raised here.
    runpy.run_path(
        str(Path(__file__).parents[1] / "docs_check.py"),
        run_name="__main__",
    )

    assert calls, "the Mintlify export check did not invoke subprocess.run"
    _, kwargs = calls[-1]
    assert kwargs["encoding"] == "utf-8", (
        "subprocess.run must use explicit UTF-8 encoding; "
        "without it the Windows locale codec silently discards Mintlify output"
    )
    assert kwargs["errors"] == "replace", (
        "errors='replace' is required so invalid bytes produce U+FFFD "
        "instead of raising UnicodeDecodeError and losing the entire stream"
    )


def test_utf8_bytes_survive_capture():
    """Bytes valid in UTF-8 but invalid in Windows cp1252 must not be lost.

    This is the minimal reproduction from issue #1578: the three bytes
    0xe2 0xa0 0x8f encode U+2800 (BRAILLE PATTERN BLANK) in UTF-8 but are
    not representable in cp1252.  Without encoding="utf-8" the subprocess
    reader thread raises UnicodeDecodeError and result.stdout becomes None,
    making combined == "" and the EPERM/EBUSY noise filter unreachable.
    """
    code = (
        "import sys; "
        "sys.stdout.buffer.write(bytes([0xe2, 0xa0, 0x8f])); "
        "sys.stdout.flush()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0
    assert result.stdout is not None, (
        "stdout must not be None; a UnicodeDecodeError in the reader thread "
        "would have discarded the entire captured stream"
    )
    # The three bytes decode to a single Unicode character (U+280F); with
    # errors="replace" any truly undecodable byte would become U+FFFD instead.
    # Either way the stream is preserved rather than lost — that is the fix.
    assert len(result.stdout.strip()) == 1, (
        "expected exactly one decoded character; "
        "an empty result means the stream was silently lost"
    )
