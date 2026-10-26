"""The EPCIS sample runs from a clean checkout and refuses a broken event set (issue #2023).

One test runs the sample the way the README says to -- a command and an exit
code, which is the sample's own definition of done. The rest call ``main()``
directly: importing semantica costs more than running the sample does, and
paying that once per test would make a small sample expensive to keep honest.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "epcis" / "walk_chain.py"
EVENTS = REPO_ROOT / "examples" / "epcis" / "events.json"
BROKEN_EVENTS = REPO_ROOT / "examples" / "epcis" / "events_missing_parent.json"

EPC = "urn:epc:id:sgtin:0614141.107346.2026"
SECOND_EPC = "urn:epc:id:sgtin:0614141.107346.2027"
PASSPORT_NS = "https://semantica.dev/examples/epcis/passport#"
HAS_EVENT = URIRef(PASSPORT_NS + "hasEvent")
FOLLOWED_BY = URIRef(PASSPORT_NS + "followedBy")

CHAIN = [
    "urn:uuid:5f0f4a3e-0001-4a3e-9b1a-0000000000a1",
    "urn:uuid:5f0f4a3e-0002-4a3e-9b1a-0000000000a2",
    "urn:uuid:5f0f4a3e-0003-4a3e-9b1a-0000000000a3",
    "urn:uuid:5f0f4a3e-0004-4a3e-9b1a-0000000000a4",
    "urn:uuid:5f0f4a3e-0005-4a3e-9b1a-0000000000a5",
]


@pytest.fixture(scope="module")
def sample():
    """The example module, loaded from its path: ``examples/`` is not a package."""
    spec = importlib.util.spec_from_file_location("epcis_walk_chain", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_one_command_writes_the_passport_and_exits_zero(tmp_path):
    result = subprocess.run(
        [sys.executable, str(EXAMPLE), "--out", str(tmp_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, result.stderr
    assert f"Product passport for {EPC}" in result.stdout

    written = list(tmp_path.glob("*.ttl"))
    assert len(written) == 1

    graph = Graph()
    graph.parse(written[0], format="turtle")

    product = URIRef(EPC)
    assert [str(event) for event in graph.objects(product, HAS_EVENT)] == CHAIN
    for previous, following in zip(CHAIN, CHAIN[1:]):
        assert (URIRef(previous), FOLLOWED_BY, URIRef(following)) in graph

    # The event classes and the business step are the GS1 ones, not the sample's.
    assert (
        URIRef(CHAIN[0]),
        RDF.type,
        URIRef("https://ref.gs1.org/epcis/ObjectEvent"),
    ) in graph
    assert (
        URIRef(CHAIN[1]),
        RDF.type,
        URIRef("https://ref.gs1.org/epcis/AggregationEvent"),
    ) in graph
    steps = {
        str(value)
        for value in graph.objects(URIRef(CHAIN[0]), URIRef(PASSPORT_NS + "bizStep"))
    }
    assert steps == {"https://ref.gs1.org/cbv/BizStep-commissioning"}


def test_the_product_can_be_chosen(sample, tmp_path, capsys):
    code = sample.main(["--epc", SECOND_EPC, "--out", str(tmp_path)])

    assert code == 0
    assert f"Product passport for {SECOND_EPC}" in capsys.readouterr().out


def test_a_missing_parent_is_reported_not_raised(sample, capsys):
    code = sample.main(["--events", str(BROKEN_EVENTS)])
    stderr = capsys.readouterr().err

    assert code == 2
    assert "not in the document" in stderr
    assert "Traceback" not in stderr


def test_events_that_do_not_form_one_chain_are_refused(sample, tmp_path, capsys):
    events = sample.load_events(EVENTS)
    for event in events:
        if event["eventID"].endswith("00a3"):
            del event["parentEventID"]
    branching = tmp_path / "branching.json"
    branching.write_text(
        json.dumps(
            {
                "type": "EPCISDocument",
                "schemaVersion": "2.0",
                "epcisBody": {"eventList": events},
            }
        ),
        encoding="utf-8",
    )

    code = sample.main(["--events", str(branching), "--out", str(tmp_path / "out")])

    assert code == 2
    assert "separate chains" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args, expected",
    [
        (["--epc", "urn:epc:id:sgtin:0614141.107346.9999"], "is not in"),
        (["--events", "does-not-exist.json"], "no event set at"),
    ],
)
def test_input_that_cannot_be_walked_is_explained(sample, args, expected, capsys):
    code = sample.main(args)

    assert code == 2
    assert expected in capsys.readouterr().err


def test_a_document_that_is_not_an_object_is_reported(sample, tmp_path, capsys):
    document = tmp_path / "array.json"
    document.write_text("[]", encoding="utf-8")

    code = sample.main(["--events", str(document)])
    stderr = capsys.readouterr().err

    assert code == 2
    assert "expected an object at the top" in stderr
    assert "Traceback" not in stderr


def test_a_set_without_a_product_epc_is_reported(sample, tmp_path, capsys):
    document = tmp_path / "productless.json"
    document.write_text(
        json.dumps(
            {
                "type": "EPCISDocument",
                "schemaVersion": "2.0",
                "epcisBody": {
                    "eventList": [
                        {
                            "eventID": "urn:uuid:5f0f4a3e-0009-4a3e-9b1a-0000000000a9",
                            "type": "ObjectEvent",
                            "eventTime": "2026-09-02T08:12:00.000+02:00",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    code = sample.main(["--events", str(document)])
    stderr = capsys.readouterr().err

    assert code == 2
    assert "mentions no product EPC" in stderr
    assert "Traceback" not in stderr


def test_a_different_2x_version_is_rejected(sample, tmp_path, capsys):
    events = sample.load_events(EVENTS)
    document = tmp_path / "version-2-1.json"
    document.write_text(
        json.dumps(
            {
                "type": "EPCISDocument",
                "schemaVersion": "2.1",
                "epcisBody": {"eventList": events},
            }
        ),
        encoding="utf-8",
    )

    code = sample.main(["--events", str(document)])
    stderr = capsys.readouterr().err

    assert code == 2
    assert "this sample reads EPCIS 2.0" in stderr


def test_jsonld_is_not_an_offered_format(sample):
    # The exporter reifies the relationships, so the sample does not offer a
    # format whose round trip it cannot check. argparse refuses it up front.
    with pytest.raises(SystemExit):
        sample.main(["--format", "jsonld"])


def test_ntriples_round_trips(sample, tmp_path, capsys):
    code = sample.main(["--format", "ntriples", "--out", str(tmp_path)])

    assert code == 0
    assert list(tmp_path.glob("*.nt"))
    assert "read back and checked" in capsys.readouterr().out
