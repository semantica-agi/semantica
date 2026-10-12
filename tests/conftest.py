"""
Suite-wide pytest configuration.

``.github/full-suite-known-failures.txt`` records the tests that already fail on
an unmodified checkout. Rather than deselecting them, the hook below marks the
listed ids ``xfail``: they keep running, and one that starts passing reports
XPASS — which, under a strict marker, fails the run and so forces its line out
of the file.

The list only holds against the pinned ``requirements-ci.txt`` tree it was
measured on. A developer machine has a different environment, so entries here
can pass there, and a strict marker would turn each of those passes into a
failure of an ordinary local run. The marker is therefore strict only when
``CI`` is set to a true value (``1``/``true``/``yes``; GitHub Actions sets
``CI=true`` for every job) and non-strict everywhere else: locally a listed entry still runs and is still xfailed, but a
pass is reported as XPASS without failing the run.

The ``Run the full test suite`` step in ``.github/workflows/ci.yml`` deselects
the entries it must — the ones marked ``# windows-only``, on Windows alone — so
those never reach this hook. The hook leaves a ``# windows-only`` entry out on
Linux, where it runs and gates. (For the symlink-rejection test that is the only
platform where the rejection is exercised at all.) The ``# non-strict`` marker keeps an
entry non-strict even in CI, for an entry that genuinely varies with run order
or timing; every other listed entry is strict in CI.

The autouse fixture below isolates the process-wide ``semantic_extract`` config
between tests: a double left there by one test otherwise makes every later
provider test see an API key that is not set, which is why the 24 ``test_llm_*``
ids used to fail in a full-suite run (#1913).
"""
from __future__ import annotations

import copy
import importlib
import os
import re
import sys
from pathlib import Path

import pytest

# Imported once, before any test module is collected, so the fixture below always
# has the real module to put back.
_CONFIG_MODULE_NAME = "semantica.semantic_extract.config"
_config_module = importlib.import_module(_CONFIG_MODULE_NAME)


@pytest.fixture(autouse=True)
def _isolate_semantic_extract_config():
    """Undo what a test leaves in the process-wide semantic_extract config.

    Providers read their API key from this config before the environment, so a
    double left there by one test (or a stand-in module left in sys.modules)
    makes every later provider test see a key that is not set.
    """
    configs = _config_module.config._configs
    saved = copy.deepcopy(configs)
    yield
    configs.clear()
    configs.update(saved)
    sys.modules[_CONFIG_MODULE_NAME] = _config_module


_KNOWN_FAILURES = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "full-suite-known-failures.txt"
)

_WINDOWS_ONLY = "# windows-only"
_NON_STRICT = "# non-strict"
_HEADING = re.compile(r"^#\s*-{3,}\s+(?P<title>\S.*?)\s*-*\s*$")
_DEFAULT_REASON = "listed in .github/full-suite-known-failures.txt"


def _listed_ids() -> dict[str, tuple[str, bool]]:
    """Return the ids to xfail, each mapped to its heading and strictness."""
    if not _KNOWN_FAILURES.is_file():
        return {}
    listed: dict[str, tuple[str, bool]] = {}
    reason = _DEFAULT_REASON
    for raw in _KNOWN_FAILURES.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            heading = _HEADING.match(line)
            if heading:
                reason = heading.group("title")
            continue
        if _WINDOWS_ONLY in line and sys.platform != "win32":
            continue
        node = line.split("#", 1)[0].strip()
        listed[node] = (reason, _NON_STRICT not in line)
    return listed


def pytest_collection_modifyitems(config, items):
    listed = _listed_ids()
    if not listed:
        return
    in_ci = os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}
    for item in items:
        entry = listed.get(item.nodeid)
        if entry is None:
            continue
        reason, strict_ok = entry
        item.add_marker(pytest.mark.xfail(reason=reason, strict=in_ci and strict_ok))
