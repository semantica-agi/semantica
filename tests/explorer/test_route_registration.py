"""Regression tests for Explorer route registration consistency."""

import importlib
import pkgutil
from collections import defaultdict

import pytest

pytest.importorskip("fastapi")

import semantica.explorer.routes as explorer_routes  # noqa: E402


def _iter_routers():
    for module_info in pkgutil.iter_modules(explorer_routes.__path__):
        module = importlib.import_module(
            f"{explorer_routes.__name__}.{module_info.name}"
        )
        router = getattr(module, "router", None)
        if router is not None:
            yield module_info.name, router


def test_explorer_routers_have_no_duplicate_method_path_routes():
    """Each (method, path) pair must be registered at most once.

    A duplicate GET/POST pair makes the later handler unreachable because
    Starlette resolves the first matching route. This happened for
    /api/ontology/alignments; see issue #2252.
    """
    seen = defaultdict(list)
    for module_name, router in _iter_routers():
        for route in router.routes:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None) or set()
            for method in methods:
                seen[(method, path)].append(f"{module_name}.{route.endpoint.__name__}")

    duplicates = {key: names for key, names in seen.items() if len(names) > 1}
    assert duplicates == {}, f"Duplicate (method, path) registrations: {duplicates}"


def test_explorer_openapi_operation_ids_are_unique():
    """OpenAPI must not expose duplicate operationIds for the same endpoint set."""
    from semantica.explorer.app import create_app

    schema = create_app().openapi()
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    duplicates = sorted(
        {
            operation_id
            for operation_id in operation_ids
            if operation_ids.count(operation_id) > 1
        }
    )
    assert duplicates == [], f"Duplicate OpenAPI operationIds: {duplicates}"


def test_alignment_collection_openapi_matches_ontology_alignment():
    """GET/POST /api/ontology/alignments must advertise the old response shape.

    The Explorer UI and the existing round-trip tests depend on
    OntologyAlignment (id, source_uri, confidence, provenance, ...), so the
    OpenAPI contract must not silently switch back to AlignmentResponse.
    """
    from semantica.explorer.app import create_app

    schema = create_app().openapi()
    operations = schema["paths"]["/api/ontology/alignments"]

    get_schema = operations["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert get_schema["type"] == "array"
    assert get_schema["items"]["$ref"].endswith("/OntologyAlignment")

    post_schema = operations["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert post_schema["$ref"].endswith("/OntologyAlignment")
