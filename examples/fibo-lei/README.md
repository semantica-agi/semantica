# FIBO + LEI sample

Checks real GLEIF LEI records against SHACL shapes derived from a pinned slice of
[FIBO](https://spec.edmcouncil.org/fibo/), the EDM Council's Financial Industry Business
Ontology. It shows Semantica consuming an external financial standard end to end:
the OWL slice is loaded with `OntologyIngestor`, the shapes are generated with
`SHACLGenerator`, and each record is validated with `run_shacl_validation`.

It runs offline. There is no gateway, no LLM call, no credentials, and no network
access; everything it reads is in this directory.

This is a worked example, not a maintained FIBO mapping. It covers a handful of
legal-entity and LEI terms only.

## Run it

From the repository root:

```bash
pip install -e ".[shacl]"          # rdflib is a core dependency, pyshacl comes with [shacl]
python examples/fibo-lei/run.py
```

```text
FIBO slice: FIBO master_2026Q2 (9 classes, 8 properties)
Shapes derived: 11 property shapes
PASS  1595HU08XQEECLKNGF93  C & V Works ApS
PASS  506700GE1G29325QX363  Global Legal Entity Identifier Foundation
PASS  HB7FFAZI0OMZ8PP8OE26  SOCIETY FOR WORLDWIDE INTERBANK FINANCIAL TELECOMMUNICATION
PASS  HWUPKR0MPOU8FGXBT394  Apple Inc.
PASS  UXIATLMNPCXXT5KR1S08  BANK FÜR INTERNATIONALEN ZAHLUNGSAUSGLEICH
5/5 records conform
```

The exit code is 0 when every record conforms and 1 when any record fails.
Pass record files to check only those, and `--show-shapes` to print the generated
SHACL:

```bash
python examples/fibo-lei/run.py path/to/record.ttl
python examples/fibo-lei/run.py --show-shapes
```

Change a constrained value and the run fails. For example, a copy of
`records/HWUPKR0MPOU8FGXBT394.ttl` with the LEI shortened by one character, passed
as the only argument:

```text
FAIL  HWUPKR0MPOU8FGXBT394  Apple Inc.
      - Node <https://example.org/fibo-lei/lei-HWUPKR0MPOU8FGXBT394> has value 'HWUPKR0MPOU8FGXBT39' for <https://spec.edmcouncil.org/fibo/ontology/FND/Relations/Relations/hasTag> which does not match the required pattern.
0/1 records conform
```

`tests/test_fibo_lei_example.py` runs the sample as shipped and with one changed
value for each constraint below.

## Files

| File | What it is |
| ---- | ---------- |
| `fibo-slice.ttl` | The FIBO slice: the classes, properties, and OWL axioms the shapes are derived from, plus the FIBO registration-status individuals. |
| `records/<LEI>.ttl` | One GLEIF LEI record per file, expressed in FIBO terms. |
| `run.py` | Loads the slice, derives the shapes, validates each record, prints PASS or FAIL. |

## What is checked

`run.py` reads the cardinality and `sh:class` of most shapes from the OWL
restrictions in the slice (an `owl:someValuesFrom` restriction becomes
`sh:minCount 1`, a qualified cardinality becomes `sh:minCount`/`sh:maxCount`, and
the restricted class becomes `sh:class`). The minimum and the maximum are read
independently, the minimum only from `someValuesFrom`, min and exact restrictions
and the maximum only from max and exact ones. `FROM_AXIOMS` in `run.py` names the
bounds each shape needs, and the run stops with an error if the slice does not
supply one (so removing the registry entry's own `someValuesFrom RegistrationStatus`
axiom cannot leave only the inherited `max 1`), or if a class or property is not
declared there. The value patterns come from the standards those FIBO terms cite,
because FIBO does not state them as OWL axioms.

| Constraint | Shape | Source |
| ---------- | ----- | ------ |
| LEI format | the LEI's `fibo-fnd-rel-rel:hasTag` is one string matching `^[A-Z0-9]{18}[0-9]{2}$` | ISO 17442 (the standard `LegalEntityIdentifier` is defined by) |
| LEI identifies one entity | `cmns-id:identifies` exactly 1, `sh:class cmns-org:LegalPerson` | FIBO `LegalEntityIdentifier` axiom |
| LEI scheme | `cmns-dsg:isDefinedIn` at least 1 `LegalEntityIdentifierScheme` (the records use `ISO17442-CodeSet`) | FIBO `LegalEntityIdentifier` axiom |
| Entity has an LEI | `cmns-id:isIdentifiedBy` at least 1 `LegalEntityIdentifier` | FIBO `LEIRegisteredEntity` definition |
| Legal name | `fibo-fnd-rel-rel:hasLegalName` exactly 1 `xsd:string` | GLEIF LEI-CDF (`LegalName` is mandatory, single-valued) |
| Jurisdiction | `cmns-rga:isOrganizedIn` exactly 1 `cmns-rga:Jurisdiction` | FIBO axiom on `cmns-org:LegalEntity` (LegalPersons ontology) |
| Jurisdiction code | the jurisdiction's `hasTag` is one string matching `^[A-Z]{2}(-[A-Z0-9]{1,3})?$` | GLEIF LEI-CDF (`LegalJurisdiction` is an ISO 3166-1 or ISO 3166-2 code) |
| Registration status | `fibo-fbc-fct-breg:hasRegistrationStatus` exactly 1 `RegistrationStatus` | FIBO `LegalEntityIdentifierRegistryEntry` (some) and `BusinessRegistryEntry` (max 1) axioms |
| Registration status value | the status is `sh:in` the `RegistrationStatus` individuals declared in the slice | FIBO `BusinessRegistries` status individuals |
| Registry entry holds the LEI | `cmns-col:comprises` at least 1 `LegalEntityIdentifier` | FIBO `LegalEntityIdentifierRegistryEntry` axiom |
| Every LEI has a registry entry | each `LegalEntityIdentifier` is comprised by exactly 1 `LegalEntityIdentifierRegistryEntry` (inverse path) | GLEIF LEI-CDF (every LEI record has one `Registration`, and `RegistrationStatus` is mandatory) |
| Record has an LEI and its entity | the record contains at least one `LegalEntityIdentifier` and one `LEIRegisteredEntity` (checked in `run.py`, not SHACL) | GLEIF LEI-CDF (a record is one LEI and the entity it identifies) |

The status-value shape and the last two rows are not generated by `SHACLGenerator`.
The registry-entry shape is written by hand in `run.py` (`REGISTRY_ENTRY_SHAPE`),
because `SHACLGenerator` does not produce inverse paths. Without it, a record whose
registry entry was removed or retyped would pass, since the status shape only
targets registry entries. The status-value shape (`registration_status_shape()`) is
built from the slice, because `SHACLGenerator` writes `sh:in` values as literals
rather than IRIs. It is needed because each record is validated merged with the
slice: with `sh:class` alone, a record could declare its own
`ex:MadeUpStatus a fibo-fbc-fct-breg:RegistrationStatus` and pass. The last check is
plain Python (`REQUIRED_TYPES`): every shape targets a class, so an empty file, or an
entity whose `LEIRegisteredEntity` type was removed, gives those shapes no focus
node and SHACL alone would report it conforming. The run prints
`no LEIRegisteredEntity in record` (or `no LegalEntityIdentifier in record`) and
fails it instead.

Each record is validated together with the slice, so `sh:class` sees the FIBO class
hierarchy (an `LEIRegisteredEntity` is a `cmns-org:LegalPerson`) and the eleven
registration statuses FIBO defines (`IssuedStatus`, `LapsedStatus`, and so on).

Each record types its entity as both `fibo-be-le-lei:LEIRegisteredEntity` and
`cmns-org:LegalEntity`. FIBO makes `LEIRegisteredEntity` a subclass of
`cmns-org:LegalPerson` only, because GLEIF also issues LEIs to parties that are not
legal entities in that sense (sole traders, for example). The jurisdiction axiom is
stated on `cmns-org:LegalEntity`, so the jurisdiction checks apply only to records
typed that way. All five records here are organizations formed under a
jurisdiction, so they carry the type. A record without it is not checked for
jurisdiction at all. It must still type its entity as `LEIRegisteredEntity` (or a
subclass the slice declares); only the `cmns-org:LegalEntity` type is optional.

Limits worth knowing:

- SHACL reads the OWL restrictions closed-world: a `someValuesFrom` that OWL would
  leave open is required to be present in the record.
- The shapes are also stricter than the OWL in two ways. A `someValuesFrom` becomes
  `sh:class` on every value of the property, and a qualified cardinality
  (`max 1 RegistrationStatus`) becomes an unqualified `sh:maxCount`. So a second,
  non-LEI identifier on `cmns-id:isIdentifiedBy` (a BIC, say) would fail, although
  FIBO allows it. That is fine for these records, which carry only the LEI;
  `sh:qualifiedValueShape` would be the faithful reading if you add other
  identifiers.
- The LEI pattern checks the shape of the code, not its ISO 7064 MOD 97-10 check
  digits.
- Only the four LEI fields below are modelled. Addresses, legal form, entity status,
  and Level 2 relationship data are not.
- GLEIF gives the legal name a language (`de` for BIS, `fr` for SWIFT). The records
  drop it and store the name as a plain string, which is what the `xsd:string`
  shape expects.

## Pinned FIBO version

FIBO release **`master_2026Q2`**
([tag](https://github.com/edmcouncil/fibo/tree/master_2026Q2), commit `f59157fe`,
published 2026-07-14). The slice was extracted from these files of that tag:

| FIBO file | `owl:versionIRI` |
| --------- | ---------------- |
| `BE/LegalEntities/LEIEntities.rdf` | `https://spec.edmcouncil.org/fibo/ontology/BE/20250301/LegalEntities/LEIEntities/` |
| `BE/LegalEntities/LegalPersons.rdf` | `https://spec.edmcouncil.org/fibo/ontology/BE/20251201/LegalEntities/LegalPersons/` |
| `FND/Relations/Relations.rdf` | `https://spec.edmcouncil.org/fibo/ontology/FND/20251201/Relations/Relations/` |
| `FBC/FunctionalEntities/BusinessRegistries.rdf` | `https://spec.edmcouncil.org/fibo/ontology/FBC/20260601/FunctionalEntities/BusinessRegistries/` |

FIBO imports the OMG Commons Ontology Library by unversioned IRI, so the Commons
term declarations in the slice were taken from the modules served at
`https://www.omg.org/spec/Commons/` on 2026-10-22: Organizations, RegulatoryAgencies,
and Designators (`.../20250801/...`), Identifiers and Collections (`.../20221101/...`).
All of these version IRIs are also recorded as `dct:source` in `fibo-slice.ttl`.

Only the terms and axioms the shapes use were copied. Annotations other than
`rdfs:label` and `skos:definition` were dropped, as were the other restrictions on
these classes.

## LEI fields used

Five records were fetched once from the GLEIF API
(`https://api.gleif.org/api/v1/lei-records/<LEI>`) on 2026-10-22 and converted to
Turtle. Four fields are used:

| GLEIF field | FIBO term in the record |
| ----------- | ----------------------- |
| `lei` | `fibo-be-le-lei:LegalEntityIdentifier`, with the code as `fibo-fnd-rel-rel:hasTag` |
| `entity.legalName.name` | `fibo-fnd-rel-rel:hasLegalName` on the `fibo-be-le-lei:LEIRegisteredEntity` |
| `entity.jurisdiction` | `cmns-rga:isOrganizedIn` a `cmns-rga:Jurisdiction`, with the ISO 3166 code as `hasTag` |
| `registration.status` | `fibo-fbc-fct-breg:hasRegistrationStatus` on a `fibo-fbc-fct-breg:LegalEntityIdentifierRegistryEntry`, pointing at the matching FIBO status individual |

The records are a snapshot. Each file names its source URL and the
`registration.lastUpdateDate` it was taken at; the live GLEIF data may have changed
since. `1595HU08XQEECLKNGF93` is included because its status is `LAPSED`, which is a
valid FIBO registration status and so passes.

## Licenses

- **FIBO slice (`fibo-slice.ttl`): MIT License.** FIBO is published under the MIT
  License ([LICENSE at the pinned tag](https://github.com/edmcouncil/fibo/blob/master_2026Q2/LICENSE)),
  and each source ontology carries the same MIT text in its `dct:license`. The OMG
  Commons modules the slice draws on are also MIT (stated in each module's
  `dct:license`). The copyright notices of all source ontologies and the MIT text
  are reproduced at the top of `fibo-slice.ttl`.
- **LEI records (`records/`): CC0 1.0.** GLEIF provides LEI data under
  [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/), per the
  [GLEIF LEI Data Terms of Use](https://www.gleif.org/en/meta/lei-data-terms-of-use).
  The Turtle conversion was made for this example; it is not provided, endorsed, or
  supported by GLEIF. The [CC0 1.0 deed](https://creativecommons.org/publicdomain/zero/1.0/)
  asks that uses of the work not imply endorsement by the author or affirmer, and
  section IV.2 of the GLEIF terms asks the same for anything beyond the original
  LEI data.
- `run.py` and this README are part of Semantica and fall under the repository's
  license.
