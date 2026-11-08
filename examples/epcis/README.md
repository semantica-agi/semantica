# EPCIS 2.0 — product passport chain

A runnable walk down one product's history: eight EPCIS events go in, a product
passport comes out as RDF. Offline, from a clean checkout, in one command.

```bash
python examples/epcis/walk_chain.py
```

```
Product passport for urn:epc:id:sgtin:0614141.107346.2026
  1. 2026-09-02T08:12:00.000+02:00  ObjectEvent BizStep-commissioning at urn:epc:id:sgln:0614141.00001.0
  2. 2026-09-02T09:40:00.000+02:00  AggregationEvent BizStep-packing at urn:epc:id:sgln:0614141.00001.0
  3. 2026-09-03T06:05:00.000+02:00  ObjectEvent BizStep-shipping at urn:epc:id:sgln:0614141.00002.0
  4. 2026-09-03T14:22:00.000+02:00  ObjectEvent BizStep-receiving at urn:epc:id:sgln:0614141.00003.0
  5. 2026-09-05T10:31:00.000+02:00  ObjectEvent BizStep-retail_selling at urn:epc:id:sgln:0614141.00003.1

Passport written to <temp dir>/0614141.107346.2026.ttl
42 triples, 5 steps, read back and checked
```

Nothing is installed beyond what the core package already pulls in: `rdflib` is
a core dependency, and the export goes through `RDFExporter.export_to_rdf()` in
`semantica/export/rdf_exporter.py`. `--out` writes the passport where you want
it, `--format` takes `turtle` (default) or `ntriples`. JSON-LD is not offered:
the exporter's serializer turns the passport's relationships into their own
nodes and writes event classes as `semantica:type`, so the chain links this
sample checks would not survive the round trip.

The event set holds two products. Asking for the second one gives its own,
shorter chain:

```bash
python examples/epcis/walk_chain.py --epc urn:epc:id:sgtin:0614141.107346.2027
```

## Where the events come from

`events.json` is an **EPCIS 2.0** document (`schemaVersion: "2.0"`, JSON
binding, `@context` pointing at
`https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld`).

The eight events were written by hand for this sample. They are not a capture
from a live system and contain no real company data: the SGTIN, SSCC and SGLN
identifiers use the `0614141` GS1 prefix that GS1 keeps as its own example
prefix, and the one business transaction points at
`https://example.org/purchase-orders/4711`. The shapes follow the standard —
`ObjectEvent` and `AggregationEvent`, CBV business steps (`commissioning`,
`packing`, `shipping`, `receiving`, `retail_selling`), `readPoint` and
`bizLocation` as SGLN.

One field is ours, not the standard's: **`parentEventID`**. EPCIS 2.0 has no
event-to-event link. It orders events by `eventTime`, and `parentID` means the
container an aggregation was about (the SSCC here), not the event that came
before. To walk a chain instead of sorting timestamps, each event carries the
`eventID` of the event it follows. It is a sample-level convention, kept in the
event set and in the passport's own `passport#` namespace rather than dressed
up as GS1 vocabulary:

| predicate | means |
|---|---|
| `passport#hasEvent` | this product appears in that event |
| `passport#followedBy` | this event came before that one |
| `passport#bizStep` | CBV business step, as a `https://ref.gs1.org/cbv/` IRI |
| `passport#bizLocation` | where it happened |
| `passport#eventTime` | when |

The class of each event is the real one, `https://ref.gs1.org/epcis/ObjectEvent`
and `.../AggregationEvent`, so the passport reads against the GS1 vocabularies
where they apply.

## A hole in the event set is reported, not raised

```bash
python examples/epcis/walk_chain.py --events examples/epcis/events_missing_parent.json
```

```
error: 1 event(s) point at a parent that is not in the document:
  urn:uuid:5f0f4a3e-0003-...-0000000000a3 points at parent urn:uuid:5f0f4a3e-0002-...-0000000000a2
```

Exit code is 2 and there is no traceback. `events_missing_parent.json` is
`events.json` with the packing event removed, so the shipping event is left
pointing at an event that is no longer there.

The same guard covers the other ways an event set stops being a chain: a
missing `eventID`, a duplicate `eventID`, a wrong `schemaVersion`, an `EPC` that
the set never mentions, and the two events for one product that both claim to
be first.

## What this sample does not do

It walks one product. It does not implement EPCIS 2.0: no query interface, no
capture interface, no `TransformationEvent` handling beyond reading the EPCs it
carries, no JSON-LD expansion (the compact IRIs are expanded by hand from the
prefixes the context binds), no validation against the standard's JSON schema.
The point is the path — an event document arrives, a passport leaves — not
coverage of the standard.
