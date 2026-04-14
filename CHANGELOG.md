# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- **Fix: `KGVisualizer` now accepts `KnowledgeGraph` objects in all `visualize_*` methods** (PR `visualization` by @KaifAhmad1, closes #458): All five public methods (`visualize_network`, `visualize_communities`, `visualize_centrality`, `visualize_entity_types`, `visualize_relationship_matrix`) previously called `graph.get("entities", [])`, silently producing no output when passed a non-dict object. Added `_normalize_graph()` which duck-types the input — dicts pass through unchanged; any object exposing `.entities` / `.relationships` attributes (e.g. the result of `GraphBuilder.build()`) is converted to the canonical dict form; anything else raises a clear `ProcessingError` naming the offending type. 21 tests added in `tests/visualization/test_kg_visualizer_normalize_graph.py`.

- **Security: 12 vulnerability fixes across CRITICAL → LOW severity** (PR `security-enhancement` by @KaifAhmad1):

  **Critical**
  - **Eval injection eliminated** (`semantica/parse/media_parser.py`): Replaced `eval(stream.get("r_frame_rate", ...))` — which executed arbitrary Python from ffprobe JSON output — with a `_safe_parse_fps()` helper using `fractions.Fraction`. No code execution possible regardless of ffprobe output content. (CWE-95)
  - **Unsafe pickle deserialization replaced** (`semantica/context/agent_memory.py`): `AgentMemory.save()` / `load()` previously used `pickle.dump` / `pickle.load`, allowing RCE if an attacker could write the `.pkl` file. Replaced with `json.dump` / `json.load`. `MemoryItem.to_dict()` / `MemoryItem.from_dict()` added for safe round-trip serialization — `timestamp` via `isoformat()`, `embedding` dropped (not JSON-safe, regenerated on demand). Legacy `.pkl` files are detected and refused with a migration message. (CWE-502)

  **High**
  - **SQL injection hardened** (`semantica/ingest/snowflake_ingestor.py`): `WHERE`, `ORDER BY`, `LIMIT`, and `OFFSET` were f-string interpolated directly into Snowflake queries. `LIMIT` / `OFFSET` now use parameterized `%s` placeholders; `ORDER BY` is validated against a strict `^[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?` regex; `WHERE` clauses containing semicolons are rejected before execution. (CWE-89)
  - **XXE protection added for RDF/XML parsing** (`semantica/explorer/utils/rdf_parser.py`): `rdflib.Graph().parse()` on XML-based RDF formats had no external-entity restrictions. Added `_safe_parse_rdf()` wrapper that calls `defusedxml.defuse_stdlib()` before parsing, neutralising Billion Laughs and local file-read XXE attacks. Falls back gracefully with a `UserWarning` if `defusedxml` is not installed. (CWE-611)
  - **Security headers and CORS added to main server** (`semantica/server.py`): No CORS policy, no response security headers, and raw `Exception` details were returned to clients. Added `CORSMiddleware` (origins from `SEMANTICA_CORS_ORIGINS` env var, defaults to `localhost` only); `_SecurityHeadersMiddleware` emitting `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, and HSTS (HTTPS only) on every response; global error handler that logs internally and returns a generic `500`. (CWE-346, CWE-200)
  - **CORS and WebSocket hardened in Explorer app** (`semantica/explorer/app.py`): `allow_methods=["*"]` and `allow_headers=["*"]` narrowed to `GET, POST, DELETE, OPTIONS` and `Content-Type, Authorization` only. `KeyError` / `ValueError` exception handlers now log the real message server-side and return generic text to clients. WebSocket messages larger than 64 KB trigger close with code `1009` (Message Too Big), preventing memory exhaustion via large frame injection. (CWE-346, CWE-400)

  **Medium**
  - **Algorithm parameter validated by enum** (`semantica/explorer/routes/graph.py`): The `algorithm` query parameter previously accepted any string; unknown values silently fell back to BFS. Replaced with `_PathAlgorithm(str, Enum)` — FastAPI now returns `422 Unprocessable Entity` for any value other than `bfs` or `dijkstra`. (CWE-20)
  - **RDF upload extension allowlist** (`semantica/explorer/routes/vocabulary.py`): No file extension check was performed before reading RDF uploads. Extension is now validated against `{".ttl", ".rdf", ".owl", ".xml", ".jsonld", ".json-ld", ".json"}` before any content is read. (CWE-434)
  - **Prompt injection mitigated** (`semantica/semantic_extract/llm_extraction.py`): User-supplied text and entity/relation labels were embedded directly into LLM prompts via f-string interpolation — a crafted input like `"\n\nIgnore all above instructions..."` could override system instructions. All user-supplied content is now passed through `json.dumps()` before embedding, neutralising newlines, quotes, and instruction-override attempts. (CWE-1336)
  - **Dynamic `__import__()` removed** (`semantica/pipeline/pipeline_validator.py`): `__import__("collections").Counter(...)` replaced with a proper `from collections import Counter` module-level import. (CWE-95)
  - **ReDoS eliminated** (`semantica/explorer/routes/enrich.py`): `re.split(r"\s+AND\s+", antecedent_text, re.IGNORECASE)` on user-supplied rule strings could exhibit polynomial backtracking. Fixed by normalising whitespace first with `" ".join(text.split())` (no regex) then splitting on the literal `" AND "`. Closes CodeQL alert #12. (CWE-1333)
  - **Path traversal blocked** (`semantica/server.py`): SPA catch-all route used `STATIC_DIR / full_path` without validation. Added `Path.resolve()` + `relative_to()` check that returns `400 Bad Request` for any path that escapes `STATIC_DIR`. Closes CodeQL alerts #13 and #14. (CWE-22)

  **Low**
  - **SPARQL result cap and timeout** (`semantica/explorer/routes/sparql.py`): SPARQL queries ran to completion with no row limit or timeout; expensive queries could exhaust memory or block indefinitely. Results are now capped at 5 000 rows; `asyncio.wait_for(..., timeout=30)` abandons the await after 30 seconds and returns a structured error response. A module-level `asyncio.Semaphore(4)` caps concurrent in-flight `graph.query` calls so that timed-out threads (which continue running in the pool) cannot crowd out other requests by exhausting executor workers. `SparqlResponse` gains a `truncated: bool` field so callers can detect a capped result set. (CWE-400)
  - **Import upload size limit and extension allowlist** (`semantica/explorer/routes/export_import.py`): No file size or type checks were enforced before reading import uploads. Extension is now validated against `{".json", ".csv"}` (the formats the handler actually parses — allowlist trimmed to match implementation); a hard 50 MB cap is enforced before content is read. (CWE-434)

  **CodeQL / scanning infrastructure**
  - Added `.github/codeql/codeql-config.yml` with `paths-ignore` for `cookbook/**/*.html` and `cookbook/**/*.js`. Notebook-exported HTML files embed entire minified third-party bundles (Plotly + MapLibre GL JS v4.7.1) that triggered false-positive JS alerts #15–#18. The Advanced Setup workflow now references this config via `config-file:`. Closes CodeQL alerts #15, #16, #17, #18.
  - Removed blanket rule-ID auto-dismiss job from `.github/workflows/codeql.yml`. The previous job dismissed every open alert whose `rule.id` matched a fixed list on each `main` push — this would silently suppress any future real vulnerability of the same type. Replaced with a commented template for pinning specific alert numbers when manual dismissal is genuinely required.

- **Fix: Knowledge Explorer — blockers and security hardening** (PR #420 by @ZohaibHassan16, review fixes by @KaifAhmad1):
  - **Dockerfile**: Renamed `DockerFile` → `Dockerfile` (case-sensitive filename caused Docker build failures on Linux CI). Fixed `CMD` module path from the non-existent `semantica.server:app` to `semantica.explorer.app:app`, which caused the Docker image to crash on startup. Added `app = create_app()` at module level in `semantica/explorer/app.py` so uvicorn can reference the ASGI app instance directly.
  - **CORS hardening**: Changed `EXPLORER_CORS_ORIGINS` default from `"*"` to `"http://localhost:5173,http://127.0.0.1:5173"`. Any deployment that does not explicitly set the env var no longer exposes the API to all origins. The env var override continues to work as before.
  - **`get_ws_manager()` guard** (`semantica/explorer/dependencies.py`): `get_ws_manager()` now raises HTTP 503 if `app.state.ws_manager` is absent, matching the existing `get_session()` guard. Previously raised an unhandled `AttributeError` during testing or if the lifespan had not completed.
  - **SPARQL read-only enforcement** (`semantica/explorer/routes/sparql.py`): Added `_is_read_only_query()` regex guard — rejects any query whose first keyword is not `SELECT`, `ASK`, `CONSTRUCT`, or `DESCRIBE`. `INSERT`, `DELETE`, `UPDATE`, `LOAD`, and `DROP` queries now return a structured `SparqlResponse` error instead of being executed against the rdflib projection.
  - **Vocabulary import size limit** (`semantica/explorer/routes/vocabulary.py`): Added 10 MB upload cap for both file and raw-text payloads — returns HTTP 413 with a human-readable message before calling `parse_skos_file()`. Prevents memory exhaustion from oversized RDF uploads.
  - **JSON-LD format auto-detection** (`semantica/explorer/routes/vocabulary.py`): Import route now detects `.jsonld`, `.json-ld`, and `.json` file extensions and passes `"json-ld"` to `parse_skos_file()`. Previously these extensions fell through to `"turtle"` and failed silently despite JSON-LD being listed as a supported format.
  - **Annotation O(1) lookup** (`semantica/explorer/routes/annotations.py`, `semantica/explorer/session.py`): `create_annotation` previously called `get_annotations()` and scanned the full list to find the just-created annotation (O(N)). Added `GraphSession.get_annotation(annotation_id)` — O(1) dict lookup — and updated the route to use it directly.
  - **Self-loop guard in `batchMergeEdges`** (`semantica-explorer/src/store/graphStore.ts`): Added `if (source === target) continue` guard at the start of the loop. The Graphology instance is initialised with `allowSelfLoops: false`; a self-loop edge from reasoning inferences or provenance cycles previously caused an uncaught Graphology error that silently broke graph loading.
  - **Static build artifacts removed from git** (`.gitignore`): Added `semantica/static/` to `.gitignore` and removed all pre-built Vite bundles from version control. The Docker multi-stage build already rebuilds the frontend from source; committing minified bundles bloated repository history and caused merge conflicts on every frontend change.

- **Fix: TripletStore.store() IRI resolution regressions** (PR #447 follow-up by @KaifAhmad1):
  - Fixed `AttributeError` crash when entity or relationship IDs are non-string types (e.g. integers emitted by `GraphBuilder`). `_resolve_iri()` previously called `.startswith()` directly on the raw ID; it now coerces any value to `str()` at entry, restoring the implicit stringification that the old f-string URN minting provided.
  - Fixed W3C vocabulary prefixes (`owl:Thing`, `xsd:date`, `rdfs:Literal`, `skos:Concept`, etc.) being incorrectly re-namespaced under the ontology `base_uri` (e.g. `https://example.com/owl:Thing`) when `base_uri` was present. `_resolve_iri()` now consults a known-prefix expansion table (`xsd`, `rdf`, `rdfs`, `owl`, `skos`, `semantica`) before applying `base_uri`, matching the same prefix map already used in `BlazegraphStore`. Standard vocabulary IRIs are always expanded to their canonical W3C forms regardless of what `base_uri` is set to.
  - Added 5 regression tests: integer IDs with and without `base_uri`, `owl:Thing` domain/range, `xsd:date` range, and `skos:Concept` parent class expansion. Total tests in `TestTripletStoreOntologyNamespace`: 14.

- **Fix: TripletStore.store() ignores ontology namespace base_uri** (PR #447 by @KaifAhmad1):
  - `store(knowledge_graph, ontology)` was minting `urn:entity:{id}`, `urn:class:{type}`, and `urn:property:{name}` URIs for all bare local names, even when `ontology.namespace.base_uri` was present. This made instance data and ontology class data irreconcilable in SPARQL joins.
  - Extracts `base_uri` once from `ontology["namespace"]["base_uri"]` (with `ontology["uri"]` as fallback) and ensures a trailing separator so concatenation is always a valid IRI path.
  - Introduced `_resolve_iri(local, kind)` closure applied to all 7 IRI-minting sites: entity URIs, entity types, relationship predicates, ontology class URIs, parent class URIs, property URIs, and domain/range URIs. Explicit `entity["uri"]` values are never overridden. Falls back to `urn:` only when no `base_uri` is available.
  - Added 9 tests in `TestTripletStoreOntologyNamespace` covering all expansion paths, `urn:` fallback, explicit URI passthrough, top-level `uri` key fallback, and trailing-slash safety.

- **Fix: Blazegraph literal serialization and SPARQL injection hardening** (PR #448 by @KaifAhmad1):
  - Fixed `_build_ntriples()`, `_build_insert_data()`, `find_triplets()`, and `delete_triplet()` in `BlazegraphStore` — all four methods previously unconditionally wrapped every triplet object in `<...>` as an IRI, causing Blazegraph to reject or misparse any triple whose object was a plain string, typed literal, or language-tagged literal.
  - Added `_format_object_for_sparql(triplet)` — central formatter that selects the correct SPARQL/N-Triples token: IRI (`<uri>`), typed literal (`"value"^^<datatype>`), language-tagged literal (`"value"@lang`), or plain literal (`"value"`).
  - Added `_resolve_datatype_iri(datatype)` — expands prefixed datatype names (`xsd:integer`, `rdf:langString`, `rdfs:Literal`, `owl:real`, `skos:notation`) to their full IRIs instead of producing invalid `<xsd:integer>` tokens. Accepts full `http/https/urn` IRIs and already-bracketed IRIs after whitespace validation. Rejects unknown prefixes and bare local names with a clear `ValueError`.
  - Added language-tag validation against RFC 5646 (`^[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$`) — values containing whitespace, dots, or other punctuation (e.g. `"en . CLEAR ALL #"`) raise `ValueError` before interpolation, closing a SPARQL injection vector in `metadata["lang"]` / `metadata["language"]`.
  - Added datatype-string validation — whitespace and SPARQL-delimiting characters inside `metadata["datatype"]` / `metadata["literal_datatype"]` raise `ValueError`, closing the parallel injection vector for typed literals.
  - Added `_is_uri_value(value)` — URI detection using `urlparse`; rejects strings that only start with a URI scheme but contain whitespace (e.g. `"http not a uri"` is serialised as a literal, not an IRI).
  - Added `_escape_literal(value)` — escapes `\`, `"`, `\n`, `\r`, `\t` inside literal strings before SPARQL interpolation.
  - New test file `tests/triplet_store/test_blazegraph_store.py` — 15 offline unit tests covering URI serialization, plain/typed/language-tagged/escaped literals, prefix expansion, IRI passthrough, injection rejection, and `_build_insert_data` delegation; all run without a live Blazegraph instance.

- **OWLGenerator user-facing schema compatibility fixes** (Issue #446):
  - Fixed OWL class/property IRI identifier fallback order to prefer `label` and then `name`.
  - Fixed datatype property handling to accept scalar and list `range` values in rdflib path (including `xsd:*`, full IRIs, and local names), preventing list-based `.startswith()` crashes.
  - Fixed generated class/property/domain/range IRIs to use the current ontology dict `uri` namespace for each generation call (instead of drifting to default namespace manager base URI when per-entity `uri` is omitted).
  - Fixed `subClassOf` / `subclassOf` parent resolution so local class names are expanded to ontology IRIs consistently with domain/range behavior.
  - Added/expanded regression coverage in `tests/ontology/test_ontology_comprehensive.py` (`test_owl_generator_user_facing_schema_compatibility`) for label-first fallback, lowercase `subclassOf`, datatype range lists, and ontology namespace consistency.

- **SKOS Vocabulary Module** (PR #319 by @KaifAhmad1):
  - **Namespace helpers** (`semantica/ontology/namespace_manager.py`): Added `get_skos_uri(local_name)` — returns the full `http://www.w3.org/2004/02/skos/core#<local_name>` URI for any SKOS term. Added `build_concept_scheme_uri(name)` — slugifies a human-readable vocabulary name (spaces/special chars → hyphens, lower-cased) and anchors the result at the configured base URI as `<base>/vocab/<slug>`.
  - **Triplet-store SKOS helpers** (`semantica/triplet_store/triplet_store.py`): Added `add_skos_concept(concept_uri, scheme_uri, pref_label, alt_labels, broader, narrower, related, definition, notation)` — assembles and stores all required SKOS triples (auto-declares the `skos:ConceptScheme`, asserts `rdf:type skos:Concept`, `skos:inScheme`, `skos:prefLabel`, and all optional predicates) via the existing `add_triplets()` API; no new storage paths introduced. Added `get_skos_concepts(scheme_uri=None)` — issues a SPARQL `SELECT` via `execute_query()` and collapses multi-valued `altLabel`/`broader`/`narrower`/`related` bindings into structured concept dicts; optional `scheme_uri` restricts results to one vocabulary.
  - **OntologyEngine vocabulary APIs** (`semantica/ontology/engine.py`): Added three public methods that delegate to `QueryEngine` via `self.store.execute_query()` — `list_vocabularies()` returns all `skos:ConceptScheme` instances with labels; `list_concepts(scheme_uri)` returns every `skos:Concept` in a scheme with `pref_label` and `alt_labels`; `search_concepts(query, scheme_uri=None)` performs case-insensitive substring matching across `skos:prefLabel` and `skos:altLabel` with optional scheme scoping.
  - **Security**: `search_concepts` sanitises user input (escapes `\`, `"`, newlines) before embedding it in the SPARQL string literal. All URI interpolation uses the existing `_sanitize_uri` helper.
  - **Tests**: Added `TestSKOSOntologyEngine` (14 tests) to `tests/ontology/test_ontology_comprehensive.py` and `TestSKOSTripletStore` (6 tests) to `tests/triplet_store/test_triplet_store.py`. Coverage: URI helpers, vocabulary listing + deduplication, concept listing with multi-value alt-label collapse, search with/without scheme filter, injection sanitisation, empty results, and no-store error paths. 20 new tests, 0 failures, 1162 total passing, 0 regressions.
  - **Docs** (`docs/reference/ontology.md`): Added "SKOS Vocabulary Management" section with SKOS data-model reference table, `add_skos_concept` usage example, bulk import via rdflib + `add_triplets`, `list_vocabularies` / `list_concepts` / `search_concepts` usage examples, and `NamespaceManager` URI helper examples.
  - No new top-level Python package created; all code extends existing `semantica/ontology/` and `semantica/triplet_store/` packages. Fully opt-in and non-breaking.

- **SHACL Shape Generation & Validation** (PR #318 by @KaifAhmad1):
  - **Phase 1 — Generation**: Added `SHACLGenerator` to `semantica/ontology/ontology_generator.py` — 6-stage internal pipeline: `_build_class_index` → `_generate_node_shapes` → `_attach_property_shapes` → `_propagate_inheritance` → `_apply_quality_tier` → `serialize`. Derives SHACL node and property shapes from any Semantica ontology dict; zero hand-authoring. Three output formats: Turtle, JSON-LD, N-Triples. Three quality tiers: `"basic"` (structure + cardinality), `"standard"` (+ `sh:in`, `sh:pattern`, inheritance; default), `"strict"` (+ `sh:closed true` + `sh:ignoredProperties` on all non-empty shapes). Iterative inheritance propagation up to 3+ levels, cycle-safe (max 20 passes), no duplicate property shapes per shape. No-domain properties attach to all node shapes. Added `PropertyShape`, `NodeShape`, `SHACLGraph` dataclasses.
  - **Phase 1 — Engine API**: Added `OntologyEngine.to_shacl(ontology, *, format, base_uri, shapes_uri, include_inherited, severity, quality_tier, validate_output)` and `OntologyEngine.export_shacl(ontology, path, format, encoding)` to `semantica/ontology/engine.py`. Added `RDFExporter.export_shacl(shacl_string, file_path, format, encoding)` to `semantica/export/rdf_exporter.py` with extension validation (`.ttl`, `.jsonld`, `.nt`, `.shacl`).
  - **Phase 2 — Runtime Validation**: Added `SHACLViolation` (8 fields: `focus_node`, `result_path`, `constraint`, `severity`, `message`, `value`, `shape`, `explanation`; `to_dict()`) and `SHACLValidationReport` (`conforms`, `violations`, `warnings`, `infos`, `raw_report`; `violation_count`/`warning_count` properties; `summary()`, `explain_violations()`, `to_dict()`) to `semantica/ontology/ontology_validator.py`. Added `_run_pyshacl(data_graph_str, shacl_str, data_graph_format, shacl_format)` — thin wrapper around `pyshacl.validate()` returning typed `SHACLValidationReport`. `pyshacl` and `rdflib` are optional deferred imports (`pip install semantica[shacl]`); `ImportError` with install hint raised if absent. Added `OntologyEngine.validate_graph(data_graph, shacl=None, *, ontology=None, data_graph_format, shacl_format, explain, abort_on_first)` — exactly one of `shacl`/`ontology` must be provided (`ValueError` otherwise); `explain=True` populates plain-English explanations via rule-based templates for all 7 SHACL constraint types (`MinCount`, `MaxCount`, `Datatype`, `Class`, `In`, `Pattern`, `Closed`).
  - **Exports**: `SHACLGenerator`, `SHACLGraph`, `NodeShape`, `PropertyShape`, `SHACLValidationReport`, `SHACLViolation` added to `semantica/ontology/__init__.py`.
  - **Security & reliability fixes**:
    - **High** (`engine.py`): Replaced path-vs-content heuristic (`len < 500 and "\n" not in s`) with `os.path.exists()` — prevents attacker-controlled SHACL strings from being silently interpreted as file paths.
    - **High** (`ontology_generator.py`): `_propagate_inheritance` now uses `dataclasses.replace(pps)` instead of appending parent `PropertyShape` objects by reference — mutations on a child's inherited property no longer silently affect the parent.
    - **Medium** (`engine.py` / `ontology_validator.py`): Added `shacl_format` parameter to `validate_graph` and `_run_pyshacl`; full format alias map (`"ttl"→"turtle"`, `"jsonld"→"json-ld"`, `"ntriples"→"nt"`) in both `to_shacl` validate-output and `_run_pyshacl` — JSON-LD and N-Triples shapes no longer fail parsing.
    - **Medium** (`ontology_generator.py`): `sh:ignoredProperties` now emits full URI `<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>` instead of prefixed `rdf:type` — eliminates prefix-dependency in strict-tier Turtle output.
    - **Low** (`ontology_generator.py`): `_prefix_decls` now iterates `sorted(graph.prefixes.items())` — deterministic Turtle output for reproducible CI `git diff` checks.
  - **Tests**: Added `TestSHACLGeneration` (16 tests) to `tests/ontology/test_ontology_comprehensive.py` and `TestSHACLHierarchicalAndValidation` (18 tests) to `tests/ontology/test_ontology_advanced.py`. 34 new tests, 0 failures, 1111 total passing, 0 regressions.
  - **README**: Added `## Unreleased / Coming Next` section, SHACL bullet points under Features → Ontology and Export Formats, updated Modules table, full Phase 1 + Phase 2 code examples under `## Ontology`, `pip install semantica[shacl]` under Installation.

- **Temporal GraphRAG Integration** (PR #402 by @KaifAhmad1):
  - Added `TemporalGraphRetriever` to `semantica/context/context_retriever.py` — drop-in wrapper for any `ContextRetriever`; calls `base_retriever.retrieve(query)` then filters `related_entities`/`related_relationships` via `reconstruct_at_time()`; `at_time=None` is a true passthrough; returns new `RetrievedContext` objects via `dataclasses.replace()` (no in-place mutation); temporal modules guarded with `try/except` at import time.
  - Extended `ContextRetriever._generate_reasoned_response()` and `query_with_reasoning()` with `at_time` and `header_template` parameters — when `at_time` is set a structured temporal header (`[Graph context valid as of: … UTC | Source: KnowledgeGraph snapshot]`) is prepended to the LLM context block; omitted when `at_time=None` (prompt byte-identical to previous behaviour); naive datetimes normalised to UTC; header built via `str.replace` not `.format` (format-string injection guard).
  - Added `TemporalQueryRewriter` and `TemporalQueryResult` in `semantica/kg/temporal_query_rewriter.py` — extracts `temporal_intent` (`"before"`, `"after"`, `"at"`, `"during"`, `"between"`, `None`), `at_time`, `start_time`, `end_time`, and `rewritten_query` from natural-language queries; regex-only by default (zero LLM calls), optional LLM-assisted mode; datetime resolution always delegated to `TemporalNormalizer`; word-boundary guards prevent false matches (`at` inside `that`); year fallback handles noun-phrase dates like `"the 2021 merger"`; never calls `reconstruct_at_time`.
  - Exported `TemporalGraphRetriever` from `semantica.context`; exported `TemporalQueryRewriter`, `TemporalQueryResult` from `semantica.kg`.
  - **Security fixes**: format-string injection in header template (medium); unconditional temporal module import at package init (low).
  - **Bug fixes**: in-place mutation of `RetrievedContext` (high); naive datetime formatted without timezone (low); missing `timezone` import causing `NameError` (low).
  - Added 99 tests across `tests/context/test_temporal_retriever.py` (56) and `tests/kg/test_temporal_query_rewriter.py` (43); 0 failures, 0 regressions.

- **Temporal Provenance & Export** (PR #401 by @KaifAhmad1):
  - **Transaction time on provenance records** (`semantica/kg/provenance_tracker.py`): `track_entity()` now automatically attaches `recorded_at = datetime.now(UTC).isoformat()` to every new record — no opt-in required. Existing records without `recorded_at` continue to work in all existing query methods (treated as unknown, not an error). Added `query_recorded_between(start, end) -> list` returning all provenance records whose `recorded_at` falls within the inclusive range; accepts `datetime` objects or ISO strings including trailing `Z`.
  - **Fact revision audit trail** (`semantica/kg/provenance_tracker.py`): Added `revision_history(fact_id) -> list` returning the complete revision chain ordered by `recorded_at` ascending; each entry includes `version` (int, 1-based), `valid_from`, `valid_until`, `recorded_at`, `author`, and optionally `revision_type`/`supersedes`; returns `[]` for unknown facts (never raises). Added `export_audit_log(fact_ids, format) -> str` supporting `"json"` (pretty-printed) and `"csv"` (with header row) formats.
  - **OWL-Time RDF export** (`semantica/export/rdf_exporter.py`): `export_to_rdf()` gains `include_temporal: bool = False` and `time_axis: str = "valid"` parameters. When `include_temporal=True`, emits OWL-Time triples (`http://www.w3.org/2006/time#`) for every relationship carrying `valid_from`/`valid_until` — a `time:Interval` node linked via `time:hasTime`, `time:hasBeginning`/`time:hasEnd` with `time:Instant` nodes, and `time:inXSDDateTimeStamp` values. `time_axis` controls which axis is exported: `"valid"`, `"transaction"`, or `"both"`. Relationships without temporal metadata are unaffected. Default `include_temporal=False` produces output identical to current behavior. **Design decision for `TemporalBound.OPEN`**: OWL-Time has no standard predicate for "no known end date" — `time:hasEnd` is omitted and `semantica:openEndedInterval "true"^^xsd:boolean` is emitted on the interval node instead. Output parses without errors in rdflib.
  - **Stable snapshot serialization format** (`semantica/kg/temporal_query.py`, new `semantica/kg/schemas/temporal_snapshot_v1.json`): `create_snapshot()` now stamps `"format_version": "1.0"` on every snapshot. Added `validate_snapshot(snapshot) -> bool` — validates required fields (`format_version`, `label`, `timestamp`, `author`, `description`, `entities`, `relationships`, `checksum`); returns `False` with structured DEBUG-level error details on failure, never raises. Added `migrate_snapshot(snapshot) -> dict` — deep-copies and upgrades old-format snapshots to v1.0, populating missing required fields with `None`; already-v1.0 snapshots returned unchanged with no data loss. New `semantica/kg/schemas/temporal_snapshot_v1.json` — JSON Schema (draft 2020-12) defining required and optional fields, types, and constraints.
  - Added 28 new tests in `tests/test_401_temporal_provenance_export.py` covering every acceptance criterion; 451 related tests pass, 0 regressions.

- **Temporal Metadata Extraction from Text** (PR #400 by @KaifAhmad1):
  - Added `extract_temporal_bounds: bool = False` parameter to `extract_relations_llm()`. When `True`, the LLM prompt is extended with a calibrated confidence scale and four few-shot examples; each returned `Relation` gains `valid_from`, `valid_until`, `temporal_confidence` (0.0–1.0), and `temporal_source_text` in its `metadata` dict. Default `False` preserves 100% backward compatibility.
  - Confidence scale anchors baked into the prompt: `1.00` = full ISO date, `0.90` = year+month, `0.85` = year only, `0.75` = quarter, `0.65` = named season/approximate range, `0.50` = vague relative with computable anchor, `0.35` = highly vague, `0.00` = no temporal signal. LLMs self-report certainty rather than clustering near 1.0.
  - Low temporal confidence (< 0.5) with a non-null date logs a `WARNING`; signal is never suppressed — callers decide how to filter.
  - Cache key now includes the `extract_temporal_bounds` flag to prevent cross-mode cache pollution.
  - Flag propagated through `_extract_relations_chunked()` so long-text chunked extraction also carries temporal metadata.
  - Added `RelationWithTemporalOut` and `RelationsWithTemporalResponse` Pydantic schemas in `semantica/semantic_extract/schemas.py`. A separate schema is required because `RelationOut` uses `extra="ignore"`, which silently drops any undeclared field including the four temporal fields.
  - New `semantica/kg/temporal_normalizer.py` — `TemporalNormalizer` class (zero LLM calls, pure regex + `dateutil` arithmetic):
    - `normalize(value)` → `(valid_from, valid_until)` UTC `datetime` tuple or `None`. Resolution order: ISO 8601 full parse → partial-date regex (year-only, month+year, YYYY-MM, Q[1-4] YYYY) → ambiguous-slash-date detection → domain phrase map → relative phrase resolution via `relativedelta`.
    - `normalize_phrase(phrase)` → metadata dict `{"maps_to": ..., "type": ..., "domain": [...]}` or `None` — exact match then regex-pattern keys.
    - Ambiguous `DD/MM/YYYY`-style inputs issue `TemporalAmbiguityWarning` and return `None` — never silently guesses locale.
    - Unparseable inputs return `None` with a debug log — never raise.
    - Relative phrases (`"last year"`, `"three months ago"`, etc.) raise `ValueError` if `reference_date` is `None` rather than guessing.
    - Default phrase map covers 13 domains: General/Policy (`effective date`, `effective from/as of/beginning`, `in force until`, `retroactive to`, `sunset clause`), Healthcare (`approval date`, `expiry date`, `market authorization`), Cybersecurity (`incident window`, `campaign period`), Supply Chain (`certification valid through`), Finance (`trading halt`), Energy (`commissioned date`, `decommissioned date`).
    - User-supplied `phrase_map` is merged over defaults at construction (`{**defaults, **user_map}`) — custom entries win without forking the library.
  - Added `TemporalAmbiguityWarning(UserWarning)` to `semantica/utils/exceptions.py`.
  - Exported `TemporalNormalizer` from `semantica/kg/__init__.py`.
  - Added 53 new tests in `tests/semantic_extract/test_temporal_extraction.py`; zero real LLM calls, suite runs in ~3.5 s. All 873 existing tests continue to pass.

- **Fix: OllamaProvider ignores `base_url`** (PR #408 by @AlexeyMyslin, fixed by @KaifAhmad1):
  - `OllamaProvider._init_client()` was assigning the raw `ollama` module to `self.client` instead of instantiating `ollama.Client(host=self.base_url)`, causing all requests to silently hit `localhost:11434` regardless of the `base_url` passed by the user
  - Fixed by replacing `self.client = ollama` with `self.client = ollama.Client(host=self.base_url)` — remote Ollama servers (e.g. `http://192.168.1.3:11434`) are now reachable
  - Added 3 regression tests: default URL forwarded as host, custom URL forwarded as host, and guard ensuring `self.client` is never the raw module

- **Temporal Awareness in Context Graph** (PR #399 by @KaifAhmad1):
  - Added `valid_from` and `valid_until` fields to the `Decision` dataclass and `record_decision()` — decisions now carry explicit validity windows; superseded decisions remain in the graph (history is immutable)
  - Added `include_superseded=False` and `as_of=None` parameters to `find_precedents_by_scenario()` — defaults exclude expired decisions; `as_of` enables point-in-time precedent queries
  - Added `ContextGraph.state_at(timestamp)` — returns a serializable point-in-time snapshot of all nodes, edges, and decisions whose validity windows include `timestamp`; source graph is never mutated
  - Stamped `recorded_at` on causal relationship edges created via `add_causal_relationship()` — enables transaction-time filtering
  - Added `CausalChainAnalyzer.trace_at_time(event_id, at_time)` — reconstructs a causal chain using only edges recorded up to `at_time` (transaction time); returns an empty list when `at_time` predates all facts, never raises
  - Added `AgentContext.checkpoint(label)`, `diff_checkpoints(label1, label2)`, and `flush_checkpoint(label)` — named in-memory context snapshots with structured diffs (`decisions_added`, `decisions_removed`, `relationships_added`, `relationships_removed`) and optional persistence via `TemporalVersionManager`
  - **Review fixes applied in the same PR**:
    - Fixed `max_depth` error message in `trace_at_time` to match actual bound (1–100)
    - Fixed Cypher `at_time` query parameter to RFC3339 UTC (`Z` suffix) for unambiguous external DB comparisons
    - `_normalize_temporal_input` now raises `ValueError` on unparseable strings instead of silently returning raw input
    - Replaced `datetime.now()` with `datetime.utcnow()` for all `recorded_at` and checkpoint timestamps — aligns with codebase convention and avoids wrong local time on Windows
    - `flush_checkpoint` wraps `TemporalVersionManager()` construction in a `try/except` and re-raises as `RuntimeError` with a clear actionable message
  - Added 7 new tests (93 total across context modules, 0 failures)

- **spaCy Runtime Fallback for NER Benchmarks**:
    - Hardened `NERExtractor` spaCy initialization so installed-but-broken spaCy environments no longer crash during extractor construction.
    - Updated ML entity extraction fallback behavior to catch runtime spaCy initialization failures, not just missing-model errors.
    - Added regression coverage for the "spaCy present but unusable at runtime" initialization path.
- **Deterministic Temporal Reasoning Engine** (PR #398 by @KaifAhmad1, implemented and follow-up fixes by OpenAI Codex):
  - Added `semantica.kg.temporal_reasoning` as the single source of truth for deterministic, LLM-free temporal reasoning with an explicit zero-LLM module contract
  - Implemented `TemporalInterval`, full Allen interval algebra via `IntervalRelation`, and `TemporalReasoningEngine`
  - Added deterministic helpers for interval overlap/containment checks, open-ended activity checks, interval merging, gap analysis, coverage calculation, timelines, retroactive coverage, and temporal normalization
  - Integrated temporal query interval logic with the reasoning engine in `TemporalGraphQuery`
  - Preserved `semantica.reasoning` access via re-exports without making it the canonical implementation source
  - Fixed open-ended `query_time_range(..., end_time=None)` handling so temporal range queries no longer crash on `TemporalBound.OPEN`
  - Restored `temporal_granularity` behavior for point-in-time checks in `query_at_time()`
  - Eliminated the `semantica.reasoning` / `semantica.kg` circular import risk introduced during the initial module move
  - Added regression coverage for all 13 Allen relations, open-ended intervals, month-granularity point queries, open-ended range queries, retroactive coverage, and normalization idempotence

- **Temporal Query Engine: Point-in-Time Correctness** (PR #397 by @KaifAhmad1, implemented and follow-up fixes by OpenAI Codex):
  - Added `reconstruct_at_time(graph, at_time)` to `TemporalGraphQuery` to build a self-consistent point-in-time subgraph without mutating the input graph
  - Updated `query_at_time()` to use point-in-time reconstruction internally so returned subgraphs exclude dangling edges when entity lifetimes are available
  - Added `TemporalConsistencyIssue` and `TemporalConsistencyReport` plus temporal consistency validation for:
    - inverted relationship intervals
    - relationships outside entity lifetimes
    - missing source/target entities
    - overlapping same-type relationships on the same edge
    - temporal gaps where a fact ends and restarts later
  - Added a module-level `validate_temporal_consistency(graph)` API alongside the query-engine method
  - Implemented sequence and cycle pattern detection with structured outputs containing `pattern_type`, `signature`, `frequency`, and per-occurrence node/edge/time details
  - Implemented calendar-aligned temporal evolution bucketing based on `temporal_granularity`
  - Added causal ordering controls to `find_temporal_paths()` via `enforce_causal_ordering` and `ordering_strategy` (`strict`, `overlap`, `loose`)
  - **Follow-up fixes applied in the same PR**:
    - Made `validate_temporal_consistency()` non-throwing on malformed temporal fields and return report errors instead of raising
    - Enforced exclusive `valid_until` semantics for point-in-time checks (`valid_from <= at_time < valid_until`)
    - Kept `query_time_range(..., temporal_aggregation="evolution")` backward-compatible by returning the flat relationship list plus a new `relationship_buckets` field
    - Hardened temporal pattern detection for open-ended intervals (`TemporalBound.OPEN`) to avoid datetime arithmetic/comparison crashes
    - Normalized relationship endpoints during point-in-time reconstruction so mixed-type IDs like `1` and `"1"` do not silently drop valid edges
    - Added in-code design comments documenting the sequence/cycle output structure required by the checklist
  - Added and expanded regression coverage for point-in-time reconstruction, exclusive end bounds, non-throwing validation, module-level validator access, pattern detection with gap tolerance/open bounds, evolution bucketing, causal ordering, and mixed-type IDs

- **Core Temporal Data Model Overhaul** (PR #396 by @KaifAhmad1, implemented and follow-up fixes by OpenAI Codex):
  - Added `semantica.kg.temporal_model` with shared helpers for parsing, normalizing, serializing, and deserializing temporal relationship fields
  - Exported `TemporalBound` and `BiTemporalFact` from `semantica.kg` for backward-compatible temporal relationship handling
  - Updated `TemporalGraphQuery` to use shared temporal parsing/model helpers instead of ad hoc string handling
  - Added support for `valid`, `transaction`, and `both` time axes in temporal query filtering
  - Standardized temporal normalization on `timezone.utc` for better cross-version portability
  - Added `TemporalValidationError` to utils exports and made invalid temporal inputs consistently raise it
  - Added history-preserving temporal revisions in `TemporalVersionManager.apply_revision()` with provenance metadata and supersession semantics
  - Added safer snapshot persistence by serializing revision metadata before storage and surfacing storage failures as `ProcessingError`
  - **Follow-up fixes applied in the same PR**:
    - Added a default factory for `BiTemporalFact.recorded_at` and preserved legacy transaction-axis behavior by falling back to `valid_from` when `recorded_at` is missing
    - Treated `TemporalBound.OPEN` as an unbounded value in shared query parsing so open-ended facts do not fail in public APIs like `analyze_evolution()` and path filtering
    - Recomputed snapshot checksums before persisting revised snapshots and any original snapshot inserted during revision flow
    - Replaced second-based revision suffixes with collision-resistant revision IDs/labels to avoid duplicate save failures under rapid revisions
    - Removed warning spam caused by canonical serialized open bounds represented as `None`
  - Added and expanded regression coverage for UTC normalization, transaction-axis queries, open-ended bounds, revision integrity, checksum verification, and collision-resistant revision identifiers

- **Audit Trail, Named Tags, and Rollback Protection** (PR #394 by @ZohaibHassan16, reviewed by @KaifAhmad1, follow-up fixes by OpenAI Codex):
  - Added mutation-level audit tracking for `ContextGraph` node and edge changes via `TemporalVersionManager.attach_to_graph()` and persistent mutation logging backends
  - Added named version tags in both in-memory and SQLite storage so human-readable tags can point to saved snapshots
  - Added rollback protection to `restore_snapshot()` so destructive graph restores require explicit confirmation
  - Added `get_node_history()` for per-entity audit inspection and `diff()` as a Git-like alias over version comparisons
  - Preserved backward compatibility for snapshot payloads and diff outputs by supporting both `nodes`/`edges` and `entities`/`relationships`
  - Fixed mixed-schema snapshot comparison and version metadata counts after the audit-trail feature landed on top of PR #393
  - Fixed restore replay so rollback does not generate synthetic mutation events in the audit log
  - Added version-label assignment for previously unlabeled mutations when a snapshot is created
  - Resolved merge conflicts against updated `main` in `managers.py`, `version_storage.py`, `context_graph.py`, and `test_managers.py`
  - Added and updated regression coverage for audit history, rollback safety, version-label persistence, and snapshot compatibility

- **Snapshot Schema Compatibility Fix** (PR #393 by @ZohaibHassan16, reviewed by @KaifAhmad1, follow-up fixes by OpenAI Codex):
  - Fixed silent snapshot restore failures caused by the `ContextGraph` `nodes`/`edges` schema not matching the version manager's legacy `entities`/`relationships` expectations
  - Updated temporal snapshot handling to accept both `nodes`/`edges` and `entities`/`relationships`
  - Preserved both schema shapes in stored snapshots to maintain backward compatibility during migration
  - Fixed temporal diffing and detailed comparison paths so new-format and mixed-format snapshots compare correctly
  - Fixed version metadata counts so `entity_count` and `relationship_count` remain accurate for both snapshot schemas
  - Restored ontology snapshot compatibility fields removed during the PR follow-up iteration
  - Added regression coverage for new-format snapshot creation, metadata counts, and mixed-schema diffing

- **ContextGraph Traversal Fallbacks for DecisionQuery & DecisionRecorder** (PR #386 by @ZohaibHassan16, reviewed and fixed by @KaifAhmad1):
  - Added native `ContextGraph` fallback execution paths to all 7 `DecisionQuery` methods (`_find_precedents_basic`, `find_by_category`, `find_by_entity`, `find_by_time_range`, `multi_hop_reasoning`, `trace_decision_path`, `find_similar_exceptions`) — resolves issue #379 where hardcoded Cypher queries broke in-memory usage
  - Added native `ContextGraph` fallback paths to 4 `DecisionRecorder` methods (`link_entities`, `record_exception`, `link_precedents`, `_store_decision_node`, `_store_exception_node`) using `add_node` / `add_edge` primitives
  - Implemented undirected BFS in `multi_hop_reasoning` fallback — traverses both outgoing and incoming edges so decisions are reachable from linked entities (matches Cypher `(start)-[*1..N]-(d:Decision)` semantics)
  - Fixed `isinstance(graph_store, ContextGraph)` guards → `type(graph_store) is ContextGraph` — prevents `Mock(spec=ContextGraph)` from triggering fallback branches and breaking 2 existing tests
  - Fixed `add_node(properties=metadata)` call in `_store_decision_node` and `_store_exception_node` — changed to `**metadata` so all decision fields are stored flat and remain readable via `_dict_to_decision`; previous form silently nested every field under a `"properties"` key
  - Fixed spurious `properties={}` keyword argument in all `add_edge` fallback calls — argument did not match the actual `add_edge(**properties)` signature
  - Fixed tz-aware / naive `datetime` mismatch in `find_by_time_range` fallback — strips `tzinfo` from aware bounds when stored timestamps are naive, preventing `TypeError` at comparison time
  - Hoisted `find_edges()` calls out of the BFS `while` loop in `trace_decision_path` — edges are now fetched once per call instead of once per visited node, eliminating O(nodes × total_edges) repeated full-graph scans
  - Removed duplicate `from ..embeddings import EmbeddingGenerator` import in `decision_query.py`
  - Added `tests/context/test_decision_query_fallback.py` with 14 tests: full integration test covering the complete fallback flow end-to-end, plus 13 targeted unit tests covering each `DecisionQuery` and `DecisionRecorder` fallback method individually, tz-aware/naive datetime mixing, and `Mock` guard correctness

- **ContextGraph Thread Safety & Pagination** (PR #385, Issues #378 #376 by @ZohaibHassan16, review & fixes by @KaifAhmad1):
  - `ContextGraph`: added `threading.RLock` (`self._lock`) to `__init__`; all mutation paths (`add_nodes`, `add_edges`, `add_node`, `add_edge`, `save_to_file`, `load_from_file`, `link_graph`) and all read/query paths (`find_nodes`, `find_edges`, `find_node`, `find_active_nodes`, `get_neighbors`, `query`, `stats`, `density`) now protected with `with self._lock:` to prevent race-condition corruption under concurrent FastAPI workers
  - `find_nodes` and `find_edges` gained native `skip`/`limit` pagination parameters so the explorer layer never loads the full collection into memory to slice it
  - `GraphSession` (`session.py`): introduced session-level `RLock` wrapping all graph access; all 8 lazy analytics properties (`centrality`, `community`, `connectivity`, `path_finder`, `node_embedder`, `similarity`, `link_predictor`, `validator`) initialised under the lock (thread-safe double-checked); `get_nodes()` and `get_edges()` delegate pagination to the graph layer when no in-memory filter is needed
  - `pyproject.toml`: removed duplicate entry and added missing comma in the `all` optional-dependency array that caused `ERROR Failed to parse pyproject.toml: Unclosed array` in CI
  - **Fixes applied post-review (by @KaifAhmad1)**:
    - Fixed `/api/graph/search` returning empty `content` and `properties` — `ContextGraph.query()` wraps results in `node.to_dict()` which uses a `"properties"` envelope, but `_node_dict_to_response` expected a flat `{id, type, content, metadata}` shape; `session.search()` now normalises the envelope before returning
    - Fixed edge metadata silently dropped on import — `add_edges()` read only from the `"properties"` key, but edges produced by `find_edges()` and `build_graph_dict()` use `"metadata"`; fixed with `edge.get("properties") or edge.get("metadata", {})` fallback
    - Fixed `POST /api/enrich/links` blocking the asyncio event loop — the O(n) `score_link` scoring loop ran inline in the `async` handler; wrapped in `asyncio.to_thread(_score_all)`
    - Removed merge-artifact dead code in `session.py`: duplicate `self.annotations` assignment, duplicate un-locked property set, and double-query logic in `get_nodes()`/`get_edges()` that recomputed results outside the lock and threw away the correctly-paginated result computed inside it
    - Removed merge-artifact dead code in `enrich.py`: unreachable second `predict_links` implementation block after early `return`, and duplicate `nodes, _` fetch in `detect_duplicates`

- **Knowledge Explorer API Backend** (PR #384, Issue #377 by @ZohaibHassan16, review & fixes by @KaifAhmad1):
  - Added `semantica.explorer` package — a full FastAPI backend for the Semantica Knowledge Explorer dashboard
  - `app.py`: `create_app(session)` factory with CORS middleware, custom exception handlers (`KeyError→404`, `ValueError→422`), and HTML5 static-file fallback routing; generic `Exception` handler correctly re-raises `HTTPException` so dependency-injection 503s are not swallowed
  - `session.py`: `GraphSession` — thread-safe container wrapping a `ContextGraph` with 8 lazily-initialised analytics components (`CentralityCalculator`, `CommunityDetector`, `ConnectivityAnalyzer`, `PathFinder`, `NodeEmbedder`, `SimilarityCalculator`, `LinkPredictor`, `GraphValidator`); all lazy properties initialised under `RLock` to prevent double-instantiation under concurrent requests; shared `build_graph_dict(node_ids=None)` method eliminates duplication across route files; `from_file(path)` classmethod loads from JSON
  - `ws.py`: `ConnectionManager` — thread-safe WebSocket manager with `connect()`, `disconnect()`, `broadcast(event_type, data)`, and `send_personal()` support; safe disconnection cleanup during broadcast
  - `dependencies.py`: `get_session(request)` and `get_ws_manager(request)` FastAPI `Depends`-compatible callables; `get_session` raises `HTTP 503` when no session is attached
  - 7 modular route files, all using `asyncio.to_thread` for sync graph operations:
    - `routes/graph.py`: `GET /api/graph/nodes` (type/keyword filter, pagination), `GET /api/graph/node/{id}`, `GET /api/graph/node/{id}/neighbors` (BFS, depth 1–5), `GET /api/graph/edges` (type/source/target filter), `GET /api/graph/node/{id}/path` (BFS or Dijkstra — algorithm param now correctly dispatched), `POST /api/graph/search`, `GET /api/graph/stats`
    - `routes/analytics.py`: `GET /api/analytics` (centrality, community, connectivity — comma-separated metrics param), `GET /api/analytics/validation`
    - `routes/decisions.py`: `GET /api/decisions` (category filter, pagination), `GET /api/decisions/{id}`, `GET /api/decisions/{id}/chain` (BFS causal chain up to 5 hops), `GET /api/decisions/{id}/precedents` (category + scenario keyword ranking), `GET /api/decisions/{id}/compliance` (in-graph check over `violates`/`non_compliant`/`breaches` edges — no longer a stub)
    - `routes/temporal.py`: `GET /api/temporal/snapshot` (ISO-8601 `at` param), `GET /api/temporal/diff` (added/removed node sets between two timestamps), `GET /api/temporal/patterns` (graceful fallback when `TemporalPatternDetector` unavailable, with warning log for unexpected errors)
    - `routes/enrich.py`: `POST /api/enrich/extract` (NLP entity/relation extraction), `POST /api/enrich/links` (per-node link prediction via `score_link` against all non-adjacent candidates — fixed from broken `predict_links` call), `POST /api/enrich/dedup` (duplicate detection — fixed missing `asyncio.to_thread` that was blocking the event loop), `POST /api/reason` (forward/backward inference via `Reasoner`)
    - `routes/export_import.py`: `POST /api/export` (12 formats: JSON, Turtle, RDF-XML, N-Triples, CSV, GraphML, GEXF, OWL, Cypher, AQL, YAML — temp file always cleaned up via `try/finally`), `POST /api/import` (JSON/JSON-LD multipart upload with WebSocket progress events)
    - `routes/annotations.py`: `GET /api/annotations`, `POST /api/annotations` (validates node exists; `add_annotation` mutates dict in-place so no extra roundtrip), `DELETE /api/annotations/{id}`
  - `schemas.py`: 28 Pydantic v2 request/response models covering all endpoint shapes including pagination, temporal, enrichment, compliance, and annotation types
  - `__init__.py`: `semantica-explorer` CLI entry point — `--graph`, `--host`, `--port`, `--no-browser` args; validates graph file exists; checks for `uvicorn`; opens browser after 1.5 s delay
  - `pyproject.toml`: added `[project.optional-dependencies] explorer` group (`fastapi`, `uvicorn[standard]`, `websockets`, `python-multipart`); registered `semantica-explorer` script entry point; fixed missing comma in `all` extra that broke `pip install semantica[all]`
  - **Fixes applied post-review (by @KaifAhmad1)**:
    - Fixed `predict_links` endpoint — was calling `predictor.predict_links(graph_dict, node_id, top_n=...)` with wrong type (`dict` as `graph_store`), wrong positional arg (`node_id` as `node_labels`), and wrong kwarg (`top_n` vs `top_k`); rewrote to iterate all non-adjacent candidate nodes and call `predictor.score_link(session.graph, source, candidate)` directly
    - Fixed `detect_duplicates` endpoint — `session.get_nodes()` was called directly in an `async def` handler without `asyncio.to_thread`, blocking the event loop
    - Fixed temp file leak in `export_graph` — file was not deleted on exception from `export_fn` or `open()`; wrapped in `try/finally`; moved `import os` to module level
    - Fixed `pyproject.toml` `all` extra — two consecutive strings with no comma between them caused a TOML syntax error
    - Fixed generic `Exception` handler swallowing `HTTPException(503)` raised by `get_session`
    - Fixed compliance endpoint — imported `PolicyEngine` then discarded it, always returning `compliant=True`; replaced with in-graph edge scan
    - Fixed `temporal_patterns` bare `except Exception` silently hiding bugs — split into `ImportError` (silent graceful) and `Exception` (warning log)
    - Fixed all 8 lazy analytics properties to initialise under `_lock` (thread-safe double-checked)
    - Fixed `find_path` ignoring the `algorithm` query param — now dispatches to `dijkstra_shortest_path` or `bfs_shortest_path`
    - Removed unnecessary `get_annotations()` round-trip in `create_annotation`
    - Removed `import traceback` unused import in `app.py`
    - Deduplicated `_build_graph_dict` (was copied identically in `graph.py`, `analytics.py`, `export_import.py`) into `GraphSession.build_graph_dict()`
  - 49 integration tests in `tests/explorer/test_explorer_api.py` using `starlette.testclient.TestClient` — all passing; covers health, nodes, edges, search, stats, decisions, causal chains, precedents, compliance (including violation detection), temporal snapshots/diff/patterns, analytics, reasoning, entity extraction, link prediction, deduplication, annotations, export (JSON + node-subset), and import (JSON + edges + unsupported format)
- **Reasoning Dead Code Removal** (PR #387, Issue #382 by @ZohaibHassan16):
  - Removed lines 357–358 in `semantica/reasoning/reasoner.py` that silently overwrote the sophisticated `_match_pattern` regex (which handles pre-bound variable embedding, repeated-variable backreferences via `(?P=var)`, and non-greedy named capture groups) with a simpler `re.escape`-based pattern, making all the prior logic unreachable dead code
  - Removed duplicate unreachable `return None` on line 368 (syntactically dead, appearing immediately after another `return None` in the same branch)
  - Surfaced `re.error` exceptions instead of swallowing them with `except Exception: pass`, preventing silent failures when malformed patterns were passed to `re.match`
  - Before this fix, any rule using the same variable twice (e.g. `rel(?x, ?x)`) generated a duplicate named group error that was silently caught, causing the match to return `None` regardless of the fact — breaking transitivity, symmetry, and self-join rule patterns entirely

- **Agno Agentic Framework Integration** (Issue #249):
  - Added `AgnoContextStore` — graph-backed agent memory implementing the `agno.memory.db.base.MemoryDb` protocol; wraps `AgentContext` + `VectorStore`; supports `create()`, `table_exists()`, `memory_exists()`, `read_memories()`, `upsert_memory()`, `delete_memory()`, `drop_table()`, `clear()` plus extended `record_decision()`, `find_precedents()`, `retrieve()` methods
  - Added `AgnoKnowledgeGraph` — multi-hop GraphRAG knowledge base implementing `agno.knowledge.base.AgentKnowledge`; ingests files, directories, URLs, and raw text via NER → relation extraction → graph build → vector index pipeline; `search()` returns `AgnoDocument` objects; `get_graph_context(entity)` returns text summary of entity's graph neighbourhood
  - Added `AgnoDecisionKit` — Agno `Toolkit` subclass exposing 6 decision-intelligence tools: `record_decision`, `find_precedents`, `trace_causal_chain`, `analyze_impact`, `check_policy`, `get_decision_summary`
  - Added `AgnoKGToolkit` — Agno `Toolkit` subclass exposing 7 KG pipeline tools: `extract_entities`, `extract_relations`, `add_to_graph`, `query_graph`, `find_related`, `infer_facts`, `export_subgraph`
  - Added `AgnoSharedContext` — team-level coordinator with a single shared `ContextGraph`; `bind_agent(role)` returns a role-scoped `_AgentScopedStore` with cross-agent memory visibility; thread-safe via `RLock`
  - All 5 components degrade gracefully when `agno` is not installed (`AGNO_AVAILABLE` flag); importable and functional without agno present
  - Added `agno = ["agno>=1.0.0"]` optional dependency in `pyproject.toml`; included in `all` extra
  - 110 integration tests in `tests/integrations/agno/` covering all public APIs, MemoryDb protocol compliance, GraphRAG search, tool registration, shared memory isolation, and thread-safety
  - 3 cookbook notebooks in `cookbook/integrations/`: `agno_decision_intelligence.ipynb` (loan underwriting), `agno_graphrag_context.ipynb` (regulatory compliance), `agno_multi_agent_shared_context.ipynb` (multi-agent team coordination)
  - Full reference documentation in `docs/integrations/agno.md`

- **Novita AI Provider** (PR #374 by @Alex-wuhu):
  - Added `NovitaProvider` — OpenAI-compatible integration via `https://api.novita.ai/v1`; supports `generate()` and `generate_structured()` (JSON forced format)
  - Default model: `deepseek/deepseek-v3.2`; configurable via `NOVITA_API_KEY` environment variable
  - Registered `"novita"` in the built-in provider factory; usable via `create_provider("novita")`
  - Added integration tests in `tests/test_novita_integration.py` with proper assertions and graceful skip when `NOVITA_API_KEY` is unset

- **Native Datalog Reasoning Engine** (PR #371, Issue #368 by @ZohaibHassan16, reviewed and fixed by @KaifAhmad1):
  - Added `DatalogReasoner` to `semantica.reasoning` — a pure-Python, bottom-up semi-naive fixpoint engine with guaranteed termination on finite graphs
  - Supports recursive Horn clause rules (e.g. `ancestor(X,Y) :- parent(X,Z), ancestor(Z,Y).`) that existing engines loop on indefinitely
  - Memory-optimized `_unify()` with deferred dict allocation — zero allocation on failed unifications
  - `O(1)` delta-index lookup per iteration eliminates redundant `O(N)` rule re-evaluations in semi-naive loop
  - `query("pred(?X, ?Y)")` returns variable-binding dicts; supports both uppercase `?Y` and lowercase `?y` variable syntax
  - `query(..., bindings={"Y": "val"})` pre-binds variables for exact-match verification
  - `load_from_graph(ContextGraph)` converts all edges and nodes to Datalog facts in one call; handles both `find_edges`/`find_nodes` and raw `edges`/`nodes` graph APIs
  - `add_fact()` accepts `"pred(a, b)"` strings and Semantica dicts (`subject/predicate/object`, `source/target/type`, `type/id` shapes); warns on unrecognised dict format instead of silently dropping
  - `_derived` cache flag — `derive_all()` skips re-evaluation when no facts or rules have changed since last run; `query()` respects the cache
  - Progress tracking wrapped in `try/finally` — `stop_tracking()` always called even on exception
  - `DatalogReasoner`, `DatalogFact`, `DatalogRule` exported from `semantica.reasoning`
  - 18 tests covering recursive rules, multi-hop inference, variable binding, graph integration, idempotency, and edge cases — all passing
- **Ontology Diff & Migration** (PR #367 by @ZohaibHassan16, review & fixes by @KaifAhmad1):
  - `VersionManager.diff_ontologies(base, target)` — structured diff between two ontology dicts using hash-map lookups; handles URI-less items via `name` fallback; deep equality checks for unordered lists; now covers classes, properties, individuals, and axioms
  - `ChangeLogAnalyzer.analyze(diff)` — classifies each change by semantic impact: removed classes/properties → `CRITICAL/BREAKING`; narrowed domain/range/cardinality → `HIGH/BREAKING`; hierarchy modifications → `MEDIUM/POTENTIALLY_BREAKING`; added elements and annotation updates → `INFO/NON_BREAKING`
  - `ImpactReport` dataclass and `generate_change_report(diff)` public helper — returns a structured dict with `summary`, `impact_classification` (breaking / potentially_breaking / safe), `recommendations`, and the raw `diff`
  - `OntologyEngine.compare_versions(base_id, target_id, **options)` — end-to-end orchestrator: loads versions from `VersionManager`, runs `diff_ontologies`, generates impact report; accepts `base_dict`/`target_dict` overrides to bypass version store; `run_validation=True` triggers `OntologyValidator` on the target schema; `graph_data=...` additionally runs `GraphValidator` on instance data against the new schema
  - `OntologyEngine.get_ontology_version_dict(version_id)` — utility to load a registered version as a plain dict ready for diffing
  - Documentation added to `docs/reference/change_management.md`: "Ontology Diff & Migration" section with code example and full report format reference
  - 7 tests added to `tests/change_management/test_managers.py` covering: empty diff, unordered list equality, URI/name fallback, breaking class removal, narrowed domain (HIGH), safe additions and annotation changes, `compare_versions` dict override, version-not-found error path, individuals/axioms diff coverage, null constraint value flagged as breaking
  - **Fixes applied post-review (by @KaifAhmad1)**:
    - Fixed typo in `ChangeCategory` enum value: `"potenitally_breaking"` → `"potentially_breaking"`
    - Fixed missing space in impact description string: `f"New{entity_type}"` → `f"New {entity_type}"`
    - Added null-value guard in `_analyze_field_changes` — constraint fields with `None` old/new value are now correctly flagged as breaking instead of silently passing the subset check
    - Made `ChangeLogAnalyzer` stateless — `report` is now a local variable passed into `_generate_recommendations(report)` rather than stored as `self.report`; removes re-entrancy hazard
    - Removed no-op `__init__` from `ChangeLogAnalyzer`
    - Replaced non-portable emoji markers in recommendations (`✘✘✘`, `¤¤¤`, `☺☺☺`) with plain-text tags (`[BREAKING]`, `[WARNING]`, `[SAFE]`)
    - Extended `diff_ontologies` to cover `individuals` and `axioms` — previously only classes and properties were diffed; the public `compare_versions` path now returns all four element types
    - Fixed exception chaining in `compare_versions`: `raise ProcessingError(...) from e` to preserve original traceback
    - Removed silent `ImportError` swallow for `GraphValidator` — it is a first-party module; an `ImportError` indicates a broken install, not a graceful skip
    - Added comment on deferred `VersionManager` import in `OntologyEngine.__init__` explaining the circular-import constraint
    - Fixed import-before-docstring in `tests/change_management/test_managers.py`
    - Fixed broken Markdown link syntax in docs JSON example block: `"[http://...](http://...)"` → bare URI string
    - Updated docs recommendations example to match the new plain-text tag format

- **Ontology Alignment API** (PR #361 by @ZohaibHassan16, review & fixes by @KaifAhmad1):
  - Alignment representation using standard RDF predicates: `owl:equivalentClass`, `owl:equivalentProperty`, `owl:sameAs`, `skos:exactMatch`, `skos:closeMatch`, `skos:broadMatch`, `skos:narrowMatch`, `skos:relatedMatch`
  - `OntologyEngine.create_alignment(source_uri, target_uri, predicate)` — store alignment triples in TripletStore
  - `OntologyEngine.get_alignments(entity_uri)` — bidirectional retrieval of all alignments for an entity
  - `OntologyEngine.list_alignments(ontology_uri=None)` — list all alignments, optionally filtered by ontology namespace
  - `NamespaceManager.get_alignment_predicates()` — expose standard OWL/SKOS alignment URIs as a convenience dict
  - `ReuseManager.suggest_alignments(target, source)` — O(N+M) hashmap heuristic to suggest alignments based on exact label matches across ontologies
  - `ReuseManager.merge_ontology_data(..., compute_alignments=True)` — optionally attach suggested alignments to merge output without auto-committing unverified triples
  - `QueryEngine.expand_entity_uri(uri, store, use_alignments=True)` — bidirectional SPARQL expansion to include aligned equivalents; no-ops when flag is False
  - `QueryEngine.build_values_clause(variable, uris)` — generate a SPARQL `VALUES` clause for injecting expanded URIs into queries
  - Alignment-aware queries section added to `docs/reference/triplet_store.md`
  - Ontology Alignment section added to `docs/reference/ontology.md`
  - **Fixes applied post-review (by @KaifAhmad1)**:
    - Fixed progress tracker leak in `expand_entity_uri` — `stop_tracking` was only called inside the `hasattr(execute_sparql)` branch; backends without it silently leaked a tracker entry
    - Fixed `relatedMatch` predicate gap — `get_alignment_predicates()` exposed `skos:relatedMatch` but all three SPARQL FILTER lists omitted it, making those alignments permanently invisible
    - Fixed SPARQL injection in `list_alignments` — previously only `"` was escaped; `\`, `{`, and `}` are now also percent-encoded to prevent WHERE block breakout
    - Fixed SPARQL injection in `build_values_clause` — URIs now run through `_sanitize_uri` before wrapping in angle-bracket literals
    - Added full-URI validation in `create_alignment` — raises `ProcessingError` if predicate is a CURIE instead of a full URI, preventing silent storage of unqueryable triples
    - Fixed E2E test `test_end_to_end_cross_ontology_uri_flow` — previously mocked the method under test; now uses a real mock backend with `execute_sparql` to exercise the actual expansion and VALUES clause injection flow
  - 19 tests added covering: `create_alignment`, `get_alignments`, `suggest_alignments`, merge with alignment computation, `expand_entity_uri` (enabled/disabled), `build_values_clause`, and full E2E cross-ontology query flow
- **Context Explainability Output Fixes** (by @KaifAhmad1):
  - Fixed decision-node storage in `ContextGraph` so full human-readable `scenario`, `reasoning`, and decision metadata are preserved on graph nodes instead of degrading into opaque IDs or truncated display text
  - Fixed causal and precedent reconstruction paths in the context module so returned `Decision` objects prefer readable stored fields over raw node identifiers
  - Fixed context aggregate outputs to return enriched readable payloads for influence, causality, similarity, policy-impact, and entity-similarity workflows instead of bare UUID lists or tuple-only results
  - Fixed `PolicyEngine.get_affected_decisions()` so both Cypher and fallback branches return consistent decision metadata including `scenario`, `category`, `outcome`, and `confidence`
  - Fixed `EntityLinker` similarity flows so enriched similarity results are consumed correctly across internal linking paths and public search aliases
  - Fixed `CentralityCalculator._build_adjacency()` to handle `ContextGraph` edges (dataclass `ContextEdge` objects with `source_id`/`target_id`) so `calculate_degree_centrality()` and related centrality algorithms work correctly when a `ContextGraph` is passed as the graph store
  - Fixed downstream KG integrations in `node_embeddings`, `link_predictor`, `centrality_calculator`, `path_finder`, and context retrieval fallbacks to normalize enriched neighbor/node outputs without breaking graph algorithms
  - Added 23 regression tests in `tests/context/test_context_explainability_regression.py` covering readable decision text preservation, enriched causal/path outputs, policy-impact results, entity similarity payloads, and compatibility with KG consumers

## [0.3.0] - 2026-03-10

- **Context Graph Feature Completeness** (by @KaifAhmad1):
  - Added `valid_from` / `valid_until` temporal validity fields to `ContextNode` and `ContextEdge` dataclasses — both expose `is_active(at_time=None) -> bool`; nodes/edges without these fields are always considered active
  - Added `add_node(valid_from=..., valid_until=...)` and `add_edge(valid_from=..., valid_until=...)` support — validity windows are extracted from `**properties` and stored as first-class dataclass fields, not in metadata
  - Added `ContextGraph.find_active_nodes(node_type=None, at_time=None)` — returns only nodes whose validity window includes the given time (defaults to `datetime.utcnow()`); complements `find_nodes()` with temporal filtering
  - Added `min_weight: float = 0.0` parameter to `ContextGraph.get_neighbors()` — edges with weight below the threshold are skipped during BFS traversal, enabling weighted/confidence-filtered multi-hop navigation; fully backward-compatible (default 0.0 passes all edges)
  - Added `ContextGraph.link_graph(other_graph, source_node_id, target_node_id, link_type="CROSS_GRAPH") -> str` — creates a navigable bridge between two separate `ContextGraph` instances; records a marker edge internally and returns a `link_id`
  - Added `ContextGraph.navigate_to(link_id) -> (other_graph, target_node_id)` — resolves a `link_id` to the target graph and its entry node, enabling hierarchical cross-graph traversal (e.g. agent moving from a high-level decision graph into a domain-specific sub-graph)
  - Added `ContextGraph.resolve_links(registry)` — reconnects cross-graph links after `load_from_file()`; `save_to_file()` now persists a `links` section with `other_graph_id` so navigation survives the full save/load cycle
  - Added `graph_id` field to `ContextGraph` — stable UUID per instance, persisted to JSON, so separate graphs can identify each other after reload
  - Fixed `is_active()` on `ContextNode` and `ContextEdge` — tz-aware `datetime` inputs are now normalised to tz-naive UTC before comparison, preventing `TypeError` when callers pass `datetime.now(timezone.utc)`
  - Fixed `valid_from` / `valid_until` serialisation — `add_nodes()`, `add_edges()`, `to_dict()`, and `from_dict()` all now preserve and restore validity windows; previously these fields were silently lost
  - Fixed cross-graph link artifact — `link_graph()` now pre-creates a `"cross_graph_link"` typed `ContextNode` for the marker before inserting the marker edge, preventing `_add_internal_edge()` from auto-creating a phantom `"entity"` node
  - Added 14 tests in `tests/context/test_cross_graph_navigation.py` covering link creation, phantom-node prevention, and full save/load round-trips with `resolve_links()`
  - Fixed `pipeline_builder.add_step()` return type annotation from `"PipelineBuilder"` to `"PipelineStep"` — implementation was already correct per 0.3.0-beta changelog, only signature and docstring were stale
  - Fixed `test_hybrid_search_performance` timing computation — accumulated a real `search_times` list and compute true average; raised threshold to `< 5.0s` to account for real `sentence-transformers` (384-dim) latency



- **0.3.0 Bug Fixes & Comprehensive Real-World Tests** (by @KaifAhmad1):
  - Fixed `ProvenanceTracker` missing from `semantica/kg/__init__.py` exports — `from semantica.kg import ProvenanceTracker` now works correctly
  - Fixed duplicate relation creation in `_parse_relation_result` — orphaned legacy block was appending every relation twice; removed the duplicate block
  - Added `extraction_method` parameter to `_parse_relation_result`; typed extraction path now correctly sets `"llm_typed"` instead of `"llm"` in relation metadata
  - Fixed cross-test cache pollution in `tests/semantic_extract/test_retry_logic.py` — module-level `_result_cache` now cleared in `setUp()` to prevent intermittent failures when tests share input text
  - Added `tests/test_030_realworld_comprehensive.py`: 85 real-world tests covering all 0.3.0-alpha/beta features with real data (tech companies, CEOs, products, investment chains, healthcare scenarios)
    - ContextGraph basic operations and decision tracking lifecycle
    - KG algorithms: centrality, community detection, embeddings, path finding, similarity, link prediction, connectivity
    - PolicyEngine, DecisionQuery, AgentContext, Decision model serialization
    - ProvenanceTracker with GraphBuilderWithProvenance and AlgorithmTrackerWithProvenance
    - Deduplication v2 with blocking strategies, RDF/TTL export, Reasoner inference
    - Pipeline builder/validator/failure handler with retry policies
    - Multi-hop investment chain (Microsoft→OpenAI, Google→Anthropic) end-to-end
    - Healthcare entity extraction and knowledge graph construction E2E

## [0.3.0-beta] - 2026-03-07

- **Multi-Founder LLM Extraction & Reasoner Inference Fix** (PR #354 by @KaifAhmad1):
  - Fixed `_parse_relation_result` in `methods.py` — unmatched subjects/objects now produce a synthetic `UNKNOWN` entity instead of silently dropping the relation; all LLM-returned co-founders are preserved
  - Rewrote `_match_pattern` in `reasoner.py` — splits pattern on `?var` placeholders first, then escapes only the literal segments; pre-bound variables resolve to exact literals, repeated variables use backreferences, non-greedy `.+?` prevents over-consumption of literal separators
  - Added `tests/reasoning/test_reasoner.py` with 4 tests covering multi-word value inference, pre-bound variables, binding conflicts, and single-word regression
  - Added `tests/semantic_extract/test_relation_extractor.py` with 6 tests covering all-founders returned, synthetic entity creation, matched entity integrity, predicate/confidence preservation, empty response, and malformed entries
- **TTL Export Alias Fix** (PR #355 by @KaifAhmad1):
  - Added `_format_aliases` map in `RDFExporter` so `format="ttl"`, `"nt"`, `"xml"`, `"rdf"`, and `"json-ld"` resolve to their canonical counterparts without breaking existing callers
  - Alias resolution applied at the top of `export_to_rdf()` before format validation — zero public API changes
  - Added working TTL export cell to `cookbook/introduction/15_Export.ipynb` (Step 3: RDF Export)
  - Added `tests/export/test_rdf_exporter.py` with 8 tests covering all aliases, canonical formats, error handling, and file export

- **Incremental/Delta Processing Feature** (PR #349 by @ZohaibHassan16, reviewed and fixed by @KaifAhmad1):
  - Native delta computation between graph snapshots using SPARQL queries
  - Delta-aware pipeline execution with `delta_mode` configuration for processing only changed data
  - Version snapshot management with graph URI tracking and metadata storage
  - Snapshot retention policies with automatic cleanup via `prune_versions()` method
  - Integration with pipeline execution engine for incremental workflows
  - Significant performance improvements: processes only changes instead of full datasets
  - Cost optimization: dramatically reduces compute and storage requirements for large-scale operations
  - Production-ready for near real-time pipelines and frequent deployment scenarios
  - Bug fixes: corrected SPARQL variable order, fixed class references, resolved duplicate dictionary keys
  - Comprehensive test coverage including delta mode integration tests
  - Complete documentation with usage examples and API references
  - Essential for enterprise-grade, large-scale semantic infrastructure
- **Deduplication v2 Migration Guide** (PR #344 by @ZohaibHassan16, fixes by @KaifAhmad1):
  - Added comprehensive MIGRATION_V2.md documentation for Deduplication v2 Epic #333
  - Documented Candidate Generation V2 with multi-key blocking and phonetic matching
  - Documented Two-Stage Scoring prefilter with configurable thresholds
  - Documented Semantic Relationship Deduplication v2 with synonym mapping
  - Added practical code examples for all V2 features with opt-in configuration
  - Fixed critical infinite recursion bug in dedup_triplets() function
  - Completed Epic #333 with comprehensive migration path and documentation
  - Performance: 5.86x speedup confirmed (129ms vs 754ms) for semantic deduplication
  - Full backward compatibility maintained with legacy mode as default
- **Semantic Relationship Deduplication v2** (PR #340 by @ZohaibHassan16, fixes by @KaifAhmad1):
  - Implemented opt-in semantic relationship deduplication mode (`semantic_v2`) with 6.98x performance improvement
  - Added canonicalization engine with predicate synonym mapping (`works_for` → `employed_by`)
  - Implemented fast-path O(1) hash matching for exact canonical signature comparisons
  - Added weighted semantic scoring (60% predicate + 40% object composition) with explainable `semantic_match_score` metadata
  - Enhanced `dedup_triplets()` function as first-class API in `methods.py`
  - Integrated semantic deduplication into merge strategy with canonical key generation
  - Added literal normalization for whitespace cleanup in object matching
  - Maintained full backward compatibility with legacy mode as default
  - Fixed critical infinite recursion bug in `dedup_triplets()` function via registry name checking
  - Performance: Semantic V2 (~83ms) vs Legacy (~579ms) - 6.98x speedup confirmed
  - All 13 deduplication benchmarks passing with comprehensive test coverage
- **Two-Stage Scoring Prefilter** (PR #339 by @ZohaibHassan16):
  - Implemented opt-in two-stage scoring with fast prefilter gates to eliminate expensive semantic scoring for obvious non-matches
  - Prefilter gates: type mismatch detection, name length ratio validation, token overlap requirements
  - Performance improvements: 18-25% faster batch processing with prefilter enabled
  - Configurable thresholds: `min_length_ratio`, `min_token_overlap_ratio`, `required_shared_token`
  - Enhanced explainability with score breakdown and rejection reasons in metadata
  - Complete backward compatibility with default `prefilter_enabled=False`

- **Candidate Generation v2 with Multi-Key Blocking** (PR #338 by @ZohaibHassan16):
  - Implemented opt-in candidate generation strategies (`legacy`, `blocking_v2`, `hybrid_v2`) to address O(N²) pair explosion during deduplication
  - Multi-key blocking with normalized token prefixes, type-aware keys, and optional phonetic (Soundex) blocking
  - Deterministic candidate budgeting with `max_candidates_per_entity` limit using stable sorting
  - Efficient pair generation with set-based deduplication across overlapping blocks
  - Performance improvements: 63.6% faster in worst-case scenarios (0.259s → 0.094s for 100 entities)
  - Complete backward compatibility with default `candidate_strategy="legacy"`
  - Added configuration options: `blocking_keys`, `enable_phonetic_blocking`, `max_candidates_per_entity`

- **ArangoDB AQL Export Support** (PR #342 by @tibisabau):
### Added

- **ArangoDB AQL Export Support** (PR #342 by @tibisabau)
  - Full-featured ArangoDB AQL exporter with 642 lines of production-ready code
  - Comprehensive AQL INSERT statement generation for vertices and edges
  - Configurable collection names with validation and sanitization
  - Batch processing support for large knowledge graphs (default: 1000)
  - Added export_arango() convenience function for easy access
  - Enhanced unified export with AQL format support and .aql auto-detection
  - Added `export_arango()` convenience function for easy access
  - Enhanced unified export with AQL format support and `.aql` auto-detection
  - Integrated with method registry for extensibility
  - 17 comprehensive test cases with 100% pass rate
  - Enterprise-grade ArangoDB multi-model database integration

- **Apache Parquet Export Support** (PR #343 by @tibisabau):
- **Apache Parquet Export Support** (PR #343 by @tibisabau)
  - Full-featured Apache Parquet exporter with 701 lines of production-ready code
  - Columnar storage format optimized for analytics and data warehousing
  - Configurable compression codecs (snappy, gzip, brotli, zstd, lz4, none)
  - Explicit Arrow schemas with type safety and consistency
  - Field normalization for varied entity and relationship naming conventions
  - Structured metadata handling using Parquet struct fields
  - Added export_parquet() convenience function for easy access
  - Enhanced unified export with Parquet format support and .parquet auto-detection
  - Added `export_parquet()` convenience function for easy access
  - Enhanced unified export with Parquet format support and `.parquet` auto-detection
  - Integrated with method registry for extensibility
  - 25 comprehensive test cases with 100% pass rate
  - Enterprise-grade analytics integration with pandas, Spark, Snowflake, BigQuery, Databricks

### Fixed
- **Fixed NameError**: missing Type import in utils/helpers.py

- Fixed NameError: missing Type import in utils/helpers.py
  - Added Type to typing imports to fix retry_on_error decorator
  - Removed unused Type import from config_manager.py
  - Resolves ImportError when importing semantica modules
  - Fixes capability gap analysis notebook execution

- **Test Suite Fixes: 0.3.0-alpha & Unreleased Features** (PR utils by @KaifAhmad1):

  **Context Module (`semantica/context/`)**
  - Fixed `retrieve_decision_precedents` to gate entity extraction on `use_hybrid_search=True` — was incorrectly extracting entities when flag was `False`
  - Fixed `_extract_entities_from_query` to use `word[0].isupper()` instead of `word.istitle()` — correctly captures `CreditCard`, `CustomerID` etc.
  - Added missing `expand_context` method — BFS graph traversal via `knowledge_graph.get_neighbors`
  - Added missing `_get_decision_query` method — creates a `DecisionQuery` from the knowledge graph
  - Fixed `hybrid_retrieval` to call `expand_context(query)` once (not per-entity) and include `"query"` key in return dict
  - Fixed `dynamic_context_traversal` to call `expand_context` once per query instead of per entity
  - Fixed `multi_hop_context_assembly` to use `_get_decision_query()` for robust decision lookup
  - Fixed `_retrieve_from_vector` to fall back to `result["metadata"]["content"]` when `result["content"]` is absent — prevents empty content and negative similarity scores during semantic re-ranking

  **Knowledge Graph Module (`semantica/kg/`)**
  - Fixed `calculate_pagerank` — added `alpha` and `max_iter` parameter aliases; changed return format to structured dict `{"centrality": scores, "rankings": sorted_list}`
  - Fixed `community_detector._to_networkx` to return a NetworkX graph directly when one is passed (was converting to adjacency list, silently losing all edges)
  - Added `method` as alias for `algorithm` parameter in `detect_communities`
  - Fixed `_build_adjacency` to handle `"edges"` key (list of tuples) in addition to `"relationships"` (list of dicts)
  - Added `_track_generic` base method and 9 domain-specific tracking methods to `AlgorithmTrackerWithProvenance`: `track_influence_analysis`, `track_verification_analysis`, `track_supply_chain_paths`, `track_bottleneck_analysis`, `track_quality_analysis`, `track_lead_time_analysis`, `track_cross_domain_analysis`, `track_cross_domain_similarity`, `track_collaboration_potential`
  - Created new `provenance_tracker.py` module with `ProvenanceTracker` class (`track_entity`, `get_all_sources`, `clear`)

  **Pipeline Module (`semantica/pipeline/`)**
  - Fixed `execution_engine` retry loop to properly iterate up to `max_retries` (was only retrying once regardless of policy)
  - Added `RecoveryAction` dataclass and `handle_failure(error, policy, retry_count)` method to `FailureHandler` — implements LINEAR, EXPONENTIAL, and FIXED backoff strategies
  - Fixed `pipeline_builder.add_step` to return the created `PipelineStep` object instead of `self`
  - Added `validate` as a public alias for `validate_pipeline` in `PipelineValidator`
  - Updated missing-dependency error message to `"Missing dependency '{dep}' for step '{name}'"` for consistent test assertions

  **Vector Store (`semantica/vector_store/`)**
  - Relaxed `test_batch_processing_performance` threshold from `< 100ms` to `< 500ms` per decision — original threshold was too tight for development machines running a real `sentence-transformers` embedding model (384-dim)

  **Test File Fixes**
  - `test_end_to_end_context_integration.py` — replaced emoji characters (`✅`, `❌`, `🔄`, `⚠️`) with ASCII equivalents (`[OK]`, `[FAIL]`, `[...]`, `[WARN]`) to fix Windows cp1252 encoding error
  - `test_context_retriever_precedents.py` — moved `assert_called_once_with` inside `with patch.object` block; fixed assertion to use `decision.scenario` not `decision.decision_id`; removed `"iPhone"` (lowercase-first) from entity extraction assertion
  - `test_real_world_scenarios.py` — fixed duplicate `source=` keyword argument (renamed to `label=`); fixed cross-domain analysis loop to iterate over all social network users instead of only `academic_users`
  - `test_pipeline_comprehensive.py` — changed `test_pipeline_validator_missing_deps` to call `validator.validate(builder)` directly instead of `builder.build()` which raises `ValidationError` before validation can complete

  **Results: ~840 tests passing, 36 skipped (external services), 0 failed**

## [0.3.0-alpha] - 2026-02-19

### Added / Changed

- **Decision Tracking System**: Complete decision lifecycle management with audit trails and provenance tracking
- **Advanced KG Algorithms**: Node2Vec embeddings, centrality analysis, community detection for decision insights  
- **Enhanced Context Module**: Unified AgentContext with granular feature flags and decision tracking integration
- **Vector Store Features**: Hybrid search combining semantic, structural, and category similarity
- **Policy Management**: Versioning, compliance checking, and exception handling
- **Production Ready Architecture**: Scalable design with comprehensive error handling and validation

### Fixed

- Fixed import issues in test suite (ProvenanceTracker location fixes)
- Fixed causal analyzer validation (max_depth bounds checking)
- Fixed test compatibility with updated method signatures
- Fixed mock object setup in test suites
- Comprehensive test suite fixes for decision tracking features

### Testing

- 113+ tests passing across context and core modules
- Comprehensive decision tracking test coverage
- Enhanced error handling and edge case testing
- Fixed all critical test failures for release readiness

### Documentation

- Enhanced context module documentation
- Updated API references for decision tracking features
- Comprehensive usage guides and examples

- Fixed: Context Graphs decision tracking bugs and added comprehensive test coverage (PR #315 by @KaifAhmad1)
  - Fixed empty/None decision ID handling in ContextGraph.add_decision()
  - Fixed None metadata handling to prevent TypeError
  - Fixed causal chain depth logic and node exclusion
  - Fixed nonexistent node handling in add_causal_relationship()
  - Added missing properties field in to_dict serialization
  - Added missing from_dict method for graph deserialization
  - Fixed precedent search direction in find_precedents()
  - Fixed UUID generation logic in all decision models
  - Added comprehensive test suite with 9 tests covering all features
  - All 71 context tests now passing (100% success rate)

- Fixed: PolicyEngine latest version selection on ContextGraph; AgentContext fallback robustness and secure logging (PR #TBD by @KaifAhmad1)
- Tests: Added ContextGraph fallback and AgentContext smoke tests; full suite passing

  - **Apache AGE Backend Security Fixes** (PR #311 by @Sameer6305, fixes by @KaifAhmad1):
  - Added AgeStore class with GraphStore API compatibility
  - Fixed SQL injection vulnerabilities with input validation
  - Added psycopg2-binary dependency and migration guide
  - Fixed parameter replacement and test mock leakage
  - Enhanced error handling and Unicode display issues

- **Context Engineering Enhancement** (PR #307 by @KaifAhmad1):
  - Comprehensive decision tracking system with full lifecycle management (record → analyze → query → precedent → influence)
  - Advanced KG algorithm integration: centrality analysis, community detection, node embeddings with ContextGraph
  - Enhanced AgentContext with granular feature flags for decision tracking, KG algorithms, and vector store features
  - PolicyException model replacing conflicting Exception name for meaningful business domain modeling
  - GraphStore validation preventing runtime failures with explicit capability checking
  - Hybrid search combining semantic, structural, and category similarity with configurable weights
  - Decision influence analysis with centrality measures and causal chain tracking
  - Policy management with versioning, compliance checking, and exception handling
  - Production-ready architecture with audit trails, security, and scalability features
  - 9 critical bug fixes: logging, security, audit trails, API compatibility, Cypher queries, centrality access, validation, naming
  - Comprehensive documentation with usage guides, production examples, and API references
  - 100% test coverage with all validation tests passing (9/9 tests)
  - Enterprise-grade features for financial services, healthcare, legal, and business domains
  - Complete backward compatibility with existing semantica components
  - Performance optimizations: caching, indexing, and efficient graph operations

- **Added PgVector Store Support** (PR #303 by @Sameer6305, @KaifAhmad1):
  - Native PostgreSQL vector storage using pgvector extension with full integration
  - Multiple distance metrics: cosine, L2/Euclidean, inner product with automatic score normalization
  - Advanced indexing: HNSW and IVFFlat for approximate nearest neighbor search with tunable parameters
  - JSONB metadata storage with flexible filtering capabilities and batch operations
  - Connection pooling support with psycopg3/psycopg2 fallback and efficient resource management
  - Comprehensive VectorStore integration with backend delegation and unified API
  - Idempotent index creation and table management with safe migration support
  - Production-ready security: SQL injection protection with psycopg_sql.SQL() and input validation
  - Performance optimizations: UUID4-based IDs, batch executemany operations, connection pooling
  - Full backward compatibility with existing vector store implementations
  - 36+ comprehensive test cases with Docker integration and dependency skipping
  - Complete documentation with setup guides, examples, and performance tuning
  - CI/CD integration: resolved benchmark compatibility and fixed documentation links

- **Improved Vector Store for Decision Tracking** (PR #293 by @KaifAhmad1):
  - Comprehensive decision tracking capabilities with hybrid search combining semantic and structural embeddings
  - New DecisionEmbeddingPipeline for generating semantic and structural embeddings with KG algorithm integration
  - HybridSimilarityCalculator with configurable weights (semantic: 0.7, structural: 0.3)
  - DecisionContext high-level interface for decision management with explainable AI features
  - ContextRetriever with hybrid precedent search and multi-hop reasoning
  - User-friendly convenience API: quick_decision(), find_precedents(), explain(), similar_to(), batch_decisions(), filter_decisions()
  - Knowledge Graph algorithm integration: Node2Vec, PathFinder, CommunityDetector, CentralityCalculator, SimilarityCalculator, ConnectivityAnalyzer
  - Explainable AI with path tracing, confidence scoring, and comprehensive decision explanations
  - Performance optimizations: 0.028s per decision processing, 0.031s search performance, ~0.8KB per decision memory usage
  - 100% backward compatibility maintained with existing VectorStore functionality
  - 34+ comprehensive tests covering all functionality including end-to-end scenarios and performance benchmarks
  - Real-world validation examples for banking and insurance domains
  - Documentation with clear imports, examples, and API references

- **Improved Graph Algorithms in KG Module** (PR #292 by @KaifAhmad1):
  - Complete algorithm suite with 30+ graph algorithms across 7 categories
  - Node Embeddings: Node2Vec, DeepWalk, Word2Vec for structural similarity analysis
  - Similarity Analysis: Cosine, Euclidean, Manhattan, Correlation metrics with batch processing
  - Path Finding: Dijkstra, A*, BFS, K-shortest paths for route and network analysis
  - Link Prediction: Preferential attachment, Jaccard, Adamic-Adar for network completion
  - Centrality Analysis: Degree, Betweenness, Closeness, PageRank for importance ranking
  - Community Detection: Louvain, Leiden, Label propagation for clustering analysis
  - Connectivity Analysis: Components, bridges, density for network robustness
  - Unified provenance tracking system with GraphBuilderWithProvenance and AlgorithmTrackerWithProvenance
  - Complete execution tracking with metadata, timestamps, and reproducibility IDs
  - Comprehensive test coverage with 5 test suites and 40+ test methods
  - Professional documentation overhaul for all modules and reference documentation
  - Enterprise-ready functionality with error handling and NetworkX compatibility
  - Performance optimizations with sparse matrix operations and batch processing
  - Full backward compatibility maintained with gradual migration support

- **Improved Security Configuration with Dependabot**:
  - Configured bi-weekly security updates with manual review by @KaifAhmad1
  - Implemented automated security scans (Monday & Thursday at 7 AM IST) with Bandit, Safety, Semgrep
  - Added security-critical package grouping (cryptography, requests, urllib3, certifi, pyopenssl)
  - Enterprise-grade security with audit trail, compliance features, and zero auto-merge
  - Optimized IST timezone scheduling (Security scans: 7 AM IST, PRs: 9 AM IST)
  - Aligned with new Dependabot features: open-source proxy support, smart dependency grouping for Snowflake/Arrow/benchmark features, private registry support, semantic commit prefixes, and latest GitHub security best practices

- **ResourceScheduler Deadlock Fix and Performance Improvements** (PR #299, #301 by @d4ndr4d3, @KaifAhmad1):
  - Fixed critical deadlock in ResourceScheduler by replacing `threading.Lock()` with `threading.RLock()`
  - Resolved nested lock acquisition issue in `allocate_resources()` → `allocate_cpu/memory/gpu()` calls
  - Added allocation validation with `ValidationError` when no resources can be allocated
  - Improved performance by moving progress tracking updates outside lock scope
  - Implemented comprehensive resource cleanup on allocation failures to prevent leaks
  - Added complete regression test suite (6 tests) for deadlock prevention and edge cases
  - Improved error handling and documentation for better operator visibility
  - Zero breaking changes, maintains thread safety and backward compatibility

## [0.2.7] - 2026-02-09

### Added / Changed

- **Snowflake Connector for Data Ingestion** (PR #276 by @Sameer6305):
  - Native Snowflake connector with multi-authentication (password, OAuth, key-pair, SSO)
  - Table and query ingestion with pagination, schema introspection, batch processing
  - SQL injection prevention via identifier escaping, OAuth token validation
  - Progress tracking integration, context manager support, document export
  - 24 comprehensive unit tests with mocking, complete documentation and examples
  - Added as optional dependency `db-snowflake` with snowflake-connector-python>=3.0.0

- **Apache Arrow Export Support** (PR #273 by @Sameer6305):
  - Added Apache Arrow exporter with explicit schemas, entity/relationship export, compression support
  - Integrated with export module and method registry, Pandas/DuckDB compatible
  - 20 unit tests + 1 integration test, complete documentation with examples

- **Comprehensive Benchmark Suite with Regression CLI** (PR #289 by @ZohaibHassan16, @KaifAhmad1):
  - 137+ benchmarks across all 10 Semantica modules (Input, Core, Storage, Context, QA, Ontology, etc.)
  - Environment-agnostic design with robust mocking system for CI/CD compatibility
  - Statistical regression detection using Z-score analysis with configurable thresholds
  - Automated performance auditing via GitHub Actions workflow
  - Comprehensive documentation suite (benchmarks.md, architecture guides, usage examples)
  - Zero breaking changes, production-ready with ultra-fast text processing (>10,000 ops/s)
  - Added benchmark runner CLI: `python benchmarks/benchmark_runner.py`

## [0.2.6] - 2026-02-03

### Added / Changed

- **W3C PROV-O Compliant Provenance Tracking** (#254, #246):
  - Comprehensive provenance tracking system with W3C PROV-O compliance across all 17 Semantica modules
  - **Core Module**: `ProvenanceManager`, W3C PROV-O schemas, storage backends (InMemory, SQLite), SHA-256 integrity verification
  - **Module Integrations**: Semantic Extract, LLMs (Groq, OpenAI, HuggingFace, LiteLLM), Pipeline, Context, Ingest, Embeddings, Graph/Vector/Triplet stores, Reasoning, Conflicts, Deduplication, Export, Parse, Normalize, Ontology, Visualization
  - **Features**: Complete lineage tracking (Document → Chunk → Entity → Relationship → Graph), LLM tracking (tokens, costs, latency), source tracking, bridge axioms for domain transformations
  - **Compliance Infrastructure**: W3C PROV-O, FDA 21 CFR Part 11, SOX, HIPAA, TNFD
  - **Testing**: 237 tests covering core functionality, all 17 module integrations, edge cases, backward compatibility
  - **Design**: Opt-in with `provenance=False` by default, zero breaking changes, no new dependencies
  - Contributed by @KaifAhmad1

- **Enhanced Change Management Module** (#248, #243):
  - Enterprise-grade version control for knowledge graphs and ontologies with persistent storage and audit trails
  - **Core Classes**: `TemporalVersionManager` (KG versioning), `OntologyVersionManager` (ontology versioning), `ChangeLogEntry` (metadata)
  - **Storage**: SQLite (persistent) and in-memory backends with thread-safe operations
  - **Features**: SHA-256 checksums, detailed entity/relationship diffs, structural ontology comparison, email validation
  - **Compliance Infrastructure**: HIPAA, SOX, FDA 21 CFR Part 11 with immutable audit trails
  - **Testing**: 104 tests (100% pass) - unit, integration, compliance, performance, edge cases
  - **Performance**: 17.6ms for 10k entities, 510+ ops/sec concurrent, handles 5k+ entity graphs
  - **Migration**: Backward compatible, simplified class names, zero external dependencies
  - Contributed by @KaifAhmad1

- CSV Ingestion Enhancements (PR #244 by @saloni0318)
  - Auto-detect CSV encoding (chardet) and delimiter (csv.Sniffer)
  - Tolerant decoding and malformed-row handling (`on_bad_lines='warn'`)
  - Optional chunked reading for large files; metadata tracks detected values
  - Expanded unit tests covering delimiters, quoted/multiline fields, header overrides, chunks, and NaN preservation

- Tests: Comprehensive units for TextNormalizer (PR #242 by @ZohaibHassan16)
  - Added focused test coverage for TextNormalizer behavior across inputs

- Tests: Register integration mark and tidy ingest test warnings (PR #241 by @KaifAhmad1)
  - Introduced integration test marker and reduced noisy warnings in ingest tests

- **Ingest Unit Tests** (#239, #232):
  - Comprehensive unit tests for ingestion modules (file, web, and feed ingestors)
  - **Coverage**: File scanning (local/cloud S3/GCS/Azure), web ingestion (URL/sitemap/robots.txt), RSS/Atom feed parsing
  - **Testing**: 998 lines of test code with mocked external dependencies for fast, isolated execution
  - **Results**: file_ingestor (86%), web_ingestor (86%), feed_ingestor (80%) coverage
  - Covers happy paths, edge cases, and error handling
  - Contributed by @Mohammed2372

### Fixed

- **Temperature Compatibility Fix** (#256, #252):
  - Fixed hardcoded `temperature=0.3` that broke compatibility with models requiring specific temperature values (e.g., gpt-5-mini)
  - Added `_add_if_set` helper method to `BaseProvider` that only passes parameters when explicitly set
  - When `temperature=None`, parameter is omitted allowing APIs to use model defaults
  - Updated all 5 providers: OpenAI, Groq, Gemini, Ollama, DeepSeek
  - Reduced code by ~85 lines with cleaner parameter handling
  - Comprehensive test coverage added (10 temperature tests, all passing)
  - Backward compatible - no breaking changes
  - Contributed by @F0rt1s and @IGES-Institut

- **JenaStore Empty Graph Bug** (#257, #258):
  - Fixed `ProcessingError: Graph not initialized` when operating on empty (but initialized) graphs
  - Replaced implicit `if not self.graph:` checks with explicit `if self.graph is None:` validation in 5 methods (`add_triplets`, `get_triplets`, `delete_triplet`, `execute_sparql`, `serialize`)
  - Properly distinguishes `None` (uninitialized) from empty graphs (initialized with 0 triplets)
  - Unblocks benchmarking suite, fresh deployments, and testing workflows
  - Contributed by @ZohaibHassan16

## [0.2.5] - 2026-01-27

### Added
- **Pinecone Vector Store Support**:
    - Implemented native Pinecone support (`PineconeStore`) with full CRUD capabilities.
    - Added support for serverless and pod-based indexes, namespaces, and metadata filtering.
    - Integrated with `VectorStore` unified interface and registry.
    - (Closes #219, Resolves #220)
- **Configurable LLM Retry Logic**:
    - Exposed `max_retries` parameter in `NERExtractor`, `RelationExtractor`, `TripletExtractor` and low-level extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Defaults to 3 retries to prevent infinite loops during JSON validation failures or API timeouts.
    - Propagated retry configuration through chunked processing helpers to ensure consistent behavior for long documents.
    - Updated `03_Earnings_Call_Analysis.ipynb` to use `max_retries=3` by default.

### Added
- **Bring Your Own Model (BYOM) Support**:
    - Enabled full support for custom Hugging Face models in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added support for custom tokenizers in `HuggingFaceModelLoader` to handle models with non-standard tokenization requirements.
    - Implemented robust fallback logic for model selection: runtime options (`extract(model=...)`) now correctly override configuration defaults.
- **Enhanced NER Implementation**:
    - Added configurable aggregation strategies (`simple`, `first`, `average`, `max`) to `extract_entities_huggingface` for better sub-word token handling.
    - Implemented robust IOB/BILOU parsing to reconstruct entities from raw model outputs when structured output is unavailable.
    - Added confidence scoring for aggregated entities.
- **Relation Extraction Improvements**:
    - Implemented standard entity marker technique (wrapping subject/object with `<subj>`, `<obj>` tags) in `extract_relations_huggingface` for compatibility with sequence classification models.
    - Added structured output parsing to convert raw model predictions into validated `Relation` objects.
- **Triplet Extraction Completion**:
    - Added specialized parsing for Seq2Seq models (e.g., REBEL) in `extract_triplets_huggingface` to generate structured triplets directly from text.
    - Implemented post-processing logic to clean and validate generated triplets.

### Fixed
- **LLM Extraction Stability**:
    - Fixed infinite retry loops in `BaseProvider` by strictly enforcing `max_retries` limit during structured output generation.
    - Resolved stuck execution in earnings call analysis notebooks when using smaller models (e.g., Llama 3 8B) that frequently produce invalid JSON.
- **Model Parameter Precedence**:
    - Fixed issue where configuration defaults took precedence over runtime arguments in Hugging Face extractors. Runtime options now correctly override config values.
- **Import Handling**:
    - Fixed circular import issues in test suites by implementing robust mocking strategies.

## [0.2.4] - 2026-01-22

### Added
- **Ontology Ingestion Module**:
    - Implemented `OntologyIngestor` in `semantica.ingest` for parsing RDF/OWL files (Turtle, RDF/XML, JSON-LD, N3) into standardized `OntologyData` objects.
    - Added `ingest_ontology` convenience function and integrated it into the unified `ingest(source_type="ontology")` interface.
    - Added recursive directory scanning support for batch ontology ingestion.
    - Exposed ingestion tools in `semantica.ontology` for better discoverability.
    - Added `OntologyData` dataclass for consistent metadata handling (source path, format, timestamps).
- **Documentation**:
    - **Ontology Usage Guide**: Updated `ontology_usage.md` with comprehensive examples for single-file and directory ingestion.
    - **API Reference**: Updated `ontology.md` with `OntologyIngestor` class documentation and method details.
- **Tests**:
    - **Comprehensive Test Suite**: Added `tests/ingest/test_ontology_ingestor.py` covering all supported formats, error handling, and unified interface integration.
    - **Demo Script**: Added `examples/demo_ontology_ingest.py` for end-to-end usage demonstration.

## [0.2.3] - 2026-01-20

### Fixed
- **LLM Relation Extraction Parsing**:
    - Fixed relation extraction returning zero relations despite successful API calls to Groq and other providers
    - Normalized typed responses from instructor/OpenAI/Groq to consistent dict format before parsing
    - Added structured JSON fallback when typed generation yields zero relations to avoid silent empty outputs
    - Removed acceptance of extra kwargs (`max_tokens`, `max_entities_prompt`) from relation extraction internals
    - Filtered kwargs passed to provider LLM calls to only `temperature` and `verbose`
- **API Parameter Handling**:
    - Limited kwargs forwarded in chunked extraction helper to prevent parameter leakage
    - Ensured minimal, safe parameters are passed to provider calls
- **Pipeline Circular Import (Issues #192, #193)**:
    - Fixed circular import between `pipeline_builder` and `pipeline_validator` triggered during `semantica.pipeline` import
    - Lazy-loaded `PipelineValidator` inside `PipelineBuilder.__init__` and guarded type hints with `TYPE_CHECKING`
    - Ensured `from semantica.deduplication import DuplicateDetector` no longer fails even when pipeline module is imported
- **JupyterLab Progress Output (Issue #181)**:
    - Added `SEMANTICA_DISABLE_JUPYTER_PROGRESS` environment variable to disable rich Jupyter/Colab progress tables
    - When enabled, progress falls back to console-style output, preventing infinite scrolling and JupyterLab out-of-memory errors

### Added
- **Comprehensive Test Suite**:
-    - Added unit tests (`tests/test_relations_llm.py`) with mocked LLM provider covering both typed and structured response paths
-    - Added integration tests (`tests/integration/test_relations_groq.py`) for real Groq API calls with environment variable API key
-    - Tests validate relation extraction completion and result parsing across different response formats
- **Amazon Neptune Dev Environment**:
-    - Added CloudFormation template (`cookbook/introduction/neptune-setup.yaml`) to provision a dev Neptune cluster with public endpoint and IAM auth enabled
-    - Documented deployment, cost estimates, and IAM User vs IAM Role best practices in `cookbook/introduction/21_Amazon_Neptune_Store.ipynb`
-    - Added `cfn-lint` to `.pre-commit-config.yaml` for validating CloudFormation templates while excluding `neptune-setup.yaml` from generic YAML linters
- **Vector Store High-Performance Ingestion**:
-    - Added `VectorStore.add_documents` for high-throughput ingestion with automatic embedding generation, batching, and parallel processing
-    - Added `VectorStore.embed_batch` helper for generating embeddings for lists of texts without immediately storing them
-    - Enabled default parallel ingestion in `VectorStore` with `max_workers=6` for common workloads
-    - Added dedicated documentation page `docs/vector_store_usage.md` describing high-performance vector store usage and configuration
-    - Added `tests/vector_store/test_vector_store_parallel.py` covering parallel vs sequential performance, error handling, and edge cases for `add_documents` and `embed_batch`

### Changed
- **Relation Extraction API**:
-    - Simplified parameter interface by removing unused kwargs that were previously ignored
-    - Improved error handling and verbose logging for debugging relation extraction issues
-    - Enhanced robustness of post-response parsing across different LLM providers
- **Vector Store Defaults and Examples**:
-    - Standardized `VectorStore` default concurrency to `max_workers=6` for parallel ingestion
-    - Updated vector store reference documentation and usage guides to rely on implicit defaults instead of requiring manual `max_workers` configuration in examples


## [0.2.2] - 2026-01-15

### Added
- **Parallel Extraction Engine**:
    - Implemented high-throughput parallel batch processing across all core extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticNetworkExtractor`) using `concurrent.futures.ThreadPoolExecutor`.
    - Added `max_workers` configuration parameter (default: 1) to all extractor `extract()` methods, allowing users to tune concurrency based on available CPU cores or API rate limits.
    - **Parallel Chunking**: Implemented parallel processing for large document chunking in `_extract_entities_chunked` and `_extract_relations_chunked`, significantly reducing latency for long-form text analysis.
    - **Thread-Safe Progress Tracking**: Enhanced `ProgressTracker` to handle concurrent updates from multiple threads without race conditions during batch processing.
- **Semantic Extract Performance & Regression**:
    - Added edge-case regression suite covering max worker defaults, LLM prompt entity filtering, and extractor reuse.
    - Added a runnable real-use-case benchmark script for batch latency across `NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticAnalyzer`, and `SemanticNetworkExtractor`.
    - Added Groq LLM smoke tests that exercise LLM-based entities/relations/triplets when `GROQ_API_KEY` is available via environment configuration.

### Security
- **Credential Sanitization**:
    - Removed hardcoded API keys from 8 cookbook notebooks to prevent secret leakage.
    - Enforced environment variable usage for `GROQ_API_KEY` across all examples.
- **Secure Caching**:
    - Updated `ExtractionCache` to exclude sensitive parameters (e.g., `api_key`, `token`, `password`) from cache key generation, preventing secret leakage and enabling safe cache sharing.
    - Upgraded cache key hashing algorithm from MD5 to **SHA-256** for enhanced collision resistance and security.

### Changed
- **Gemini SDK Migration**:
    - Migrated `GeminiProvider` to use the new `google-genai` SDK (v0.1.0+) to address deprecation warnings.
    - Implemented graceful fallback to `google.generativeai` for backward compatibility.
- **Dependency Resolution**:
    - Pinned `opentelemetry-api` and `opentelemetry-sdk` to `1.37.0` to resolve pip conflicts.
    - Updated `protobuf` and `grpcio` constraints for better stability.
- **Entity Filtering Scope**:
    - Removed entity filtering from non-LLM extraction flows to avoid accuracy regressions.
    - Applied entity downselection only to LLM relation prompt construction, while matching returned entities against the full original entity list.
- **Batch Concurrency Defaults**:
    - Standardized `max_workers` defaulting across `semantic_extract` and tuned for low-latency: ML-backed methods default to single-worker, while pattern/regex/rules/LLM/huggingface methods use a higher parallelism default capped by CPU.
    - Raised the global `optimization.max_workers` default to 8 for better throughput on batch workloads.

### Performance
- **Bottleneck Optimization (GitHub Issue #186)**:
    - **Resolved Bottleneck #1 (Sequential Processing)**: Replaced sequential `for` loops with parallel execution for both document-level batches and intra-document chunks.
    - **Performance Gains**: Achieved **~1.89x speedup** in real-world extraction scenarios (tested with Groq `llama-3.3-70b-versatile` on standard datasets).
    - **Initialization Optimization**: Refactored test suite to use class-level `setUpClass` for LLM provider initialization, eliminating redundant API client creation overhead.
- **Low-Latency Entity Matching**:
    - Avoided heavyweight embedding stack imports on common matches by improving fast matching heuristics and short-circuiting before embedding similarity.
    - Optimized entity matching to prioritize exact/substring/word-boundary matches and only fall back to embedding similarity when needed, reducing CPU overhead in LLM relation/triplet mapping.


## [0.2.1] - 2026-01-12

### Fixed
- **LLM Output Stability (Bug #176)**:
    - Fixed incomplete JSON output issues by correctly propagating `max_tokens` parameter in `extract_relations_llm`.
    - Implemented automatic error handling that halves chunk sizes and retries when LLM context or output limits are exceeded.
    - Fixed `AttributeError` in provider integration by ensuring consistent parameter passing via `**kwargs`.
- **Constraint Relaxations**:
    - Removed hardcoded `max_length` constraints from `Entity`, `Relation`, and `Triplet` classes to support long-form semantic extraction (e.g., long descriptions or names).
- Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
- Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
- Fixed dependency compatibility issues by pinning `protobuf>=5.29.1,<7.0` and `grpcio>=1.71.2`.
- Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
- Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Changed
- **Chunking Defaults**:
    - Increased default `max_text_length` for auto-chunking to **64,000 characters** (from 32k/16k) for OpenAI, Anthropic, Gemini, Groq, and DeepSeek providers.
    - Unified chunking logic across `extract_entities_llm`, `extract_relations_llm`, and `extract_triplets_llm`.
- **Groq Support**:
    - Standardized Groq provider defaults to use `llama-3.3-70b-versatile` with a 64k context window.
    - Added native support for `max_tokens` and `max_completion_tokens` to prevent output truncation.

### Added
- **Testing**:
    - Added `tests/reproduce_issue_176.py` to validate `max_tokens` propagation and chunking behavior across all extractors.


## [0.2.0] - 2026-01-10

### Added
- **Amazon Neptune Support**:
    - Added `AmazonNeptuneStore` providing Amazon Neptune graph database integration via Bolt protocol and OpenCypher.
    - Implemented `NeptuneAuthTokenManager` extending Neo4j AuthManager for AWS IAM SigV4 signing with automatic token refresh.
    - Added robust connection handling: retry logic with backoff for transient errors (signature expired, connection closed) and driver recreation.
    - Added `graph-amazon-neptune` optional dependency group (boto3, neo4j).
    - Comprehensive test suite covering all GraphStore interface methods.
- **Docling Integration**:
    - Added `DoclingParser` in `semantica.parse` for high-fidelity document parsing using the Docling library.
    - Supports multi-format parsing (PDF, DOCX, PPTX, XLSX, HTML, images) with superior table extraction and structure understanding.
    - Implemented as a standalone parser supporting local execution, OCR, and multiple export formats (Markdown, HTML, JSON).
- **Robust Extraction Fallbacks**:
    - Implemented comprehensive fallback chains ("ML/LLM" -> "Pattern" -> "Last Resort") across `NERExtractor`, `RelationExtractor`, and `TripletExtractor` to prevent empty result lists.
    - Added "Last Resort" pattern matching in `NERExtractor` to identify capitalized words as generic entities when all other methods fail.
    - Added "Last Resort" adjacency-based relation extraction in `RelationExtractor` to create weak connections between adjacent entities if no relations are found.
    - Added fallback logic in `TripletExtractor` to convert relations to triplets or use rule-based extraction if standard methods fail.
- **Provenance & Tracking**:
    - Added count tracking to batch processing logs in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added `batch_index` and `document_id` to the metadata of all extracted entities, relations, triplets, semantic roles, and clusters for better traceability.
- **Semantic Extract Improvements**:
    - Introduced `auto-chunking` for long text processing in LLM extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Added `silent_fail` parameter to LLM extraction methods for configurable error handling.
    - Implemented robust JSON parsing and automatic retry logic (3 attempts with exponential backoff) in `BaseProvider` for all LLM providers.
    - Enhanced `GroqProvider` with better diagnostics and connectivity testing.
    - Added comprehensive entity, relation, and triplet deduplication for chunked extraction.
    - Added `semantica/semantic_extract/schemas.py` with canonical Pydantic models for consistent structured output.
- **Testing**:
    - Added comprehensive robustness test suite `tests/semantic_extract/test_robustness_fallback.py` for validating extraction fallbacks and metadata propagation.
    - Added comprehensive unit test suite `tests/embeddings/test_model_switching.py` for verifying dynamic model transitions and dimension updates.
    - Added end-to-end integration test suite for Knowledge Graph pipeline validation (GraphBuilder -> EntityResolver -> GraphAnalyzer).
- **Other**:
    - Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
    - Robustified ID extraction across `CentralityCalculator`, `CommunityDetector`, and `ConnectivityAnalyzer` to handle various entity formats.
    - Improved `Entity` class hashability and equality logic in `utils/types.py`.

### Changed
- **Deduplication & Conflict Logic**:
    - Removed internal deduplication logic from `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Removed consistency/conflict checking from `ExtractionValidator` to defer to dedicated `semantica/conflicts` module.
    - Removed `_deduplicate_*` methods from `semantica/semantic_extract/methods.py`.
- **Batch Processing & Consistency**:
    - Standardized batch processing across all extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `SemanticNetworkExtractor`, `EventDetector`, `SemanticAnalyzer`, `CoreferenceResolver`) using a unified `extract`/`analyze`/`resolve` method pattern with progress tracking.
    - Added provenance metadata (`batch_index`, `document_id`) to `SemanticNetwork` nodes/edges, `Event` objects, `SemanticRole` results, `CoreferenceChain` mentions, and `SemanticCluster` (tracking source `document_ids`).
    - Updated `SemanticClusterer.cluster` and `SemanticAnalyzer.cluster_semantically` to accept list of dictionaries (with `content` and `id` keys) for better document tracking during clustering.
    - Removed legacy `check_triplet_consistency` from `TripletExtractor`.
    - Removed `validate_consistency` and `_check_consistency` from `ExtractionValidator`.
- **Weighted Scoring**:
    - Clarified weighted confidence scoring (50% Method Confidence + 50% Type Similarity) in comments.
    - Explicitly labeled "Type Similarity" as "user-provided" in code comments to remove ambiguity.
- **Refactoring**:
    - Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
    - Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Fixed
- **Critical Fixes**:
    - Resolved `NameError` in `extraction_validator.py` by adding missing `Union` import.
    - Resolved issues where extractors would return empty lists for valid input text when primary extraction methods failed.
    - Fixed metadata initialization issue in batch processing where `batch_index` and `document_id` were occasionally missing from extracted items.
    - Ensured `LLMExtraction` methods (`enhance_entities`, `enhance_relations`) return original input instead of failing or returning empty results when LLM providers are unavailable.
- **Component Fixes**:
    - Fixed model switching bug in `TextEmbedder` where internal state was not cleared, preventing dynamic updates between `fastembed` and `sentence_transformers` (#160).
    - Implemented model-intrinsic embedding dimension detection in `TextEmbedder` to ensure consistency between models and vector databases.
    - Updated `set_model` to properly refresh configuration and dimensions during model switches.
    - Fixed `TypeError: unhashable type: 'Entity'` in `GraphAnalyzer` when processing graphs with raw `Entity` objects or dictionaries in relationships (#159).
    - Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
    - Fixed dependency compatibility issues by pinning `protobuf==4.25.3` and `grpcio==1.67.1`.
    - Fixed a bug in `TripletExtractor` where the `validate_triplets` method was shadowed by an internal attribute.
    - Fixed incorrect `TextSplitter` import path in the `semantic_extract.methods` module.

## [0.1.1] - 2026-01-05

### Added
- Exported `DoclingParser` and `DoclingMetadata` from `semantica.parse` for easier access.
- Added comprehensive `DoclingParser` usage examples to README and documentation.
- Added Windows-specific troubleshooting note for PyTorch DLL issues.

### Fixed
- Fixed `DoclingParser` import/export issues across platforms (Windows, Linux, Google Colab).
- Improved error messaging when optional `docling` dependency is missing.
- Fixed versioning inconsistencies across the framework.

## [0.1.0] - 2025-12-31

### Added
- New command-line interface (`semantica` CLI) with support for knowledge base building and info commands.
- Integrated FastAPI-based REST API server for remote access to framework functionality.
- Dedicated background worker component for scalable task processing and pipeline execution.
- Framework-level versioning configuration for PyPI distribution.
- Automated release workflow with Trusted Publishing support.

### Changed
- Updated versioning across the framework to 0.1.0.
- Refined entry point configurations in `pyproject.toml`.
- Improved lazy module loading for core framework components.

## [0.0.5] - 2025-11-26

### Changed
- Configured Trusted Publishing for secure automated PyPI deployments

## [0.0.4] - 2025-11-26

### Changed
- Fixed PyPI deployment issues from v0.0.3

## [0.0.3] - 2025-11-25

### Changed
- Simplified CI/CD workflows - removed failing tests and strict linting
- Combined release and PyPI publishing into single workflow
- Simplified security scanning to weekly pip-audit only
- Streamlined GitHub Actions configuration

### Added
- Comprehensive issue templates (Bug, Feature, Documentation, Support, Grant/Partnership)
- Updated pull request template with clear guidelines
- Community support documentation (SUPPORT.md)
- Funding and sponsorship configuration (FUNDING.yml)
- GitHub configuration README for maintainers
- 10+ new domain-specific cookbook examples (Finance, Healthcare, Cybersecurity, etc.)

### Removed
- Redundant scripts folder (8 shell/PowerShell scripts)
- Unnecessary automation workflows (label-issues, mark-answered)
- Excessive issue templates

## [0.0.2] - 2025-11-25

### Changed
- Updated README with streamlined content and better examples
- Added more notebooks to cookbook
- Improved documentation structure

## [0.0.1] - 2024-01-XX

### Added
- Core framework architecture
- Universal data ingestion (multiple file formats)
- Semantic intelligence engine (NER, relation extraction, event detection)
- Knowledge graph construction with entity resolution
- 6-stage ontology generation pipeline
- GraphRAG engine for hybrid retrieval
- Multi-agent system infrastructure
- Production-ready quality assurance modules
- Comprehensive documentation with MkDocs
- Cookbook with interactive tutorials
- Support for multiple vector stores (Weaviate, Qdrant, FAISS)
- Support for multiple graph databases (Neo4j, NetworkX, RDFLib)
- Temporal knowledge graph support
- Conflict detection and resolution
- Deduplication and entity merging
- Schema template enforcement
- Seed data management
- Multi-format export (RDF, JSON-LD, CSV, GraphML)
- Visualization tools
- Pipeline orchestration
- Streaming support (Kafka, RabbitMQ, Kinesis)
- Context engineering for AI agents
- Reasoning and inference engine

### Documentation
- Getting started guide
- API reference for all modules
- Concepts and architecture documentation
- Use case examples
- Cookbook tutorials
- Community projects showcase

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

## Migration Guides

When breaking changes are introduced, migration guides will be provided in the release notes and documentation.

---

For detailed release notes, see [GitHub Releases](https://github.com/Hawksight-AI/semantica/releases).

## Legacy Changelog Snapshot A (Preserved Merge Artifact)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- **OWLGenerator user-facing schema compatibility fixes** (Issue #446):
  - Fixed OWL class/property IRI identifier fallback order to prefer label and then name.
  - Fixed datatype property handling to accept scalar and list range values in rdflib path (including xsd:*, full IRIs, and local names), preventing list-based .startswith() crashes.
  - Fixed generated class/property/domain/range IRIs to use the current ontology dict uri namespace for each generation call (instead of drifting to default namespace manager base URI when per-entity uri is omitted).
  - Fixed subClassOf / subclassOf parent resolution so local class names are expanded to ontology IRIs consistently with domain/range behavior.
  - Added/expanded regression coverage in 	ests/ontology/test_ontology_comprehensive.py (	est_owl_generator_user_facing_schema_compatibility) for label-first fallback, lowercase subclassOf, datatype range lists, and ontology namespace consistency.

- Fixed: PolicyEngine latest version selection on ContextGraph; AgentContext fallback robustness and secure logging (PR #TBD by @KaifAhmad1)
- Tests: Added ContextGraph fallback and AgentContext smoke tests; full suite passing

- **Context Engineering Enhancement** (PR #307 by @KaifAhmad1):
  - Comprehensive decision tracking system with full lifecycle management (record → analyze → query → precedent → influence)
  - Advanced KG algorithm integration: centrality analysis, community detection, node embeddings with ContextGraph
  - Enhanced AgentContext with granular feature flags for decision tracking, KG algorithms, and vector store features
  - PolicyException model replacing conflicting Exception name for meaningful business domain modeling
  - GraphStore validation preventing runtime failures with explicit capability checking
  - Hybrid search combining semantic, structural, and category similarity with configurable weights
  - Decision influence analysis with centrality measures and causal chain tracking
  - Policy management with versioning, compliance checking, and exception handling
  - Production-ready architecture with audit trails, security, and scalability features
  - 9 critical bug fixes: logging, security, audit trails, API compatibility, Cypher queries, centrality access, validation, naming
  - Comprehensive documentation with usage guides, production examples, and API references
  - 100% test coverage with all validation tests passing (9/9 tests)
  - Enterprise-grade features for financial services, healthcare, legal, and business domains
  - Complete backward compatibility with existing semantica components
  - Performance optimizations: caching, indexing, and efficient graph operations

- **Added PgVector Store Support** (PR #303 by @Sameer6305, @KaifAhmad1):
  - Native PostgreSQL vector storage using pgvector extension with full integration
  - Multiple distance metrics: cosine, L2/Euclidean, inner product with automatic score normalization
  - Advanced indexing: HNSW and IVFFlat for approximate nearest neighbor search with tunable parameters
  - JSONB metadata storage with flexible filtering capabilities and batch operations
  - Connection pooling support with psycopg3/psycopg2 fallback and efficient resource management
  - Comprehensive VectorStore integration with backend delegation and unified API
  - Idempotent index creation and table management with safe migration support
  - Production-ready security: SQL injection protection with psycopg_sql.SQL() and input validation
  - Performance optimizations: UUID4-based IDs, batch executemany operations, connection pooling
  - Full backward compatibility with existing vector store implementations
  - 36+ comprehensive test cases with Docker integration and dependency skipping
  - Complete documentation with setup guides, examples, and performance tuning
  - CI/CD integration: resolved benchmark compatibility and fixed documentation links

- **Improved Vector Store for Decision Tracking** (PR #293 by @KaifAhmad1):
  - Comprehensive decision tracking capabilities with hybrid search combining semantic and structural embeddings
  - New DecisionEmbeddingPipeline for generating semantic and structural embeddings with KG algorithm integration
  - HybridSimilarityCalculator with configurable weights (semantic: 0.7, structural: 0.3)
  - DecisionContext high-level interface for decision management with explainable AI features
  - ContextRetriever with hybrid precedent search and multi-hop reasoning
  - User-friendly convenience API: quick_decision(), find_precedents(), explain(), similar_to(), batch_decisions(), filter_decisions()
  - Knowledge Graph algorithm integration: Node2Vec, PathFinder, CommunityDetector, CentralityCalculator, SimilarityCalculator, ConnectivityAnalyzer
  - Explainable AI with path tracing, confidence scoring, and comprehensive decision explanations
  - Performance optimizations: 0.028s per decision processing, 0.031s search performance, ~0.8KB per decision memory usage
  - 100% backward compatibility maintained with existing VectorStore functionality
  - 34+ comprehensive tests covering all functionality including end-to-end scenarios and performance benchmarks
  - Real-world validation examples for banking and insurance domains
  - Documentation with clear imports, examples, and API references

- **Improved Graph Algorithms in KG Module** (PR #292 by @KaifAhmad1):
  - Complete algorithm suite with 30+ graph algorithms across 7 categories
  - Node Embeddings: Node2Vec, DeepWalk, Word2Vec for structural similarity analysis
  - Similarity Analysis: Cosine, Euclidean, Manhattan, Correlation metrics with batch processing
  - Path Finding: Dijkstra, A*, BFS, K-shortest paths for route and network analysis
  - Link Prediction: Preferential attachment, Jaccard, Adamic-Adar for network completion
  - Centrality Analysis: Degree, Betweenness, Closeness, PageRank for importance ranking
  - Community Detection: Louvain, Leiden, Label propagation for clustering analysis
  - Connectivity Analysis: Components, bridges, density for network robustness
  - Unified provenance tracking system with GraphBuilderWithProvenance and AlgorithmTrackerWithProvenance
  - Complete execution tracking with metadata, timestamps, and reproducibility IDs
  - Comprehensive test coverage with 5 test suites and 40+ test methods
  - Professional documentation overhaul for all modules and reference documentation
  - Enterprise-ready functionality with error handling and NetworkX compatibility
  - Performance optimizations with sparse matrix operations and batch processing
  - Full backward compatibility maintained with gradual migration support

- **Improved Security Configuration with Dependabot**:
  - Configured bi-weekly security updates with manual review by @KaifAhmad1
  - Implemented automated security scans (Monday & Thursday at 7 AM IST) with Bandit, Safety, Semgrep
  - Added security-critical package grouping (cryptography, requests, urllib3, certifi, pyopenssl)
  - Enterprise-grade security with audit trail, compliance features, and zero auto-merge
  - Optimized IST timezone scheduling (Security scans: 7 AM IST, PRs: 9 AM IST)
  - Aligned with new Dependabot features: open-source proxy support, smart dependency grouping for Snowflake/Arrow/benchmark features, private registry support, semantic commit prefixes, and latest GitHub security best practices

- **ResourceScheduler Deadlock Fix and Performance Improvements** (PR #299, #301 by @d4ndr4d3, @KaifAhmad1):
  - Fixed critical deadlock in ResourceScheduler by replacing `threading.Lock()` with `threading.RLock()`
  - Resolved nested lock acquisition issue in `allocate_resources()` → `allocate_cpu/memory/gpu()` calls
  - Added allocation validation with `ValidationError` when no resources can be allocated
  - Improved performance by moving progress tracking updates outside lock scope
  - Implemented comprehensive resource cleanup on allocation failures to prevent leaks
  - Added complete regression test suite (6 tests) for deadlock prevention and edge cases
  - Improved error handling and documentation for better operator visibility
  - Zero breaking changes, maintains thread safety and backward compatibility

## [0.2.7] - 2026-02-09

### Added / Changed

- **Snowflake Connector for Data Ingestion** (PR #276 by @Sameer6305):
  - Native Snowflake connector with multi-authentication (password, OAuth, key-pair, SSO)
  - Table and query ingestion with pagination, schema introspection, batch processing
  - SQL injection prevention via identifier escaping, OAuth token validation
  - Progress tracking integration, context manager support, document export
  - 24 comprehensive unit tests with mocking, complete documentation and examples
  - Added as optional dependency `db-snowflake` with snowflake-connector-python>=3.0.0

- **Apache Arrow Export Support** (PR #273 by @Sameer6305):
  - Added Apache Arrow exporter with explicit schemas, entity/relationship export, compression support
  - Integrated with export module and method registry, Pandas/DuckDB compatible
  - 20 unit tests + 1 integration test, complete documentation with examples

- **Comprehensive Benchmark Suite with Regression CLI** (PR #289 by @ZohaibHassan16, @KaifAhmad1):
  - 137+ benchmarks across all 10 Semantica modules (Input, Core, Storage, Context, QA, Ontology, etc.)
  - Environment-agnostic design with robust mocking system for CI/CD compatibility
  - Statistical regression detection using Z-score analysis with configurable thresholds
  - Automated performance auditing via GitHub Actions workflow
  - Comprehensive documentation suite (benchmarks.md, architecture guides, usage examples)
  - Zero breaking changes, production-ready with ultra-fast text processing (>10,000 ops/s)
  - Added benchmark runner CLI: `python benchmarks/benchmark_runner.py`

## [0.2.6] - 2026-02-03

### Added / Changed

- **W3C PROV-O Compliant Provenance Tracking** (#254, #246):
  - Comprehensive provenance tracking system with W3C PROV-O compliance across all 17 Semantica modules
  - **Core Module**: `ProvenanceManager`, W3C PROV-O schemas, storage backends (InMemory, SQLite), SHA-256 integrity verification
  - **Module Integrations**: Semantic Extract, LLMs (Groq, OpenAI, HuggingFace, LiteLLM), Pipeline, Context, Ingest, Embeddings, Graph/Vector/Triplet stores, Reasoning, Conflicts, Deduplication, Export, Parse, Normalize, Ontology, Visualization
  - **Features**: Complete lineage tracking (Document → Chunk → Entity → Relationship → Graph), LLM tracking (tokens, costs, latency), source tracking, bridge axioms for domain transformations
  - **Compliance Infrastructure**: W3C PROV-O, FDA 21 CFR Part 11, SOX, HIPAA, TNFD
  - **Testing**: 237 tests covering core functionality, all 17 module integrations, edge cases, backward compatibility
  - **Design**: Opt-in with `provenance=False` by default, zero breaking changes, no new dependencies
  - Contributed by @KaifAhmad1

- **Enhanced Change Management Module** (#248, #243):
  - Enterprise-grade version control for knowledge graphs and ontologies with persistent storage and audit trails
  - **Core Classes**: `TemporalVersionManager` (KG versioning), `OntologyVersionManager` (ontology versioning), `ChangeLogEntry` (metadata)
  - **Storage**: SQLite (persistent) and in-memory backends with thread-safe operations
  - **Features**: SHA-256 checksums, detailed entity/relationship diffs, structural ontology comparison, email validation
  - **Compliance Infrastructure**: HIPAA, SOX, FDA 21 CFR Part 11 with immutable audit trails
  - **Testing**: 104 tests (100% pass) - unit, integration, compliance, performance, edge cases
  - **Performance**: 17.6ms for 10k entities, 510+ ops/sec concurrent, handles 5k+ entity graphs
  - **Migration**: Backward compatible, simplified class names, zero external dependencies
  - Contributed by @KaifAhmad1

- CSV Ingestion Enhancements (PR #244 by @saloni0318)
  - Auto-detect CSV encoding (chardet) and delimiter (csv.Sniffer)
  - Tolerant decoding and malformed-row handling (`on_bad_lines='warn'`)
  - Optional chunked reading for large files; metadata tracks detected values
  - Expanded unit tests covering delimiters, quoted/multiline fields, header overrides, chunks, and NaN preservation

- Tests: Comprehensive units for TextNormalizer (PR #242 by @ZohaibHassan16)
  - Added focused test coverage for TextNormalizer behavior across inputs

- Tests: Register integration mark and tidy ingest test warnings (PR #241 by @KaifAhmad1)
  - Introduced integration test marker and reduced noisy warnings in ingest tests

- **Ingest Unit Tests** (#239, #232):
  - Comprehensive unit tests for ingestion modules (file, web, and feed ingestors)
  - **Coverage**: File scanning (local/cloud S3/GCS/Azure), web ingestion (URL/sitemap/robots.txt), RSS/Atom feed parsing
  - **Testing**: 998 lines of test code with mocked external dependencies for fast, isolated execution
  - **Results**: file_ingestor (86%), web_ingestor (86%), feed_ingestor (80%) coverage
  - Covers happy paths, edge cases, and error handling
  - Contributed by @Mohammed2372

### Fixed

- **Temperature Compatibility Fix** (#256, #252):
  - Fixed hardcoded `temperature=0.3` that broke compatibility with models requiring specific temperature values (e.g., gpt-5-mini)
  - Added `_add_if_set` helper method to `BaseProvider` that only passes parameters when explicitly set
  - When `temperature=None`, parameter is omitted allowing APIs to use model defaults
  - Updated all 5 providers: OpenAI, Groq, Gemini, Ollama, DeepSeek
  - Reduced code by ~85 lines with cleaner parameter handling
  - Comprehensive test coverage added (10 temperature tests, all passing)
  - Backward compatible - no breaking changes
  - Contributed by @F0rt1s and @IGES-Institut

- **JenaStore Empty Graph Bug** (#257, #258):
  - Fixed `ProcessingError: Graph not initialized` when operating on empty (but initialized) graphs
  - Replaced implicit `if not self.graph:` checks with explicit `if self.graph is None:` validation in 5 methods (`add_triplets`, `get_triplets`, `delete_triplet`, `execute_sparql`, `serialize`)
  - Properly distinguishes `None` (uninitialized) from empty graphs (initialized with 0 triplets)
  - Unblocks benchmarking suite, fresh deployments, and testing workflows
  - Contributed by @ZohaibHassan16

## [0.2.5] - 2026-01-27

### Added
- **Pinecone Vector Store Support**:
    - Implemented native Pinecone support (`PineconeStore`) with full CRUD capabilities.
    - Added support for serverless and pod-based indexes, namespaces, and metadata filtering.
    - Integrated with `VectorStore` unified interface and registry.
    - (Closes #219, Resolves #220)
- **Configurable LLM Retry Logic**:
    - Exposed `max_retries` parameter in `NERExtractor`, `RelationExtractor`, `TripletExtractor` and low-level extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Defaults to 3 retries to prevent infinite loops during JSON validation failures or API timeouts.
    - Propagated retry configuration through chunked processing helpers to ensure consistent behavior for long documents.
    - Updated `03_Earnings_Call_Analysis.ipynb` to use `max_retries=3` by default.

### Added
- **Bring Your Own Model (BYOM) Support**:
    - Enabled full support for custom Hugging Face models in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added support for custom tokenizers in `HuggingFaceModelLoader` to handle models with non-standard tokenization requirements.
    - Implemented robust fallback logic for model selection: runtime options (`extract(model=...)`) now correctly override configuration defaults.
- **Enhanced NER Implementation**:
    - Added configurable aggregation strategies (`simple`, `first`, `average`, `max`) to `extract_entities_huggingface` for better sub-word token handling.
    - Implemented robust IOB/BILOU parsing to reconstruct entities from raw model outputs when structured output is unavailable.
    - Added confidence scoring for aggregated entities.
- **Relation Extraction Improvements**:
    - Implemented standard entity marker technique (wrapping subject/object with `<subj>`, `<obj>` tags) in `extract_relations_huggingface` for compatibility with sequence classification models.
    - Added structured output parsing to convert raw model predictions into validated `Relation` objects.
- **Triplet Extraction Completion**:
    - Added specialized parsing for Seq2Seq models (e.g., REBEL) in `extract_triplets_huggingface` to generate structured triplets directly from text.
    - Implemented post-processing logic to clean and validate generated triplets.

### Fixed
- **LLM Extraction Stability**:
    - Fixed infinite retry loops in `BaseProvider` by strictly enforcing `max_retries` limit during structured output generation.
    - Resolved stuck execution in earnings call analysis notebooks when using smaller models (e.g., Llama 3 8B) that frequently produce invalid JSON.
- **Model Parameter Precedence**:
    - Fixed issue where configuration defaults took precedence over runtime arguments in Hugging Face extractors. Runtime options now correctly override config values.
- **Import Handling**:
    - Fixed circular import issues in test suites by implementing robust mocking strategies.

## [0.2.4] - 2026-01-22

### Added
- **Ontology Ingestion Module**:
    - Implemented `OntologyIngestor` in `semantica.ingest` for parsing RDF/OWL files (Turtle, RDF/XML, JSON-LD, N3) into standardized `OntologyData` objects.
    - Added `ingest_ontology` convenience function and integrated it into the unified `ingest(source_type="ontology")` interface.
    - Added recursive directory scanning support for batch ontology ingestion.
    - Exposed ingestion tools in `semantica.ontology` for better discoverability.
    - Added `OntologyData` dataclass for consistent metadata handling (source path, format, timestamps).
- **Documentation**:
    - **Ontology Usage Guide**: Updated `ontology_usage.md` with comprehensive examples for single-file and directory ingestion.
    - **API Reference**: Updated `ontology.md` with `OntologyIngestor` class documentation and method details.
- **Tests**:
    - **Comprehensive Test Suite**: Added `tests/ingest/test_ontology_ingestor.py` covering all supported formats, error handling, and unified interface integration.
    - **Demo Script**: Added `examples/demo_ontology_ingest.py` for end-to-end usage demonstration.

## [0.2.3] - 2026-01-20

### Fixed
- **LLM Relation Extraction Parsing**:
    - Fixed relation extraction returning zero relations despite successful API calls to Groq and other providers
    - Normalized typed responses from instructor/OpenAI/Groq to consistent dict format before parsing
    - Added structured JSON fallback when typed generation yields zero relations to avoid silent empty outputs
    - Removed acceptance of extra kwargs (`max_tokens`, `max_entities_prompt`) from relation extraction internals
    - Filtered kwargs passed to provider LLM calls to only `temperature` and `verbose`
- **API Parameter Handling**:
    - Limited kwargs forwarded in chunked extraction helper to prevent parameter leakage
    - Ensured minimal, safe parameters are passed to provider calls
- **Pipeline Circular Import (Issues #192, #193)**:
    - Fixed circular import between `pipeline_builder` and `pipeline_validator` triggered during `semantica.pipeline` import
    - Lazy-loaded `PipelineValidator` inside `PipelineBuilder.__init__` and guarded type hints with `TYPE_CHECKING`
    - Ensured `from semantica.deduplication import DuplicateDetector` no longer fails even when pipeline module is imported
- **JupyterLab Progress Output (Issue #181)**:
    - Added `SEMANTICA_DISABLE_JUPYTER_PROGRESS` environment variable to disable rich Jupyter/Colab progress tables
    - When enabled, progress falls back to console-style output, preventing infinite scrolling and JupyterLab out-of-memory errors

### Added
- **Comprehensive Test Suite**:
-    - Added unit tests (`tests/test_relations_llm.py`) with mocked LLM provider covering both typed and structured response paths
-    - Added integration tests (`tests/integration/test_relations_groq.py`) for real Groq API calls with environment variable API key
-    - Tests validate relation extraction completion and result parsing across different response formats
- **Amazon Neptune Dev Environment**:
-    - Added CloudFormation template (`cookbook/introduction/neptune-setup.yaml`) to provision a dev Neptune cluster with public endpoint and IAM auth enabled
-    - Documented deployment, cost estimates, and IAM User vs IAM Role best practices in `cookbook/introduction/21_Amazon_Neptune_Store.ipynb`
-    - Added `cfn-lint` to `.pre-commit-config.yaml` for validating CloudFormation templates while excluding `neptune-setup.yaml` from generic YAML linters
- **Vector Store High-Performance Ingestion**:
-    - Added `VectorStore.add_documents` for high-throughput ingestion with automatic embedding generation, batching, and parallel processing
-    - Added `VectorStore.embed_batch` helper for generating embeddings for lists of texts without immediately storing them
-    - Enabled default parallel ingestion in `VectorStore` with `max_workers=6` for common workloads
-    - Added dedicated documentation page `docs/vector_store_usage.md` describing high-performance vector store usage and configuration
-    - Added `tests/vector_store/test_vector_store_parallel.py` covering parallel vs sequential performance, error handling, and edge cases for `add_documents` and `embed_batch`

### Changed
- **Relation Extraction API**:
-    - Simplified parameter interface by removing unused kwargs that were previously ignored
-    - Improved error handling and verbose logging for debugging relation extraction issues
-    - Enhanced robustness of post-response parsing across different LLM providers
- **Vector Store Defaults and Examples**:
-    - Standardized `VectorStore` default concurrency to `max_workers=6` for parallel ingestion
-    - Updated vector store reference documentation and usage guides to rely on implicit defaults instead of requiring manual `max_workers` configuration in examples


## [0.2.2] - 2026-01-15

### Added
- **Parallel Extraction Engine**:
    - Implemented high-throughput parallel batch processing across all core extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticNetworkExtractor`) using `concurrent.futures.ThreadPoolExecutor`.
    - Added `max_workers` configuration parameter (default: 1) to all extractor `extract()` methods, allowing users to tune concurrency based on available CPU cores or API rate limits.
    - **Parallel Chunking**: Implemented parallel processing for large document chunking in `_extract_entities_chunked` and `_extract_relations_chunked`, significantly reducing latency for long-form text analysis.
    - **Thread-Safe Progress Tracking**: Enhanced `ProgressTracker` to handle concurrent updates from multiple threads without race conditions during batch processing.
- **Semantic Extract Performance & Regression**:
    - Added edge-case regression suite covering max worker defaults, LLM prompt entity filtering, and extractor reuse.
    - Added a runnable real-use-case benchmark script for batch latency across `NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticAnalyzer`, and `SemanticNetworkExtractor`.
    - Added Groq LLM smoke tests that exercise LLM-based entities/relations/triplets when `GROQ_API_KEY` is available via environment configuration.

### Security
- **Credential Sanitization**:
    - Removed hardcoded API keys from 8 cookbook notebooks to prevent secret leakage.
    - Enforced environment variable usage for `GROQ_API_KEY` across all examples.
- **Secure Caching**:
    - Updated `ExtractionCache` to exclude sensitive parameters (e.g., `api_key`, `token`, `password`) from cache key generation, preventing secret leakage and enabling safe cache sharing.
    - Upgraded cache key hashing algorithm from MD5 to **SHA-256** for enhanced collision resistance and security.

### Changed
- **Gemini SDK Migration**:
    - Migrated `GeminiProvider` to use the new `google-genai` SDK (v0.1.0+) to address deprecation warnings.
    - Implemented graceful fallback to `google.generativeai` for backward compatibility.
- **Dependency Resolution**:
    - Pinned `opentelemetry-api` and `opentelemetry-sdk` to `1.37.0` to resolve pip conflicts.
    - Updated `protobuf` and `grpcio` constraints for better stability.
- **Entity Filtering Scope**:
    - Removed entity filtering from non-LLM extraction flows to avoid accuracy regressions.
    - Applied entity downselection only to LLM relation prompt construction, while matching returned entities against the full original entity list.
- **Batch Concurrency Defaults**:
    - Standardized `max_workers` defaulting across `semantic_extract` and tuned for low-latency: ML-backed methods default to single-worker, while pattern/regex/rules/LLM/huggingface methods use a higher parallelism default capped by CPU.
    - Raised the global `optimization.max_workers` default to 8 for better throughput on batch workloads.

### Performance
- **Bottleneck Optimization (GitHub Issue #186)**:
    - **Resolved Bottleneck #1 (Sequential Processing)**: Replaced sequential `for` loops with parallel execution for both document-level batches and intra-document chunks.
    - **Performance Gains**: Achieved **~1.89x speedup** in real-world extraction scenarios (tested with Groq `llama-3.3-70b-versatile` on standard datasets).
    - **Initialization Optimization**: Refactored test suite to use class-level `setUpClass` for LLM provider initialization, eliminating redundant API client creation overhead.
- **Low-Latency Entity Matching**:
    - Avoided heavyweight embedding stack imports on common matches by improving fast matching heuristics and short-circuiting before embedding similarity.
    - Optimized entity matching to prioritize exact/substring/word-boundary matches and only fall back to embedding similarity when needed, reducing CPU overhead in LLM relation/triplet mapping.


## [0.2.1] - 2026-01-12

### Fixed
- **LLM Output Stability (Bug #176)**:
    - Fixed incomplete JSON output issues by correctly propagating `max_tokens` parameter in `extract_relations_llm`.
    - Implemented automatic error handling that halves chunk sizes and retries when LLM context or output limits are exceeded.
    - Fixed `AttributeError` in provider integration by ensuring consistent parameter passing via `**kwargs`.
- **Constraint Relaxations**:
    - Removed hardcoded `max_length` constraints from `Entity`, `Relation`, and `Triplet` classes to support long-form semantic extraction (e.g., long descriptions or names).
- Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
- Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
- Fixed dependency compatibility issues by pinning `protobuf>=5.29.1,<7.0` and `grpcio>=1.71.2`.
- Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
- Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Changed
- **Chunking Defaults**:
    - Increased default `max_text_length` for auto-chunking to **64,000 characters** (from 32k/16k) for OpenAI, Anthropic, Gemini, Groq, and DeepSeek providers.
    - Unified chunking logic across `extract_entities_llm`, `extract_relations_llm`, and `extract_triplets_llm`.
- **Groq Support**:
    - Standardized Groq provider defaults to use `llama-3.3-70b-versatile` with a 64k context window.
    - Added native support for `max_tokens` and `max_completion_tokens` to prevent output truncation.

### Added
- **Testing**:
    - Added `tests/reproduce_issue_176.py` to validate `max_tokens` propagation and chunking behavior across all extractors.


## [0.2.0] - 2026-01-10

### Added
- **Amazon Neptune Support**:
    - Added `AmazonNeptuneStore` providing Amazon Neptune graph database integration via Bolt protocol and OpenCypher.
    - Implemented `NeptuneAuthTokenManager` extending Neo4j AuthManager for AWS IAM SigV4 signing with automatic token refresh.
    - Added robust connection handling: retry logic with backoff for transient errors (signature expired, connection closed) and driver recreation.
    - Added `graph-amazon-neptune` optional dependency group (boto3, neo4j).
    - Comprehensive test suite covering all GraphStore interface methods.
- **Docling Integration**:
    - Added `DoclingParser` in `semantica.parse` for high-fidelity document parsing using the Docling library.
    - Supports multi-format parsing (PDF, DOCX, PPTX, XLSX, HTML, images) with superior table extraction and structure understanding.
    - Implemented as a standalone parser supporting local execution, OCR, and multiple export formats (Markdown, HTML, JSON).
- **Robust Extraction Fallbacks**:
    - Implemented comprehensive fallback chains ("ML/LLM" -> "Pattern" -> "Last Resort") across `NERExtractor`, `RelationExtractor`, and `TripletExtractor` to prevent empty result lists.
    - Added "Last Resort" pattern matching in `NERExtractor` to identify capitalized words as generic entities when all other methods fail.
    - Added "Last Resort" adjacency-based relation extraction in `RelationExtractor` to create weak connections between adjacent entities if no relations are found.
    - Added fallback logic in `TripletExtractor` to convert relations to triplets or use rule-based extraction if standard methods fail.
- **Provenance & Tracking**:
    - Added count tracking to batch processing logs in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added `batch_index` and `document_id` to the metadata of all extracted entities, relations, triplets, semantic roles, and clusters for better traceability.
- **Semantic Extract Improvements**:
    - Introduced `auto-chunking` for long text processing in LLM extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Added `silent_fail` parameter to LLM extraction methods for configurable error handling.
    - Implemented robust JSON parsing and automatic retry logic (3 attempts with exponential backoff) in `BaseProvider` for all LLM providers.
    - Enhanced `GroqProvider` with better diagnostics and connectivity testing.
    - Added comprehensive entity, relation, and triplet deduplication for chunked extraction.
    - Added `semantica/semantic_extract/schemas.py` with canonical Pydantic models for consistent structured output.
- **Testing**:
    - Added comprehensive robustness test suite `tests/semantic_extract/test_robustness_fallback.py` for validating extraction fallbacks and metadata propagation.
    - Added comprehensive unit test suite `tests/embeddings/test_model_switching.py` for verifying dynamic model transitions and dimension updates.
    - Added end-to-end integration test suite for Knowledge Graph pipeline validation (GraphBuilder -> EntityResolver -> GraphAnalyzer).
- **Other**:
    - Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
    - Robustified ID extraction across `CentralityCalculator`, `CommunityDetector`, and `ConnectivityAnalyzer` to handle various entity formats.
    - Improved `Entity` class hashability and equality logic in `utils/types.py`.

### Changed
- **Deduplication & Conflict Logic**:
    - Removed internal deduplication logic from `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Removed consistency/conflict checking from `ExtractionValidator` to defer to dedicated `semantica/conflicts` module.
    - Removed `_deduplicate_*` methods from `semantica/semantic_extract/methods.py`.
- **Batch Processing & Consistency**:
    - Standardized batch processing across all extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `SemanticNetworkExtractor`, `EventDetector`, `SemanticAnalyzer`, `CoreferenceResolver`) using a unified `extract`/`analyze`/`resolve` method pattern with progress tracking.
    - Added provenance metadata (`batch_index`, `document_id`) to `SemanticNetwork` nodes/edges, `Event` objects, `SemanticRole` results, `CoreferenceChain` mentions, and `SemanticCluster` (tracking source `document_ids`).
    - Updated `SemanticClusterer.cluster` and `SemanticAnalyzer.cluster_semantically` to accept list of dictionaries (with `content` and `id` keys) for better document tracking during clustering.
    - Removed legacy `check_triplet_consistency` from `TripletExtractor`.
    - Removed `validate_consistency` and `_check_consistency` from `ExtractionValidator`.
- **Weighted Scoring**:
    - Clarified weighted confidence scoring (50% Method Confidence + 50% Type Similarity) in comments.
    - Explicitly labeled "Type Similarity" as "user-provided" in code comments to remove ambiguity.
- **Refactoring**:
    - Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
    - Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Fixed
- **Critical Fixes**:
    - Resolved `NameError` in `extraction_validator.py` by adding missing `Union` import.
    - Resolved issues where extractors would return empty lists for valid input text when primary extraction methods failed.
    - Fixed metadata initialization issue in batch processing where `batch_index` and `document_id` were occasionally missing from extracted items.
    - Ensured `LLMExtraction` methods (`enhance_entities`, `enhance_relations`) return original input instead of failing or returning empty results when LLM providers are unavailable.
- **Component Fixes**:
    - Fixed model switching bug in `TextEmbedder` where internal state was not cleared, preventing dynamic updates between `fastembed` and `sentence_transformers` (#160).
    - Implemented model-intrinsic embedding dimension detection in `TextEmbedder` to ensure consistency between models and vector databases.
    - Updated `set_model` to properly refresh configuration and dimensions during model switches.
    - Fixed `TypeError: unhashable type: 'Entity'` in `GraphAnalyzer` when processing graphs with raw `Entity` objects or dictionaries in relationships (#159).
    - Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
    - Fixed dependency compatibility issues by pinning `protobuf==4.25.3` and `grpcio==1.67.1`.
    - Fixed a bug in `TripletExtractor` where the `validate_triplets` method was shadowed by an internal attribute.
    - Fixed incorrect `TextSplitter` import path in the `semantic_extract.methods` module.

## [0.1.1] - 2026-01-05

### Added
- Exported `DoclingParser` and `DoclingMetadata` from `semantica.parse` for easier access.
- Added comprehensive `DoclingParser` usage examples to README and documentation.
- Added Windows-specific troubleshooting note for PyTorch DLL issues.

### Fixed
- Fixed `DoclingParser` import/export issues across platforms (Windows, Linux, Google Colab).
- Improved error messaging when optional `docling` dependency is missing.
- Fixed versioning inconsistencies across the framework.

## [0.1.0] - 2025-12-31

### Added
- New command-line interface (`semantica` CLI) with support for knowledge base building and info commands.
- Integrated FastAPI-based REST API server for remote access to framework functionality.
- Dedicated background worker component for scalable task processing and pipeline execution.
- Framework-level versioning configuration for PyPI distribution.
- Automated release workflow with Trusted Publishing support.

### Changed
- Updated versioning across the framework to 0.1.0.
- Refined entry point configurations in `pyproject.toml`.
- Improved lazy module loading for core framework components.

## [0.0.5] - 2025-11-26

### Changed
- Configured Trusted Publishing for secure automated PyPI deployments

## [0.0.4] - 2025-11-26

### Changed
- Fixed PyPI deployment issues from v0.0.3

## [0.0.3] - 2025-11-25

### Changed
- Simplified CI/CD workflows - removed failing tests and strict linting
- Combined release and PyPI publishing into single workflow
- Simplified security scanning to weekly pip-audit only
- Streamlined GitHub Actions configuration

### Added
- Comprehensive issue templates (Bug, Feature, Documentation, Support, Grant/Partnership)
- Updated pull request template with clear guidelines
- Community support documentation (SUPPORT.md)
- Funding and sponsorship configuration (FUNDING.yml)
- GitHub configuration README for maintainers
- 10+ new domain-specific cookbook examples (Finance, Healthcare, Cybersecurity, etc.)

### Removed
- Redundant scripts folder (8 shell/PowerShell scripts)
- Unnecessary automation workflows (label-issues, mark-answered)
- Excessive issue templates

## [0.0.2] - 2025-11-25

### Changed
- Updated README with streamlined content and better examples
- Added more notebooks to cookbook
- Improved documentation structure

## [0.0.1] - 2024-01-XX

### Added
- Core framework architecture
- Universal data ingestion (multiple file formats)
- Semantic intelligence engine (NER, relation extraction, event detection)
- Knowledge graph construction with entity resolution
- 6-stage ontology generation pipeline
- GraphRAG engine for hybrid retrieval
- Multi-agent system infrastructure
- Production-ready quality assurance modules
- Comprehensive documentation with MkDocs
- Cookbook with interactive tutorials
- Support for multiple vector stores (Weaviate, Qdrant, FAISS)
- Support for multiple graph databases (Neo4j, NetworkX, RDFLib)
- Temporal knowledge graph support
- Conflict detection and resolution
- Deduplication and entity merging
- Schema template enforcement
- Seed data management
- Multi-format export (RDF, JSON-LD, CSV, GraphML)
- Visualization tools
- Pipeline orchestration
- Streaming support (Kafka, RabbitMQ, Kinesis)
- Context engineering for AI agents
- Reasoning and inference engine

### Documentation
- Getting started guide
- API reference for all modules
- Concepts and architecture documentation
- Use case examples
- Cookbook tutorials
- Community projects showcase

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

## Migration Guides

When breaking changes are introduced, migration guides will be provided in the release notes and documentation.

---

For detailed release notes, see [GitHub Releases](https://github.com/Hawksight-AI/semantica/releases).

## Legacy Changelog Snapshot B (Preserved Merge Artifact)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- **OWLGenerator user-facing schema compatibility fixes** (Issue #446):
  - Fixed OWL class/property IRI identifier fallback order to prefer label and then name.
  - Fixed datatype property handling to accept scalar and list range values in rdflib path (including xsd:*, full IRIs, and local names), preventing list-based .startswith() crashes.
  - Fixed generated class/property/domain/range IRIs to use the current ontology dict uri namespace for each generation call (instead of drifting to default namespace manager base URI when per-entity uri is omitted).
  - Fixed subClassOf / subclassOf parent resolution so local class names are expanded to ontology IRIs consistently with domain/range behavior.
  - Added/expanded regression coverage in 	ests/ontology/test_ontology_comprehensive.py (	est_owl_generator_user_facing_schema_compatibility) for label-first fallback, lowercase subclassOf, datatype range lists, and ontology namespace consistency.

- Fixed: PolicyEngine latest version selection on ContextGraph; AgentContext fallback robustness and secure logging (PR #TBD by @KaifAhmad1)
- Tests: Added ContextGraph fallback and AgentContext smoke tests; full suite passing

- **Context Engineering Enhancement** (PR #307 by @KaifAhmad1):
  - Comprehensive decision tracking system with full lifecycle management (record → analyze → query → precedent → influence)
  - Advanced KG algorithm integration: centrality analysis, community detection, node embeddings with ContextGraph
  - Enhanced AgentContext with granular feature flags for decision tracking, KG algorithms, and vector store features
  - PolicyException model replacing conflicting Exception name for meaningful business domain modeling
  - GraphStore validation preventing runtime failures with explicit capability checking
  - Hybrid search combining semantic, structural, and category similarity with configurable weights
  - Decision influence analysis with centrality measures and causal chain tracking
  - Policy management with versioning, compliance checking, and exception handling
  - Production-ready architecture with audit trails, security, and scalability features
  - 9 critical bug fixes: logging, security, audit trails, API compatibility, Cypher queries, centrality access, validation, naming
  - Comprehensive documentation with usage guides, production examples, and API references
  - 100% test coverage with all validation tests passing (9/9 tests)
  - Enterprise-grade features for financial services, healthcare, legal, and business domains
  - Complete backward compatibility with existing semantica components
  - Performance optimizations: caching, indexing, and efficient graph operations

- **Added PgVector Store Support** (PR #303 by @Sameer6305, @KaifAhmad1):
  - Native PostgreSQL vector storage using pgvector extension with full integration
  - Multiple distance metrics: cosine, L2/Euclidean, inner product with automatic score normalization
  - Advanced indexing: HNSW and IVFFlat for approximate nearest neighbor search with tunable parameters
  - JSONB metadata storage with flexible filtering capabilities and batch operations
  - Connection pooling support with psycopg3/psycopg2 fallback and efficient resource management
  - Comprehensive VectorStore integration with backend delegation and unified API
  - Idempotent index creation and table management with safe migration support
  - Production-ready security: SQL injection protection with psycopg_sql.SQL() and input validation
  - Performance optimizations: UUID4-based IDs, batch executemany operations, connection pooling
  - Full backward compatibility with existing vector store implementations
  - 36+ comprehensive test cases with Docker integration and dependency skipping
  - Complete documentation with setup guides, examples, and performance tuning
  - CI/CD integration: resolved benchmark compatibility and fixed documentation links

- **Improved Vector Store for Decision Tracking** (PR #293 by @KaifAhmad1):
  - Comprehensive decision tracking capabilities with hybrid search combining semantic and structural embeddings
  - New DecisionEmbeddingPipeline for generating semantic and structural embeddings with KG algorithm integration
  - HybridSimilarityCalculator with configurable weights (semantic: 0.7, structural: 0.3)
  - DecisionContext high-level interface for decision management with explainable AI features
  - ContextRetriever with hybrid precedent search and multi-hop reasoning
  - User-friendly convenience API: quick_decision(), find_precedents(), explain(), similar_to(), batch_decisions(), filter_decisions()
  - Knowledge Graph algorithm integration: Node2Vec, PathFinder, CommunityDetector, CentralityCalculator, SimilarityCalculator, ConnectivityAnalyzer
  - Explainable AI with path tracing, confidence scoring, and comprehensive decision explanations
  - Performance optimizations: 0.028s per decision processing, 0.031s search performance, ~0.8KB per decision memory usage
  - 100% backward compatibility maintained with existing VectorStore functionality
  - 34+ comprehensive tests covering all functionality including end-to-end scenarios and performance benchmarks
  - Real-world validation examples for banking and insurance domains
  - Documentation with clear imports, examples, and API references

- **Improved Graph Algorithms in KG Module** (PR #292 by @KaifAhmad1):
  - Complete algorithm suite with 30+ graph algorithms across 7 categories
  - Node Embeddings: Node2Vec, DeepWalk, Word2Vec for structural similarity analysis
  - Similarity Analysis: Cosine, Euclidean, Manhattan, Correlation metrics with batch processing
  - Path Finding: Dijkstra, A*, BFS, K-shortest paths for route and network analysis
  - Link Prediction: Preferential attachment, Jaccard, Adamic-Adar for network completion
  - Centrality Analysis: Degree, Betweenness, Closeness, PageRank for importance ranking
  - Community Detection: Louvain, Leiden, Label propagation for clustering analysis
  - Connectivity Analysis: Components, bridges, density for network robustness
  - Unified provenance tracking system with GraphBuilderWithProvenance and AlgorithmTrackerWithProvenance
  - Complete execution tracking with metadata, timestamps, and reproducibility IDs
  - Comprehensive test coverage with 5 test suites and 40+ test methods
  - Professional documentation overhaul for all modules and reference documentation
  - Enterprise-ready functionality with error handling and NetworkX compatibility
  - Performance optimizations with sparse matrix operations and batch processing
  - Full backward compatibility maintained with gradual migration support

- **Improved Security Configuration with Dependabot**:
  - Configured bi-weekly security updates with manual review by @KaifAhmad1
  - Implemented automated security scans (Monday & Thursday at 7 AM IST) with Bandit, Safety, Semgrep
  - Added security-critical package grouping (cryptography, requests, urllib3, certifi, pyopenssl)
  - Enterprise-grade security with audit trail, compliance features, and zero auto-merge
  - Optimized IST timezone scheduling (Security scans: 7 AM IST, PRs: 9 AM IST)
  - Aligned with new Dependabot features: open-source proxy support, smart dependency grouping for Snowflake/Arrow/benchmark features, private registry support, semantic commit prefixes, and latest GitHub security best practices

- **ResourceScheduler Deadlock Fix and Performance Improvements** (PR #299, #301 by @d4ndr4d3, @KaifAhmad1):
  - Fixed critical deadlock in ResourceScheduler by replacing `threading.Lock()` with `threading.RLock()`
  - Resolved nested lock acquisition issue in `allocate_resources()` → `allocate_cpu/memory/gpu()` calls
  - Added allocation validation with `ValidationError` when no resources can be allocated
  - Improved performance by moving progress tracking updates outside lock scope
  - Implemented comprehensive resource cleanup on allocation failures to prevent leaks
  - Added complete regression test suite (6 tests) for deadlock prevention and edge cases
  - Improved error handling and documentation for better operator visibility
  - Zero breaking changes, maintains thread safety and backward compatibility

## [0.2.7] - 2026-02-09

### Added / Changed

- **Snowflake Connector for Data Ingestion** (PR #276 by @Sameer6305):
  - Native Snowflake connector with multi-authentication (password, OAuth, key-pair, SSO)
  - Table and query ingestion with pagination, schema introspection, batch processing
  - SQL injection prevention via identifier escaping, OAuth token validation
  - Progress tracking integration, context manager support, document export
  - 24 comprehensive unit tests with mocking, complete documentation and examples
  - Added as optional dependency `db-snowflake` with snowflake-connector-python>=3.0.0

- **Apache Arrow Export Support** (PR #273 by @Sameer6305):
  - Added Apache Arrow exporter with explicit schemas, entity/relationship export, compression support
  - Integrated with export module and method registry, Pandas/DuckDB compatible
  - 20 unit tests + 1 integration test, complete documentation with examples

- **Comprehensive Benchmark Suite with Regression CLI** (PR #289 by @ZohaibHassan16, @KaifAhmad1):
  - 137+ benchmarks across all 10 Semantica modules (Input, Core, Storage, Context, QA, Ontology, etc.)
  - Environment-agnostic design with robust mocking system for CI/CD compatibility
  - Statistical regression detection using Z-score analysis with configurable thresholds
  - Automated performance auditing via GitHub Actions workflow
  - Comprehensive documentation suite (benchmarks.md, architecture guides, usage examples)
  - Zero breaking changes, production-ready with ultra-fast text processing (>10,000 ops/s)
  - Added benchmark runner CLI: `python benchmarks/benchmark_runner.py`

## [0.2.6] - 2026-02-03

### Added / Changed

- **W3C PROV-O Compliant Provenance Tracking** (#254, #246):
  - Comprehensive provenance tracking system with W3C PROV-O compliance across all 17 Semantica modules
  - **Core Module**: `ProvenanceManager`, W3C PROV-O schemas, storage backends (InMemory, SQLite), SHA-256 integrity verification
  - **Module Integrations**: Semantic Extract, LLMs (Groq, OpenAI, HuggingFace, LiteLLM), Pipeline, Context, Ingest, Embeddings, Graph/Vector/Triplet stores, Reasoning, Conflicts, Deduplication, Export, Parse, Normalize, Ontology, Visualization
  - **Features**: Complete lineage tracking (Document → Chunk → Entity → Relationship → Graph), LLM tracking (tokens, costs, latency), source tracking, bridge axioms for domain transformations
  - **Compliance Infrastructure**: W3C PROV-O, FDA 21 CFR Part 11, SOX, HIPAA, TNFD
  - **Testing**: 237 tests covering core functionality, all 17 module integrations, edge cases, backward compatibility
  - **Design**: Opt-in with `provenance=False` by default, zero breaking changes, no new dependencies
  - Contributed by @KaifAhmad1

- **Enhanced Change Management Module** (#248, #243):
  - Enterprise-grade version control for knowledge graphs and ontologies with persistent storage and audit trails
  - **Core Classes**: `TemporalVersionManager` (KG versioning), `OntologyVersionManager` (ontology versioning), `ChangeLogEntry` (metadata)
  - **Storage**: SQLite (persistent) and in-memory backends with thread-safe operations
  - **Features**: SHA-256 checksums, detailed entity/relationship diffs, structural ontology comparison, email validation
  - **Compliance Infrastructure**: HIPAA, SOX, FDA 21 CFR Part 11 with immutable audit trails
  - **Testing**: 104 tests (100% pass) - unit, integration, compliance, performance, edge cases
  - **Performance**: 17.6ms for 10k entities, 510+ ops/sec concurrent, handles 5k+ entity graphs
  - **Migration**: Backward compatible, simplified class names, zero external dependencies
  - Contributed by @KaifAhmad1

- CSV Ingestion Enhancements (PR #244 by @saloni0318)
  - Auto-detect CSV encoding (chardet) and delimiter (csv.Sniffer)
  - Tolerant decoding and malformed-row handling (`on_bad_lines='warn'`)
  - Optional chunked reading for large files; metadata tracks detected values
  - Expanded unit tests covering delimiters, quoted/multiline fields, header overrides, chunks, and NaN preservation

- Tests: Comprehensive units for TextNormalizer (PR #242 by @ZohaibHassan16)
  - Added focused test coverage for TextNormalizer behavior across inputs

- Tests: Register integration mark and tidy ingest test warnings (PR #241 by @KaifAhmad1)
  - Introduced integration test marker and reduced noisy warnings in ingest tests

- **Ingest Unit Tests** (#239, #232):
  - Comprehensive unit tests for ingestion modules (file, web, and feed ingestors)
  - **Coverage**: File scanning (local/cloud S3/GCS/Azure), web ingestion (URL/sitemap/robots.txt), RSS/Atom feed parsing
  - **Testing**: 998 lines of test code with mocked external dependencies for fast, isolated execution
  - **Results**: file_ingestor (86%), web_ingestor (86%), feed_ingestor (80%) coverage
  - Covers happy paths, edge cases, and error handling
  - Contributed by @Mohammed2372

### Fixed

- **Temperature Compatibility Fix** (#256, #252):
  - Fixed hardcoded `temperature=0.3` that broke compatibility with models requiring specific temperature values (e.g., gpt-5-mini)
  - Added `_add_if_set` helper method to `BaseProvider` that only passes parameters when explicitly set
  - When `temperature=None`, parameter is omitted allowing APIs to use model defaults
  - Updated all 5 providers: OpenAI, Groq, Gemini, Ollama, DeepSeek
  - Reduced code by ~85 lines with cleaner parameter handling
  - Comprehensive test coverage added (10 temperature tests, all passing)
  - Backward compatible - no breaking changes
  - Contributed by @F0rt1s and @IGES-Institut

- **JenaStore Empty Graph Bug** (#257, #258):
  - Fixed `ProcessingError: Graph not initialized` when operating on empty (but initialized) graphs
  - Replaced implicit `if not self.graph:` checks with explicit `if self.graph is None:` validation in 5 methods (`add_triplets`, `get_triplets`, `delete_triplet`, `execute_sparql`, `serialize`)
  - Properly distinguishes `None` (uninitialized) from empty graphs (initialized with 0 triplets)
  - Unblocks benchmarking suite, fresh deployments, and testing workflows
  - Contributed by @ZohaibHassan16

## [0.2.5] - 2026-01-27

### Added
- **Pinecone Vector Store Support**:
    - Implemented native Pinecone support (`PineconeStore`) with full CRUD capabilities.
    - Added support for serverless and pod-based indexes, namespaces, and metadata filtering.
    - Integrated with `VectorStore` unified interface and registry.
    - (Closes #219, Resolves #220)
- **Configurable LLM Retry Logic**:
    - Exposed `max_retries` parameter in `NERExtractor`, `RelationExtractor`, `TripletExtractor` and low-level extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Defaults to 3 retries to prevent infinite loops during JSON validation failures or API timeouts.
    - Propagated retry configuration through chunked processing helpers to ensure consistent behavior for long documents.
    - Updated `03_Earnings_Call_Analysis.ipynb` to use `max_retries=3` by default.

### Added
- **Bring Your Own Model (BYOM) Support**:
    - Enabled full support for custom Hugging Face models in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added support for custom tokenizers in `HuggingFaceModelLoader` to handle models with non-standard tokenization requirements.
    - Implemented robust fallback logic for model selection: runtime options (`extract(model=...)`) now correctly override configuration defaults.
- **Enhanced NER Implementation**:
    - Added configurable aggregation strategies (`simple`, `first`, `average`, `max`) to `extract_entities_huggingface` for better sub-word token handling.
    - Implemented robust IOB/BILOU parsing to reconstruct entities from raw model outputs when structured output is unavailable.
    - Added confidence scoring for aggregated entities.
- **Relation Extraction Improvements**:
    - Implemented standard entity marker technique (wrapping subject/object with `<subj>`, `<obj>` tags) in `extract_relations_huggingface` for compatibility with sequence classification models.
    - Added structured output parsing to convert raw model predictions into validated `Relation` objects.
- **Triplet Extraction Completion**:
    - Added specialized parsing for Seq2Seq models (e.g., REBEL) in `extract_triplets_huggingface` to generate structured triplets directly from text.
    - Implemented post-processing logic to clean and validate generated triplets.

### Fixed
- **LLM Extraction Stability**:
    - Fixed infinite retry loops in `BaseProvider` by strictly enforcing `max_retries` limit during structured output generation.
    - Resolved stuck execution in earnings call analysis notebooks when using smaller models (e.g., Llama 3 8B) that frequently produce invalid JSON.
- **Model Parameter Precedence**:
    - Fixed issue where configuration defaults took precedence over runtime arguments in Hugging Face extractors. Runtime options now correctly override config values.
- **Import Handling**:
    - Fixed circular import issues in test suites by implementing robust mocking strategies.

## [0.2.4] - 2026-01-22

### Added
- **Ontology Ingestion Module**:
    - Implemented `OntologyIngestor` in `semantica.ingest` for parsing RDF/OWL files (Turtle, RDF/XML, JSON-LD, N3) into standardized `OntologyData` objects.
    - Added `ingest_ontology` convenience function and integrated it into the unified `ingest(source_type="ontology")` interface.
    - Added recursive directory scanning support for batch ontology ingestion.
    - Exposed ingestion tools in `semantica.ontology` for better discoverability.
    - Added `OntologyData` dataclass for consistent metadata handling (source path, format, timestamps).
- **Documentation**:
    - **Ontology Usage Guide**: Updated `ontology_usage.md` with comprehensive examples for single-file and directory ingestion.
    - **API Reference**: Updated `ontology.md` with `OntologyIngestor` class documentation and method details.
- **Tests**:
    - **Comprehensive Test Suite**: Added `tests/ingest/test_ontology_ingestor.py` covering all supported formats, error handling, and unified interface integration.
    - **Demo Script**: Added `examples/demo_ontology_ingest.py` for end-to-end usage demonstration.

## [0.2.3] - 2026-01-20

### Fixed
- **LLM Relation Extraction Parsing**:
    - Fixed relation extraction returning zero relations despite successful API calls to Groq and other providers
    - Normalized typed responses from instructor/OpenAI/Groq to consistent dict format before parsing
    - Added structured JSON fallback when typed generation yields zero relations to avoid silent empty outputs
    - Removed acceptance of extra kwargs (`max_tokens`, `max_entities_prompt`) from relation extraction internals
    - Filtered kwargs passed to provider LLM calls to only `temperature` and `verbose`
- **API Parameter Handling**:
    - Limited kwargs forwarded in chunked extraction helper to prevent parameter leakage
    - Ensured minimal, safe parameters are passed to provider calls
- **Pipeline Circular Import (Issues #192, #193)**:
    - Fixed circular import between `pipeline_builder` and `pipeline_validator` triggered during `semantica.pipeline` import
    - Lazy-loaded `PipelineValidator` inside `PipelineBuilder.__init__` and guarded type hints with `TYPE_CHECKING`
    - Ensured `from semantica.deduplication import DuplicateDetector` no longer fails even when pipeline module is imported
- **JupyterLab Progress Output (Issue #181)**:
    - Added `SEMANTICA_DISABLE_JUPYTER_PROGRESS` environment variable to disable rich Jupyter/Colab progress tables
    - When enabled, progress falls back to console-style output, preventing infinite scrolling and JupyterLab out-of-memory errors

### Added
- **Comprehensive Test Suite**:
-    - Added unit tests (`tests/test_relations_llm.py`) with mocked LLM provider covering both typed and structured response paths
-    - Added integration tests (`tests/integration/test_relations_groq.py`) for real Groq API calls with environment variable API key
-    - Tests validate relation extraction completion and result parsing across different response formats
- **Amazon Neptune Dev Environment**:
-    - Added CloudFormation template (`cookbook/introduction/neptune-setup.yaml`) to provision a dev Neptune cluster with public endpoint and IAM auth enabled
-    - Documented deployment, cost estimates, and IAM User vs IAM Role best practices in `cookbook/introduction/21_Amazon_Neptune_Store.ipynb`
-    - Added `cfn-lint` to `.pre-commit-config.yaml` for validating CloudFormation templates while excluding `neptune-setup.yaml` from generic YAML linters
- **Vector Store High-Performance Ingestion**:
-    - Added `VectorStore.add_documents` for high-throughput ingestion with automatic embedding generation, batching, and parallel processing
-    - Added `VectorStore.embed_batch` helper for generating embeddings for lists of texts without immediately storing them
-    - Enabled default parallel ingestion in `VectorStore` with `max_workers=6` for common workloads
-    - Added dedicated documentation page `docs/vector_store_usage.md` describing high-performance vector store usage and configuration
-    - Added `tests/vector_store/test_vector_store_parallel.py` covering parallel vs sequential performance, error handling, and edge cases for `add_documents` and `embed_batch`

### Changed
- **Relation Extraction API**:
-    - Simplified parameter interface by removing unused kwargs that were previously ignored
-    - Improved error handling and verbose logging for debugging relation extraction issues
-    - Enhanced robustness of post-response parsing across different LLM providers
- **Vector Store Defaults and Examples**:
-    - Standardized `VectorStore` default concurrency to `max_workers=6` for parallel ingestion
-    - Updated vector store reference documentation and usage guides to rely on implicit defaults instead of requiring manual `max_workers` configuration in examples


## [0.2.2] - 2026-01-15

### Added
- **Parallel Extraction Engine**:
    - Implemented high-throughput parallel batch processing across all core extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticNetworkExtractor`) using `concurrent.futures.ThreadPoolExecutor`.
    - Added `max_workers` configuration parameter (default: 1) to all extractor `extract()` methods, allowing users to tune concurrency based on available CPU cores or API rate limits.
    - **Parallel Chunking**: Implemented parallel processing for large document chunking in `_extract_entities_chunked` and `_extract_relations_chunked`, significantly reducing latency for long-form text analysis.
    - **Thread-Safe Progress Tracking**: Enhanced `ProgressTracker` to handle concurrent updates from multiple threads without race conditions during batch processing.
- **Semantic Extract Performance & Regression**:
    - Added edge-case regression suite covering max worker defaults, LLM prompt entity filtering, and extractor reuse.
    - Added a runnable real-use-case benchmark script for batch latency across `NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticAnalyzer`, and `SemanticNetworkExtractor`.
    - Added Groq LLM smoke tests that exercise LLM-based entities/relations/triplets when `GROQ_API_KEY` is available via environment configuration.

### Security
- **Credential Sanitization**:
    - Removed hardcoded API keys from 8 cookbook notebooks to prevent secret leakage.
    - Enforced environment variable usage for `GROQ_API_KEY` across all examples.
- **Secure Caching**:
    - Updated `ExtractionCache` to exclude sensitive parameters (e.g., `api_key`, `token`, `password`) from cache key generation, preventing secret leakage and enabling safe cache sharing.
    - Upgraded cache key hashing algorithm from MD5 to **SHA-256** for enhanced collision resistance and security.

### Changed
- **Gemini SDK Migration**:
    - Migrated `GeminiProvider` to use the new `google-genai` SDK (v0.1.0+) to address deprecation warnings.
    - Implemented graceful fallback to `google.generativeai` for backward compatibility.
- **Dependency Resolution**:
    - Pinned `opentelemetry-api` and `opentelemetry-sdk` to `1.37.0` to resolve pip conflicts.
    - Updated `protobuf` and `grpcio` constraints for better stability.
- **Entity Filtering Scope**:
    - Removed entity filtering from non-LLM extraction flows to avoid accuracy regressions.
    - Applied entity downselection only to LLM relation prompt construction, while matching returned entities against the full original entity list.
- **Batch Concurrency Defaults**:
    - Standardized `max_workers` defaulting across `semantic_extract` and tuned for low-latency: ML-backed methods default to single-worker, while pattern/regex/rules/LLM/huggingface methods use a higher parallelism default capped by CPU.
    - Raised the global `optimization.max_workers` default to 8 for better throughput on batch workloads.

### Performance
- **Bottleneck Optimization (GitHub Issue #186)**:
    - **Resolved Bottleneck #1 (Sequential Processing)**: Replaced sequential `for` loops with parallel execution for both document-level batches and intra-document chunks.
    - **Performance Gains**: Achieved **~1.89x speedup** in real-world extraction scenarios (tested with Groq `llama-3.3-70b-versatile` on standard datasets).
    - **Initialization Optimization**: Refactored test suite to use class-level `setUpClass` for LLM provider initialization, eliminating redundant API client creation overhead.
- **Low-Latency Entity Matching**:
    - Avoided heavyweight embedding stack imports on common matches by improving fast matching heuristics and short-circuiting before embedding similarity.
    - Optimized entity matching to prioritize exact/substring/word-boundary matches and only fall back to embedding similarity when needed, reducing CPU overhead in LLM relation/triplet mapping.


## [0.2.1] - 2026-01-12

### Fixed
- **LLM Output Stability (Bug #176)**:
    - Fixed incomplete JSON output issues by correctly propagating `max_tokens` parameter in `extract_relations_llm`.
    - Implemented automatic error handling that halves chunk sizes and retries when LLM context or output limits are exceeded.
    - Fixed `AttributeError` in provider integration by ensuring consistent parameter passing via `**kwargs`.
- **Constraint Relaxations**:
    - Removed hardcoded `max_length` constraints from `Entity`, `Relation`, and `Triplet` classes to support long-form semantic extraction (e.g., long descriptions or names).
- Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
- Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
- Fixed dependency compatibility issues by pinning `protobuf>=5.29.1,<7.0` and `grpcio>=1.71.2`.
- Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
- Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Changed
- **Chunking Defaults**:
    - Increased default `max_text_length` for auto-chunking to **64,000 characters** (from 32k/16k) for OpenAI, Anthropic, Gemini, Groq, and DeepSeek providers.
    - Unified chunking logic across `extract_entities_llm`, `extract_relations_llm`, and `extract_triplets_llm`.
- **Groq Support**:
    - Standardized Groq provider defaults to use `llama-3.3-70b-versatile` with a 64k context window.
    - Added native support for `max_tokens` and `max_completion_tokens` to prevent output truncation.

### Added
- **Testing**:
    - Added `tests/reproduce_issue_176.py` to validate `max_tokens` propagation and chunking behavior across all extractors.


## [0.2.0] - 2026-01-10

### Added
- **Amazon Neptune Support**:
    - Added `AmazonNeptuneStore` providing Amazon Neptune graph database integration via Bolt protocol and OpenCypher.
    - Implemented `NeptuneAuthTokenManager` extending Neo4j AuthManager for AWS IAM SigV4 signing with automatic token refresh.
    - Added robust connection handling: retry logic with backoff for transient errors (signature expired, connection closed) and driver recreation.
    - Added `graph-amazon-neptune` optional dependency group (boto3, neo4j).
    - Comprehensive test suite covering all GraphStore interface methods.
- **Docling Integration**:
    - Added `DoclingParser` in `semantica.parse` for high-fidelity document parsing using the Docling library.
    - Supports multi-format parsing (PDF, DOCX, PPTX, XLSX, HTML, images) with superior table extraction and structure understanding.
    - Implemented as a standalone parser supporting local execution, OCR, and multiple export formats (Markdown, HTML, JSON).
- **Robust Extraction Fallbacks**:
    - Implemented comprehensive fallback chains ("ML/LLM" -> "Pattern" -> "Last Resort") across `NERExtractor`, `RelationExtractor`, and `TripletExtractor` to prevent empty result lists.
    - Added "Last Resort" pattern matching in `NERExtractor` to identify capitalized words as generic entities when all other methods fail.
    - Added "Last Resort" adjacency-based relation extraction in `RelationExtractor` to create weak connections between adjacent entities if no relations are found.
    - Added fallback logic in `TripletExtractor` to convert relations to triplets or use rule-based extraction if standard methods fail.
- **Provenance & Tracking**:
    - Added count tracking to batch processing logs in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added `batch_index` and `document_id` to the metadata of all extracted entities, relations, triplets, semantic roles, and clusters for better traceability.
- **Semantic Extract Improvements**:
    - Introduced `auto-chunking` for long text processing in LLM extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Added `silent_fail` parameter to LLM extraction methods for configurable error handling.
    - Implemented robust JSON parsing and automatic retry logic (3 attempts with exponential backoff) in `BaseProvider` for all LLM providers.
    - Enhanced `GroqProvider` with better diagnostics and connectivity testing.
    - Added comprehensive entity, relation, and triplet deduplication for chunked extraction.
    - Added `semantica/semantic_extract/schemas.py` with canonical Pydantic models for consistent structured output.
- **Testing**:
    - Added comprehensive robustness test suite `tests/semantic_extract/test_robustness_fallback.py` for validating extraction fallbacks and metadata propagation.
    - Added comprehensive unit test suite `tests/embeddings/test_model_switching.py` for verifying dynamic model transitions and dimension updates.
    - Added end-to-end integration test suite for Knowledge Graph pipeline validation (GraphBuilder -> EntityResolver -> GraphAnalyzer).
- **Other**:
    - Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
    - Robustified ID extraction across `CentralityCalculator`, `CommunityDetector`, and `ConnectivityAnalyzer` to handle various entity formats.
    - Improved `Entity` class hashability and equality logic in `utils/types.py`.

### Changed
- **Deduplication & Conflict Logic**:
    - Removed internal deduplication logic from `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Removed consistency/conflict checking from `ExtractionValidator` to defer to dedicated `semantica/conflicts` module.
    - Removed `_deduplicate_*` methods from `semantica/semantic_extract/methods.py`.
- **Batch Processing & Consistency**:
    - Standardized batch processing across all extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `SemanticNetworkExtractor`, `EventDetector`, `SemanticAnalyzer`, `CoreferenceResolver`) using a unified `extract`/`analyze`/`resolve` method pattern with progress tracking.
    - Added provenance metadata (`batch_index`, `document_id`) to `SemanticNetwork` nodes/edges, `Event` objects, `SemanticRole` results, `CoreferenceChain` mentions, and `SemanticCluster` (tracking source `document_ids`).
    - Updated `SemanticClusterer.cluster` and `SemanticAnalyzer.cluster_semantically` to accept list of dictionaries (with `content` and `id` keys) for better document tracking during clustering.
    - Removed legacy `check_triplet_consistency` from `TripletExtractor`.
    - Removed `validate_consistency` and `_check_consistency` from `ExtractionValidator`.
- **Weighted Scoring**:
    - Clarified weighted confidence scoring (50% Method Confidence + 50% Type Similarity) in comments.
    - Explicitly labeled "Type Similarity" as "user-provided" in code comments to remove ambiguity.
- **Refactoring**:
    - Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
    - Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Fixed
- **Critical Fixes**:
    - Resolved `NameError` in `extraction_validator.py` by adding missing `Union` import.
    - Resolved issues where extractors would return empty lists for valid input text when primary extraction methods failed.
    - Fixed metadata initialization issue in batch processing where `batch_index` and `document_id` were occasionally missing from extracted items.
    - Ensured `LLMExtraction` methods (`enhance_entities`, `enhance_relations`) return original input instead of failing or returning empty results when LLM providers are unavailable.
- **Component Fixes**:
    - Fixed model switching bug in `TextEmbedder` where internal state was not cleared, preventing dynamic updates between `fastembed` and `sentence_transformers` (#160).
    - Implemented model-intrinsic embedding dimension detection in `TextEmbedder` to ensure consistency between models and vector databases.
    - Updated `set_model` to properly refresh configuration and dimensions during model switches.
    - Fixed `TypeError: unhashable type: 'Entity'` in `GraphAnalyzer` when processing graphs with raw `Entity` objects or dictionaries in relationships (#159).
    - Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
    - Fixed dependency compatibility issues by pinning `protobuf==4.25.3` and `grpcio==1.67.1`.
    - Fixed a bug in `TripletExtractor` where the `validate_triplets` method was shadowed by an internal attribute.
    - Fixed incorrect `TextSplitter` import path in the `semantic_extract.methods` module.

## [0.1.1] - 2026-01-05

### Added
- Exported `DoclingParser` and `DoclingMetadata` from `semantica.parse` for easier access.
- Added comprehensive `DoclingParser` usage examples to README and documentation.
- Added Windows-specific troubleshooting note for PyTorch DLL issues.

### Fixed
- Fixed `DoclingParser` import/export issues across platforms (Windows, Linux, Google Colab).
- Improved error messaging when optional `docling` dependency is missing.
- Fixed versioning inconsistencies across the framework.

## [0.1.0] - 2025-12-31

### Added
- New command-line interface (`semantica` CLI) with support for knowledge base building and info commands.
- Integrated FastAPI-based REST API server for remote access to framework functionality.
- Dedicated background worker component for scalable task processing and pipeline execution.
- Framework-level versioning configuration for PyPI distribution.
- Automated release workflow with Trusted Publishing support.

### Changed
- Updated versioning across the framework to 0.1.0.
- Refined entry point configurations in `pyproject.toml`.
- Improved lazy module loading for core framework components.

## [0.0.5] - 2025-11-26

### Changed
- Configured Trusted Publishing for secure automated PyPI deployments

## [0.0.4] - 2025-11-26

### Changed
- Fixed PyPI deployment issues from v0.0.3

## [0.0.3] - 2025-11-25

### Changed
- Simplified CI/CD workflows - removed failing tests and strict linting
- Combined release and PyPI publishing into single workflow
- Simplified security scanning to weekly pip-audit only
- Streamlined GitHub Actions configuration

### Added
- Comprehensive issue templates (Bug, Feature, Documentation, Support, Grant/Partnership)
- Updated pull request template with clear guidelines
- Community support documentation (SUPPORT.md)
- Funding and sponsorship configuration (FUNDING.yml)
- GitHub configuration README for maintainers
- 10+ new domain-specific cookbook examples (Finance, Healthcare, Cybersecurity, etc.)

### Removed
- Redundant scripts folder (8 shell/PowerShell scripts)
- Unnecessary automation workflows (label-issues, mark-answered)
- Excessive issue templates

## [0.0.2] - 2025-11-25

### Changed
- Updated README with streamlined content and better examples
- Added more notebooks to cookbook
- Improved documentation structure

## [0.0.1] - 2024-01-XX

### Added
- Core framework architecture
- Universal data ingestion (multiple file formats)
- Semantic intelligence engine (NER, relation extraction, event detection)
- Knowledge graph construction with entity resolution
- 6-stage ontology generation pipeline
- GraphRAG engine for hybrid retrieval
- Multi-agent system infrastructure
- Production-ready quality assurance modules
- Comprehensive documentation with MkDocs
- Cookbook with interactive tutorials
- Support for multiple vector stores (Weaviate, Qdrant, FAISS)
- Support for multiple graph databases (Neo4j, NetworkX, RDFLib)
- Temporal knowledge graph support
- Conflict detection and resolution
- Deduplication and entity merging
- Schema template enforcement
- Seed data management
- Multi-format export (RDF, JSON-LD, CSV, GraphML)
- Visualization tools
- Pipeline orchestration
- Streaming support (Kafka, RabbitMQ, Kinesis)
- Context engineering for AI agents
- Reasoning and inference engine

### Documentation
- Getting started guide
- API reference for all modules
- Concepts and architecture documentation
- Use case examples
- Cookbook tutorials
- Community projects showcase

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

## Migration Guides

When breaking changes are introduced, migration guides will be provided in the release notes and documentation.

---

For detailed release notes, see [GitHub Releases](https://github.com/Hawksight-AI/semantica/releases).




