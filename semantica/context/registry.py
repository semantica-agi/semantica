"""
Method Registry Module for Context Engineering.

Provides a method registry system for registering and dispatching custom
retrieval and context engineering methods.
"""

from typing import Any, Callable, Dict, List, Optional


class MethodRegistry:
    """Registry for custom context retrieval and engineering methods."""

    _methods: Dict[str, Dict[str, Callable]] = {
        "retrieval": {},
        "global_retrieval": {},
        "drift_search": {},
        "context": {},
    }
    _metadata: Dict[str, Dict[str, Dict[str, Any]]] = {
        "retrieval": {},
        "global_retrieval": {},
        "drift_search": {},
        "context": {},
    }
    _capabilities: Dict[str, Dict[str, List[str]]] = {
        "retrieval": {},
        "global_retrieval": {},
        "drift_search": {},
        "context": {},
    }

    @classmethod
    def register(
        cls,
        task: str,
        name: str,
        method_func: Callable,
        metadata: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[str]] = None,
    ) -> None:
        """Register a custom context method."""
        if task not in cls._methods:
            cls._methods[task] = {}
            cls._metadata[task] = {}
            cls._capabilities[task] = {}
        cls._methods[task][name] = method_func
        cls._metadata[task][name] = metadata or {}
        cls._capabilities[task][name] = capabilities or []

    @classmethod
    def get(cls, task: str, name: str) -> Optional[Callable]:
        """Get method function by task and name."""
        return cls._methods.get(task, {}).get(name)

    @classmethod
    def list_all(cls, task: Optional[str] = None) -> Dict[str, List[str]]:
        """List registered methods, optionally filtered by task."""
        if task is not None:
            return {task: list(cls._methods.get(task, {}).keys())}
        return {t: list(m.keys()) for t, m in cls._methods.items()}

    @classmethod
    def unregister(cls, task: str, name: str) -> bool:
        """Unregister a method by task and name."""
        if task in cls._methods and name in cls._methods[task]:
            del cls._methods[task][name]
            cls._metadata.get(task, {}).pop(name, None)
            cls._capabilities.get(task, {}).pop(name, None)
            return True
        return False

    @classmethod
    def get_metadata(
        cls, task: str, name: str
    ) -> Optional[Dict[str, Any]]:
        """Get metadata for a registered method."""
        return cls._metadata.get(task, {}).get(name)

    @classmethod
    def has_capability(
        cls, task: str, name: str, capability: str
    ) -> bool:
        """Check if a registered method advertises a specific capability."""
        caps = cls._capabilities.get(task, {}).get(name, [])
        return capability in caps


method_registry = MethodRegistry()
