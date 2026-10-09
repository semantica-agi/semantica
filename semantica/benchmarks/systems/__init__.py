"""The systems under test and their registry.

Importing this package registers every adapter, but imports no vendor SDK —
each adapter defers its ``mem0``/``graphiti``/``cognee`` import to factory call
time, so listing systems works in a bare checkout.
"""

from . import external, lexical, semantica_memory  # noqa: F401,E402
from .base import (  # noqa: F401
    SYSTEMS,
    MemorySystem,
    SystemUnavailable,
    get_system,
    list_systems,
    register_system,
)
