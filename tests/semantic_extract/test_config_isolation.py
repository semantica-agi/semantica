"""The process-wide semantic_extract config does not carry state between tests.

The tests in this file run in order: each odd one leaves something behind the
way a careless test would, and the next one checks it is gone (see #1913).
"""

import sys
from unittest.mock import MagicMock

import pytest

from semantica.semantic_extract.config import config


def test_leaves_a_double_in_the_config():
    config.set_provider("openai", api_key=MagicMock())
    assert isinstance(config.get_api_key("openai"), MagicMock)


def test_does_not_see_the_double_left_by_the_previous_test():
    assert not isinstance(config.get_api_key("openai"), MagicMock)


@pytest.fixture(scope="module")
def nested_setting():
    config.set_provider("isolation_test", options={"model": "original"})
    yield
    config._configs.pop("isolation_test", None)


def test_changes_a_nested_setting(nested_setting):
    config.get_provider_config("isolation_test")["options"]["model"] = "changed"


def test_does_not_see_the_nested_setting_changed_by_the_previous_test(
    nested_setting,
):
    options = config.get_provider_config("isolation_test")["options"]
    assert options["model"] == "original"


def test_leaves_a_stand_in_config_module_in_sys_modules():
    sys.modules["semantica.semantic_extract.config"] = MagicMock()


def test_does_not_see_the_stand_in_config_module():
    assert not isinstance(sys.modules["semantica.semantic_extract.config"], MagicMock)
