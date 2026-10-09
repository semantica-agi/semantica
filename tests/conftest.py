"""Shared pytest configuration for the whole test suite."""

import copy
import importlib
import sys

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
