"""
EPCIS 2.0 - walk a product passport chain end to end

Reads an EPCIS 2.0 event set (JSON), keeps the events that touch one product,
orders them into a chain and exports the resulting product passport as RDF.

Run it from the repository root:

    python examples/epcis/walk_chain.py

    python examples/epcis/walk_chain.py --epc urn:epc:id:sgtin:0614141.107346.2027
    python examples/epcis/walk_chain.py --events examples/epcis/events_missing_parent.json

The event set ships with the sample in events.json; README.md says where the
events come from and which part of them is EPCIS and which part is ours.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Set before importing semantica: the progress bars would otherwise interleave
# with the chain this sample prints.
os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")

from semantica.export import RDFExporter  # noqa: E402  (after the env var)

HERE = Path(__file__).resolve().parent

#: Prefixes the EPCIS 2.0 JSON-LD context binds, kept here because this sample
#: reads plain JSON: nothing in it runs a JSON-LD processor, so compact IRIs
#: like ``cbv:BizStep-shipping`` have to be expanded by hand.
EPCIS_PREFIXES = {
    "epcis": "https://ref.gs1.org/epcis/",
    "cbv": "https://ref.gs1.org/cbv/",
    "gs1": "https://gs1.org/voc/",
}

#: Where the EPC in each event type sits.
EPC_FIELDS = ("epcList", "childEPCs", "inputEPCList", "outputEPCList")

#: The chain predicates. EPCIS 2.0 has no event-to-event link (it orders events
#: by time, and parentID only says which container an aggregation was about),
#: so the two links below are this sample's own and live in their own
#: namespace rather than being passed off as GS1 vocabulary.
PASSPORT_NS = "https://semantica.dev/examples/epcis/passport#"
HAS_EVENT = PASSPORT_NS + "hasEvent"
FOLLOWED_BY = PASSPORT_NS + "followedBy"
BIZ_STEP = PASSPORT_NS + "bizStep"
BIZ_LOCATION = PASSPORT_NS + "bizLocation"
EVENT_TIME = PASSPORT_NS + "eventTime"


class EpcisChainError(Exception):
    """The event set cannot be walked into a chain. Message is for the reader."""


def expand(term: str) -> str:
    """Expand a compact IRI from the EPCIS context; leave anything else alone."""
    prefix, sep, local = term.partition(":")
    if sep and prefix in EPCIS_PREFIXES:
        return EPCIS_PREFIXES[prefix] + local
    return term


def local_name(term: str) -> str:
    """The readable end of a compact or full IRI: ``cbv:BizStep-shipping`` -> ``BizStep-shipping``."""
    expanded = expand(term)
    return expanded.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def load_events(path: Path) -> List[Dict[str, Any]]:
    """Read an EPCIS document and return its event list."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EpcisChainError(f"no event set at {path}")
    except json.JSONDecodeError as exc:
        raise EpcisChainError(
            f"{path.name} is not valid JSON: {exc.msg} (line {exc.lineno})"
        )

    if not isinstance(document, dict):
        raise EpcisChainError(
            f"{path.name} is not an EPCIS document: expected an object at the top, "
            f"found {type(document).__name__}"
        )
    if document.get("type") != "EPCISDocument":
        raise EpcisChainError(
            f"{path.name} is not an EPCIS document: expected type 'EPCISDocument', "
            f"found {document.get('type')!r}"
        )
    version = str(document.get("schemaVersion", ""))
    if version != "2.0":
        raise EpcisChainError(
            f"{path.name} is EPCIS {version or 'of unknown version'}; this sample reads EPCIS 2.0"
        )

    body = document.get("epcisBody")
    if not isinstance(body, dict):
        raise EpcisChainError(f"{path.name} has no epcisBody object")
    events = body.get("eventList")
    if not isinstance(events, list) or not events:
        raise EpcisChainError(f"{path.name} has no epcisBody.eventList")
    return events


def index_events(events: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map eventID -> event, refusing duplicates and events without an id."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for position, event in enumerate(events):
        event_id = event.get("eventID")
        if not event_id:
            raise EpcisChainError(
                f"event #{position} has no eventID, so nothing can point at it"
            )
        if event_id in by_id:
            raise EpcisChainError(f"eventID {event_id} appears twice")
        by_id[event_id] = event
    return by_id


def check_parents(
    events: Iterable[Dict[str, Any]], by_id: Dict[str, Dict[str, Any]]
) -> None:
    """Every parent reference must resolve, and the parent links must not loop."""
    dangling = []
    for event in events:
        parent = event.get("parentEventID")
        if parent and parent not in by_id:
            dangling.append((event["eventID"], parent))
    if dangling:
        lines = [
            f"  {event_id} points at parent {parent}" for event_id, parent in dangling
        ]
        raise EpcisChainError(
            f"{len(dangling)} event(s) point at a parent that is not in the document:\n"
            + "\n".join(lines)
        )

    for event_id in by_id:
        seen = set()
        current: Optional[str] = event_id
        while current:
            if current in seen:
                raise EpcisChainError(f"the parent links loop back to {current}")
            seen.add(current)
            current = by_id[current].get("parentEventID")


def products(events: Iterable[Dict[str, Any]]) -> List[str]:
    """Every EPC the event set mentions, in the order they first appear."""
    found: List[str] = []
    for event in events:
        for field in EPC_FIELDS:
            for epc in event.get(field) or []:
                if epc not in found:
                    found.append(epc)
    return found


def touches(event: Dict[str, Any], epc: str) -> bool:
    return any(epc in (event.get(field) or []) for field in EPC_FIELDS)


def chain_for(events: List[Dict[str, Any]], epc: str) -> List[Dict[str, Any]]:
    """The events that touch ``epc``, ordered root first along parentEventID."""
    own = [event for event in events if touches(event, epc)]
    if not own:
        raise EpcisChainError(f"no event in the set mentions {epc}")

    own_ids = {event["eventID"] for event in own}
    children: Dict[str, str] = {}
    starts = []
    for event in own:
        parent = event.get("parentEventID")
        # A parent outside this product's own events (the pallet it was packed
        # into, say) is not a hole in the document: it just means the chain
        # starts here. check_parents() already rejected the real holes.
        if parent and parent in own_ids:
            if parent in children:
                raise EpcisChainError(
                    f"the events for {epc} branch: {parent} is followed by "
                    f"{children[parent]} and {event['eventID']}"
                )
            children[parent] = event["eventID"]
        else:
            starts.append(event["eventID"])

    if len(starts) != 1:
        raise EpcisChainError(
            f"the events for {epc} form {len(starts)} separate chains instead of one: "
            + ", ".join(sorted(starts))
            + " - add the missing parentEventID links"
        )

    order = []
    current: Optional[str] = starts[0]
    by_id = {event["eventID"]: event for event in own}
    while current:
        order.append(by_id[current])
        current = children.get(current)
    return order


def build_graph(chain: List[Dict[str, Any]], epc: str) -> Dict[str, Any]:
    """Turn the chain into the entity/relationship shape RDFExporter takes."""
    entities: List[Dict[str, Any]] = [
        {
            "id": epc,
            "text": f"Product passport for {epc}",
            "type": "https://gs1.org/voc/Product",
        }
    ]
    relationships: List[Dict[str, Any]] = []

    for event in chain:
        event_id = event["eventID"]
        step = local_name(event.get("bizStep", ""))
        entities.append(
            {
                "id": event_id,
                "text": f"{event.get('type', 'Event')} {step}".strip(),
                "type": expand(f"epcis:{event.get('type', 'Event')}"),
                "metadata": _event_metadata(event),
            }
        )
        relationships.append(
            {"source_id": epc, "target_id": event_id, "type": HAS_EVENT}
        )

    for previous, following in zip(chain, chain[1:]):
        relationships.append(
            {
                "source_id": previous["eventID"],
                "target_id": following["eventID"],
                "type": FOLLOWED_BY,
            }
        )

    return {
        "entities": entities,
        "relationships": relationships,
        "metadata": {
            "num_entities": len(entities),
            "num_relationships": len(relationships),
        },
    }


def _event_metadata(event: Dict[str, Any]) -> Dict[str, Any]:
    """The fields worth carrying into the RDF, as they are written in EPCIS."""
    metadata: Dict[str, Any] = {}
    if event.get("bizStep"):
        metadata["bizStep"] = expand(event["bizStep"])
    if event.get("bizLocation"):
        metadata["bizLocation"] = event["bizLocation"].get("id")
    if event.get("eventTime"):
        metadata["eventTime"] = event["eventTime"]
    return metadata


#: Metadata keys the exporter will not guess a namespace for (issue #1146), so
#: the sample says where its own keys belong.
METADATA_TERMS = {
    "bizStep": BIZ_STEP,
    "bizLocation": BIZ_LOCATION,
    "eventTime": EVENT_TIME,
}


def render_passport(chain: List[Dict[str, Any]], epc: str) -> str:
    """The chain as a human reads it: one line per step, in order."""
    lines = [f"Product passport for {epc}"]
    for number, event in enumerate(chain, start=1):
        location = (event.get("bizLocation") or {}).get("id", "-")
        step = local_name(event.get("bizStep", "?"))
        lines.append(
            f"  {number}. {event.get('eventTime', '?')}  {event.get('type', '?')} "
            f"{step} at {location}"
        )
    return "\n".join(lines)


def read_back(
    graph_path: Path, chain: List[Dict[str, Any]], epc: str, graph_format: str
) -> int:
    """Parse the passport we just wrote and check the links survived.

    The parser has to match what was written: a Turtle parser reading a triple
    file raises before any check runs.
    """
    from rdflib import Graph, URIRef

    graph = Graph()
    graph.parse(graph_path, format="nt" if graph_format == "ntriples" else graph_format)

    for event in chain:
        event_ref = URIRef(event["eventID"])
        if (URIRef(epc), URIRef(HAS_EVENT), event_ref) not in graph:
            raise EpcisChainError(
                f"the passport lost the link from {epc} to {event['eventID']}"
            )
    for previous, following in zip(chain, chain[1:]):
        if (
            URIRef(previous["eventID"]),
            URIRef(FOLLOWED_BY),
            URIRef(following["eventID"]),
        ) not in graph:
            raise EpcisChainError(
                f"the passport lost the link from {previous['eventID']} to {following['eventID']}"
            )
    return len(graph)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Walk an EPCIS 2.0 product passport chain."
    )
    parser.add_argument("--events", type=Path, default=HERE / "events.json")
    parser.add_argument(
        "--epc",
        default=None,
        help="the product to walk (default: the first one in the set)",
    )
    parser.add_argument(
        "--format",
        default="turtle",
        choices=("turtle", "ntriples"),
        help=(
            "passport syntax; JSON-LD is not offered because the exporter "
            "reifies the relationships this sample checks"
        ),
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="where to write the passport"
    )
    args = parser.parse_args(argv)

    try:
        events = load_events(args.events)
        by_id = index_events(events)
        check_parents(events, by_id)

        available = products(events)
        if not available:
            raise EpcisChainError(
                f"{args.events.name} mentions no product EPC in {', '.join(EPC_FIELDS)}"
            )
        epc = args.epc or available[0]
        if epc not in available:
            raise EpcisChainError(
                f"{epc} is not in {args.events.name}; it mentions {', '.join(available)}"
            )

        chain = chain_for(events, epc)
        print(render_passport(chain, epc))

        graph = build_graph(chain, epc)
        passport = RDFExporter().export_to_rdf(
            graph, format=args.format, metadata_terms=METADATA_TERMS
        )

        out_dir = args.out or Path(tempfile.mkdtemp(prefix="epcis-passport-"))
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = {"turtle": "ttl", "jsonld": "jsonld", "ntriples": "nt"}[args.format]
        graph_path = out_dir / f"{epc.rsplit(':', 1)[-1]}.{suffix}"
        graph_path.write_text(passport, encoding="utf-8")

        triple_count = read_back(graph_path, chain, epc, args.format)
        print(f"\nPassport written to {graph_path}")
        print(f"{triple_count} triples, {len(chain)} steps, read back and checked")
    except EpcisChainError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
