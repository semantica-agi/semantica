from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_core_extractors_import_from_package() -> None:
    from semantica.semantic_extract import (
        NERExtractor,
        RelationExtractor,
        TripletExtractor,
    )

    assert NERExtractor.__name__ == "NERExtractor"
    assert RelationExtractor.__name__ == "RelationExtractor"
    assert TripletExtractor.__name__ == "TripletExtractor"


def test_triple_extractor_alias_imports() -> None:
    from semantica.semantic_extract import TripleExtractor, TripletExtractor

    assert TripleExtractor is TripletExtractor


def test_method_dispatchers_import_without_extractor_cycle() -> None:
    from semantica.semantic_extract.methods import (
        get_entity_method,
        get_relation_method,
        get_triplet_method,
    )

    assert callable(get_entity_method("pattern"))
    assert callable(get_relation_method("pattern"))
    assert callable(get_triplet_method("pattern"))


def test_ml_is_a_registered_triplet_method() -> None:
    """#1789 (Qodo) — 'ml' must resolve to a real triplet method.

    The CLI defaults to ``--method ml`` across every mode, so the triplet
    registry has to know that name. Otherwise the extractor swallows the
    resulting ValueError and the requested method is silently ignored.
    """
    from semantica.semantic_extract.methods import (
        extract_triplets_ml,
        get_triplet_method,
    )

    assert get_triplet_method("ml") is extract_triplets_ml


def test_ml_triplets_convert_supplied_relations() -> None:
    """The ml triplet path must emit real triplets, not degrade silently."""
    from semantica.semantic_extract.methods import extract_triplets_ml
    from semantica.semantic_extract.types import Entity, Relation

    alice = Entity(text="Alice", label="PER", start_char=0, end_char=5)
    acme = Entity(text="Acme", label="ORG", start_char=15, end_char=19)
    relation = Relation(
        subject=alice, predicate="works_at", object=acme, confidence=0.9
    )

    triplets = extract_triplets_ml(
        "Alice works at Acme", entities=[alice, acme], relations=[relation]
    )

    assert len(triplets) == 1
    assert (
        triplets[0].subject,
        triplets[0].predicate,
        triplets[0].object,
    ) == ("Alice", "works_at", "Acme")
    assert triplets[0].metadata["extraction_method"] == "ml"


def test_import_order_methods_before_extractors() -> None:
    result = _run_python(
        """
from semantica.semantic_extract.methods import get_entity_method
from semantica.semantic_extract import NERExtractor, RelationExtractor, TripletExtractor
print(get_entity_method("pattern").__name__, NERExtractor.__name__, RelationExtractor.__name__, TripletExtractor.__name__)
"""
    )

    assert result.returncode == 0, result.stderr
    assert "extract_entities_pattern NERExtractor RelationExtractor TripletExtractor" in result.stdout


def test_import_order_extractors_before_methods() -> None:
    result = _run_python(
        """
from semantica.semantic_extract import NERExtractor, RelationExtractor, TripletExtractor
from semantica.semantic_extract.methods import get_entity_method
print(NERExtractor.__name__, RelationExtractor.__name__, TripletExtractor.__name__, get_entity_method("pattern").__name__)
"""
    )

    assert result.returncode == 0, result.stderr
    assert "NERExtractor RelationExtractor TripletExtractor extract_entities_pattern" in result.stdout


def test_legacy_type_imports_still_work() -> None:
    from semantica.semantic_extract.ner_extractor import Entity
    from semantica.semantic_extract.relation_extractor import Relation
    from semantica.semantic_extract.triplet_extractor import Triplet
    from semantica.semantic_extract.types import (
        Entity as SharedEntity,
        Relation as SharedRelation,
        Triplet as SharedTriplet,
    )

    assert Entity is SharedEntity
    assert Relation is SharedRelation
    assert Triplet is SharedTriplet


def test_core_package_imports_do_not_require_yaml() -> None:
    result = _run_python(
        """
import importlib.abc
import sys


class OptionalDependencyBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'")
        return None


sys.meta_path.insert(0, OptionalDependencyBlocker())

from semantica.semantic_extract import NERExtractor, RelationExtractor, TripletExtractor
print(NERExtractor.__name__, RelationExtractor.__name__, TripletExtractor.__name__)
"""
    )

    assert result.returncode == 0, result.stderr
    assert "NERExtractor RelationExtractor TripletExtractor" in result.stdout
