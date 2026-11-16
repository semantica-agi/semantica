"""``--json`` output must be the only thing on stdout (#2150).

``setup_logging`` attached its console handler to ``sys.stdout``, so the log
records a command emits while it starts up (a ``ContextGraph`` logs on
construction, for one) came out ahead of the JSON document and ``json.loads``
on stdout failed. ``tests/test_cli_commands.py`` replaces ``setup_logging``
with a no-op for every test, so it cannot see this.
"""

import json
import logging
import subprocess
import sys

import pytest

from semantica.utils.logging import get_logger, setup_logging


@pytest.fixture
def restore_semantica_logger():
    """``setup_logging`` replaces the handlers of the shared ``semantica`` logger."""
    logger = logging.getLogger("semantica")
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


def test_json_command_prints_only_json_on_stdout(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(f"graph_db:\n  backend: memory\n  path: {tmp_path / 'graph.json'}\n")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from semantica.cli import main; main()",
            "--config",
            str(cfg),
            "decision",
            "list",
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def test_setup_logging_writes_records_to_stderr(capsys, restore_semantica_logger):
    setup_logging(level="INFO", file=None)

    logging.getLogger("semantica.test_json_stdout").info("CONSOLE_RECORD")

    captured = capsys.readouterr()
    assert "CONSOLE_RECORD" in captured.err
    assert "CONSOLE_RECORD" not in captured.out


def test_custom_format_handler_writes_records_to_stderr(capsys):
    logger = get_logger(
        "test_json_stdout_format", format="%(message)s", propagate=False
    )
    try:
        logger.warning("FORMATTED_RECORD")
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

    captured = capsys.readouterr()
    assert "FORMATTED_RECORD" in captured.err
    assert "FORMATTED_RECORD" not in captured.out
