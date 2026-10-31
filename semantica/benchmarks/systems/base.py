"""The memory-system abstraction and its registry.

To compare memory backends fairly, the harness talks to every system through
one tiny protocol instead of importing each vendor SDK directly:

    reset()  -> forget everything
    ingest(passages)  -> write evidence into memory
    answer(question)  -> read memory and produce a free-form answer

That is the whole surface. A system that can honour those three calls can be
benchmarked next to any other, and the runner never needs to know whether the
implementation is an in-process lexical index, semantica's own memory layer, or
a hosted graph service.

Systems are registered as **factories** (``() -> MemorySystem``) rather than
instances, so importing this package never imports an optional vendor SDK —
``mem0`` and friends are only touched when a run actually selects them.
"""

from typing import Callable, Dict, List, Protocol, Sequence, runtime_checkable


class SystemUnavailable(RuntimeError):
    """Raised when a registered system cannot run (missing dep or credential)."""


@runtime_checkable
class MemorySystem(Protocol):
    """Minimal contract every benchmarked memory backend implements."""

    name: str

    def reset(self) -> None:
        """Drop all remembered content so the next dataset starts clean."""

    def ingest(self, passages: Sequence[str], *, case_id: str = "") -> None:
        """Write ``passages`` into memory (``case_id`` is an optional hint)."""

    def answer(self, question: str, *, case_id: str = "") -> str:
        """Return a free-form answer to ``question`` from what is in memory."""


SYSTEMS: Dict[str, Callable[..., MemorySystem]] = {}


def register_system(name: str, factory: Callable[..., MemorySystem]) -> None:
    """Register a system factory under ``name``.

    A factory takes **options and returns a ready :class:`MemorySystem`. The
    runner passes its own options through, and each factory uses what it needs
    and ignores the rest — so new run options never require touching every
    adapter.
    """
    SYSTEMS[name] = factory


def list_systems() -> List[str]:
    """Registered system names, sorted."""
    return sorted(SYSTEMS)


def get_system(name: str, **options) -> MemorySystem:
    """Instantiate a registered system, or raise ``SystemUnavailable``.

    Unknown names and unavailable optional dependencies both surface as
    ``SystemUnavailable`` with an actionable message, so a caller can skip a
    system instead of crashing a whole benchmark run.
    """
    if name not in SYSTEMS:
        raise SystemUnavailable(
            f"unknown system {name!r}. Registered: {list_systems()}"
        )
    try:
        return SYSTEMS[name](**options)
    except SystemUnavailable:
        raise
    except ImportError as exc:
        raise SystemUnavailable(
            f"system {name!r} is registered but its backend is not installed: {exc}"
        ) from exc
