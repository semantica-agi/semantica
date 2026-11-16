"""Tests for examples/fibo-lei: passes as shipped, fails on a changed value."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("pyshacl")

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "fibo-lei"
RUN = EXAMPLE / "run.py"
RECORD = EXAMPLE / "records" / "HWUPKR0MPOU8FGXBT394.ttl"


def run_sample(*args):
    return subprocess.run(
        [sys.executable, str(RUN), *map(str, args)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_shipped_records_conform():
    result = run_sample()

    assert result.returncode == 0, result.stdout + result.stderr
    records = sorted((EXAMPLE / "records").glob("*.ttl"))
    assert len(records) >= 3
    for record in records:
        assert f"PASS  {record.stem}" in result.stdout
    assert "FAIL" not in result.stdout


@pytest.mark.parametrize(
    "old, new, expected",
    [
        # LEI format (ISO 17442): drop a check digit
        (
            'hasTag "HWUPKR0MPOU8FGXBT394"',
            'hasTag "HWUPKR0MPOU8FGXBT39"',
            "Relations/hasTag> which does not match the required pattern",
        ),
        # Legal name is mandatory
        (
            'fibo-fnd-rel-rel:hasLegalName "Apple Inc." ;',
            "",
            "missing required property <https://spec.edmcouncil.org/fibo/ontology/"
            "FND/Relations/Relations/hasLegalName>",
        ),
        # Jurisdiction must be an ISO 3166 code
        (
            'hasTag "US-CA"',
            'hasTag "California"',
            "jurisdiction-US-CA> has value 'California'",
        ),
        # Registration status must be a FIBO RegistrationStatus (ActiveStatus is
        # an entity status, not a registration status)
        (
            "fibo-fbc-fct-breg:IssuedStatus",
            "fibo-fbc-fct-breg:ActiveStatus",
            "BusinessRegistries/hasRegistrationStatus> but it must be an instance",
        ),
        # Every LEI needs its registry entry, where the status lives
        (
            "a fibo-fbc-fct-breg:LegalEntityIdentifierRegistryEntry ;",
            "a ex:SomethingElse ;",
            "LEI must be in exactly one LEI registry entry",
        ),
        # Without its LEIRegisteredEntity type the entity is no focus node for
        # the legal-name shape, so the record itself must be rejected
        (
            "a fibo-be-le-lei:LEIRegisteredEntity, cmns-org:LegalEntity ;",
            "a cmns-org:LegalEntity ;",
            "no LEIRegisteredEntity in record",
        ),
        # A status the record declares itself is not a FIBO status individual
        (
            "fibo-fbc-fct-breg:hasRegistrationStatus fibo-fbc-fct-breg:IssuedStatus .",
            "fibo-fbc-fct-breg:hasRegistrationStatus ex:MadeUpStatus .\n"
            "ex:MadeUpStatus a fibo-fbc-fct-breg:RegistrationStatus .",
            "BusinessRegistries/hasRegistrationStatus> which is not in the allowed set",
        ),
    ],
    ids=[
        "lei-format",
        "legal-name",
        "jurisdiction",
        "registration-status",
        "registry-entry",
        "entity-type",
        "invented-status",
    ],
)
def test_changed_constrained_value_fails(tmp_path, old, new, expected):
    text = RECORD.read_text(encoding="utf-8")
    assert old in text
    bad = tmp_path / RECORD.name
    bad.write_text(text.replace(old, new), encoding="utf-8")

    result = run_sample(bad)

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"FAIL  {bad.stem}" in result.stdout
    assert expected in result.stdout


def test_invalid_turtle_is_a_one_line_failure(tmp_path):
    bad = tmp_path / "broken.ttl"
    bad.write_text("ex:broken a .\n", encoding="utf-8")

    result = run_sample(bad)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL  broken  parse error:" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


def test_one_bad_record_fails_the_whole_run(tmp_path):
    text = RECORD.read_text(encoding="utf-8")
    bad = tmp_path / RECORD.name
    bad.write_text(text.replace('hasTag "US-CA"', 'hasTag "us-ca"'), encoding="utf-8")
    good = sorted((EXAMPLE / "records").glob("*.ttl"))

    result = run_sample(*good, bad)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("PASS") == len(good)
    assert result.stdout.count("FAIL") == 1


def test_empty_record_fails(tmp_path):
    empty = tmp_path / "empty.ttl"
    empty.write_text("", encoding="utf-8")

    result = run_sample(empty)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL  empty" in result.stdout
    assert "no LegalEntityIdentifier in record" in result.stdout
    assert "no LEIRegisteredEntity in record" in result.stdout


def test_missing_status_axiom_stops_derivation():
    spec = importlib.util.spec_from_file_location("fibo_lei_run", RUN)
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    graph = run.rdflib.Graph().parse(run.SLICE_PATH, format="turtle")
    entry = run.BREG.LegalEntityIdentifierRegistryEntry
    prop = run.BREG.hasRegistrationStatus
    # Use the bounds FROM_AXIOMS really asks for, so weakening that row fails here.
    (expects,) = [e for cls, p, e in run.FROM_AXIOMS if cls == entry and p == prop]
    assert "min" in expects
    bounds = run.constraint_from_axioms(graph, entry, prop, expects)
    assert bounds[:2] == (1, 1)

    # Drop the entry's own someValuesFrom axiom; the inherited max 1 remains.
    for r in list(graph.objects(entry, run.RDFS.subClassOf)):
        if graph.value(r, run.OWL.onProperty) == prop:
            graph.remove((entry, run.RDFS.subClassOf, r))

    with pytest.raises(ValueError, match="no axiom giving a min cardinality"):
        run.constraint_from_axioms(graph, entry, prop, expects)


def test_subclass_declared_in_the_slice_counts_but_not_one_in_the_record():
    spec = importlib.util.spec_from_file_location("fibo_lei_run", RUN)
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    slice_graph = run.rdflib.Graph().parse(run.SLICE_PATH, format="turtle")
    record = run.rdflib.Graph().parse(
        RUN.parent / "records" / "HWUPKR0MPOU8FGXBT394.ttl", format="turtle"
    )
    assert run.missing_types(record, slice_graph) == []

    sub = run.URIRef("https://example.org/test#SpecialEntity")
    for s in list(record.subjects(run.RDF.type, run.LEI.LEIRegisteredEntity)):
        record.remove((s, run.RDF.type, run.LEI.LEIRegisteredEntity))
        record.add((s, run.RDF.type, sub))
    # Declared only in the record: not accepted.
    record.add((sub, run.RDFS.subClassOf, run.LEI.LEIRegisteredEntity))
    assert run.missing_types(record, slice_graph) == [
        "no LEIRegisteredEntity in record"
    ]
    # Declared in the slice: accepted, as sh:targetClass would.
    slice_graph.add((sub, run.RDFS.subClassOf, run.LEI.LEIRegisteredEntity))
    assert run.missing_types(record, slice_graph) == []
