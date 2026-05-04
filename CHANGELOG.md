# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

**Ontology Hub** (part of #517)

- **Alignments tab** (PR #524, @KaifAhmad1 @ZohaibHassan16) — cross-ontology alignment authoring UI:
  - Create/edit/delete alignments with source URI, target URI, relation selector (owl:equivalentClass, all five skos:*Match variants), confidence slider, provenance, and reviewer fields.
  - Pairwise alignment matrix: scrollable table for all loaded ontology pairs; clicking a badge pre-fills the form.
  - Alignment suggestions via `POST /api/ontology/suggest-alignments` — blended score (0.4×label + 0.6×TF-IDF char-ngram cosine); one-click accept.
  - Ephemeral-storage banner; all handlers wrapped in `useCallback`.
- **Health Dashboard** (PR #524) — per-ontology quality scoring across 5 dimensions:
  - Completeness, Consistency, SHACL (stub), Alignment, Documentation.
  - Total score computed as mean of scoreable dimensions only (SHACL excluded when unavailable).
  - Issue list with severity badges (error/warning/info), entity URI chip, "Fix in Editor" deep-link.
  - Downloadable JSON health report; `GET /api/ontology/health` with `_MAX_ANALYSIS_NODES = 5 000` OOM cap.
- **SHACL Studio** (PR #524) — interactive SHACL shape authoring:
  - Shape generation via `POST /api/ontology/shacl/generate` (permissive/standard/strict tiers).
  - Shape library panel with per-shape Turtle extraction; "View all" restores full document.
  - Monaco editor with custom Monarch tokenizer for Turtle syntax.
  - Validation stub via `POST /api/ontology/shacl/validate`; rejects empty/invalid Turtle with HTTP 422.
- **Visual Ontology Editor** (PR #519, @KaifAhmad1) — @xyflow/react canvas for authoring classes/properties/individuals without hand-writing OWL/Turtle:
  - Context menus on nodes (rename, add super/subclass, restrictions, SKOS metadata, deprecation, delete with impact count) and edges (toggle functional/symmetric/transitive/inverse-functional, add inverse).
  - All edits debounced and staged as pending diffs via `PATCH /api/ontology/draft`; nothing commits until proposal publish.
- **Versions & Proposals tab** (PR #519) — version timeline, proposal review (approve/reject/publish), SHACL pre-validation, side-by-side diff via `VersionManager.diff_ontologies()`.
- **Ontology Registry** (PR #518, @KaifAhmad1) — full CRUD with status/format badges, per-ontology stats, live search, filter pills (All/OWL/SKOS/Internal/External), action feedback auto-hide.
- **Ontology Loader** (PR #518) — three-mode modal: URL import (fetch preview + load), file upload (.ttl/.rdf/.owl/.nt/.jsonld/.n3), create new (scratch/from-data/from-text).
- **Entity Search panel** (PR #518) — debounced 320 ms search across all loaded ontologies; type filter pills; result detail panel with super/subclasses, domain/range, instance count.
- **SKOS Vocabulary Manager** (PR #518) — hierarchical concept browser with recursive `ConceptTreeNode`, client-side `filterConcepts()`, full SKOS annotation detail (definition, scopeNote, broader/narrower/related/exactMatch).
- **16 backend endpoints** under `/api/ontology` — registry, preview, load, create, search, entity, skos/schemes, skos/concept, draft, proposals CRUD, versions, alignments, health, shacl/generate, shacl/shapes, shacl/validate (PRs #518, #519, #524).
- **Explorer landing page redesign** (PR #516, @ZohaibHassan16) — hero section, animated SVG graph preview, live `/api/graph/stats` metrics, workspace launcher; `Space Grotesk` / `IBM Plex Sans` fonts; `prefers-reduced-motion` support.
- **Distance Intelligence** (PR #502, @KaifAhmad1):
  - `ContextGraph.get_neighbors(include_distance_metadata)` — adds `distance_band`, `confidence_decay`, `path_to_anchor` per result.
  - `AgentContext.retrieve()` / `find_precedents()` blend graph proximity with semantic score (`combined_score = (1−w)×semantic + w×proximity`).
  - 5 new API endpoints: `POST /api/graph/distance-matrix` (N×N, upper-triangle mirrored), `GET /api/graph/node/{id}/semantic-neighborhood`, `GET /api/decisions/causal-distance`, `GET /api/temporal/distance-history`, `POST /api/export/distance-enriched` (CSV/JSONL, capped at 200 nodes).
  - Explorer UI: Ego Mode (BFS depth-of-field fading, depth slider 1–8), Structural overlay, Semantic overlay, Heatmap (green→red by hop); Path inspector with distance band chip, metric cards, bottleneck node highlight.
  - 57 new tests in `tests/context/test_distance_intelligence.py`.
- **Graph Explorer visual refresh** (PR #503, @ZohaibHassan16) — structured `ui.*` design-token namespace; per-shape biomolecule/condition/compound config; decomposed toolbar memos; typed sub-components (`SearchCommandBar`, `ToolbarCluster`, etc.); deterministic LOD edge classification via `GraphFullEdgeClass`.
- **Graph Workspace declutter** (PR #483, @ZohaibHassan16) — calmer default presentation for dense graphs, display-edge aggregation with raw-edge bundle retention, grouped community view, neighborhood collapse/expand.
- **Bidirectional path finding** (closes #469, @KaifAhmad1) — `directed=false` query param on BFS and Dijkstra; undirected view built via `graph.to_undirected()` for traversal only; empty-path 404 guard; `PathResponse.directed` field.
- **Node distance semantics in path responses** (closes #472) — `PathResponse` gains `hop_count` and `distance_band` ("direct"/"near"/"mid-range"/"distant"); `classify_path_distance()` in `semantica/utils/helpers.py`; `KGVisualizer.visualize_network(highlight_path)` with band-scaled edge rendering.
- **Native `KnowledgeGraph` type support in `KGVisualizer`** (closes #471) — formal `KnowledgeGraph` dataclass (`entities`, `relationships`, `metadata`); `_normalize_graph()` routes it through `_convert_knowledge_graph()` as an explicit fast-path in all 5 `visualize_*` methods.
- **Indexed search for large graphs** (PR #481, @ZohaibHassan16) — purpose-built inverted index with exact/token/prefix lookup tiers; LRU cache (128 slots); O(log n) mutation sync via `bisect.insort`; warm-query time 24 ms → 0.004 ms on 118 k-node graph.
- **Provenance traversal multi-hop fix** (PR #480, @Sameer6305) — undirected ego-graph expansion so upstream ancestors at depth ≥ 2 are no longer silently excluded; `ProvenanceEdge.direction` field (upstream/downstream/lateral); grouped markdown report under `## Upstream/Downstream/Lateral` sections.
- **TripletStore ontology namespace** (PR #447, @KaifAhmad1) — `_resolve_iri()` applies `base_uri` before `urn:` fallback; W3C prefix expansion table (owl/xsd/rdf/rdfs/skos) expands to canonical IRIs regardless of `base_uri`.
- **Blazegraph literal serialization** (PR #448, @KaifAhmad1) — `_format_object_for_sparql()` selects IRI/typed-literal/language-tagged-literal/plain-literal token; `_resolve_datatype_iri()` with prefix expansion; RFC 5646 language-tag validation; `_escape_literal()` for string escaping.
- **DeepSeek provider via OpenAI SDK** (PR #482, @liling) — `_init_client` rewritten using `openai.OpenAI(base_url=self.base_url)` instead of defunct `deepseek` package; `verbose_mode` assignment fix; `pyproject.toml` updated to `openai>=1.0.0`.

### Fixed

- **OWLExporter Turtle syntax** (closes #478) — invalid multi-block output fixed via `_ttl_block()`; data properties no longer silently dropped; `_escape_ttl_str()` applied to all label/comment/version sites. 43 tests added.
- **OWLGenerator schema compatibility** (Issue #446) — label-first IRI fallback, list-typed datatype ranges, per-call namespace consistency, `subClassOf`/`subclassOf` parity.
- **TripletStore IRI regressions** (PR #447 follow-up) — non-string IDs coerced to `str()`; W3C prefix expansion now correct regardless of `base_uri`.
- **`KGVisualizer` accepts `KnowledgeGraph` objects** (closes #458) — `_normalize_graph()` duck-types input; raises clear `ProcessingError` on unknown types. 21 tests added.
- **Semantic Distance UI slash-safe routes** (PR #515, @ZohaibHassan16) — query-param routes `/api/graph/semantic-neighborhood?node_id=` and `/api/graph/path?source=&target=` bypass FastAPI's `%2F` pre-decode; legacy path-segment routes kept as deprecated aliases.
- **Explorer Distance Intelligence rendering** (PR #513, @ZohaibHassan16) — distance state flows through Sigma reducer/theme pipeline instead of mutating raw graph attributes; `restoreNodeColors()` race eliminated by merging ego/heatmap `useEffect` hooks.
- **Distance Intelligence code review regressions** (PR #502 follow-up, @KaifAhmad1) — `top_k` param name fix; `include_distance_metadata` gated behind `False` default; `weakest_link` key standardized; temporal sampling uses `timedelta` not `timetuple`; O(E×L) decay replaced with O(E) index; `AgentContext._apply_proximity_metadata` stores `graph_node_id` separately; sweep animation `sweepGeneration` counter fix; HTTP 413 for >200 node subsets; upper-triangle distance matrix.
- **Knowledge Explorer blockers** (PR #420, @ZohaibHassan16):
  - `Dockerfile`: renamed `DockerFile` → `Dockerfile`; fixed `CMD` module path; added `app = create_app()` at module level.
  - CORS: default origins narrowed from `"*"` to `localhost:5173` only.
  - `get_ws_manager()` now raises HTTP 503 instead of unhandled `AttributeError`.
  - SPARQL: read-only enforcement — `INSERT`/`DELETE`/`UPDATE`/`LOAD`/`DROP` rejected.
  - Vocabulary: 10 MB upload cap; JSON-LD format auto-detection for `.jsonld`/`.json-ld`/`.json`.
  - Annotation `O(1)` lookup via `GraphSession.get_annotation(id)`.
  - Self-loop guard in `batchMergeEdges` prevents Graphology crash.
  - Static build artifacts removed from git; `semantica/static/` added to `.gitignore`.
- **Ontology Hub post-review hardening** (PR #518 follow-up, @KaifAhmad1):
  - Registry filter: `status` param removed from `fetchRegistry`; filtering applied client-side.
  - Toggle/refresh URI: removed `.removesuffix()` calls that corrupted URIs ending with those strings.
  - Format detector: `_detect_format()` ReDoS eliminated — `re.match` replaced with two O(1) string ops.
  - Broken `fmtMap` entries: added `xml`/`json` mappings; unknown-extension fallback changed from `|| "turtle"` to `?? ""`.
  - XML hardening: `_parse_rdf_sync()` now routes through `_safe_parse_rdf()` for consistent defusedxml XXE protection.
  - Search: replaced O(999 999) linear scan with `GraphSearchIndex`-backed `session.search()`.

### Security

- **12 vulnerability fixes** (PR security-enhancement, @KaifAhmad1):
  - **[CRITICAL — CWE-95]** Eval injection in `media_parser.py`: replaced `eval(ffprobe_output)` with `fractions.Fraction`.
  - **[CRITICAL — CWE-502]** Pickle deserialization in `agent_memory.py`: replaced with JSON; legacy `.pkl` files detected and refused with migration message.
  - **[HIGH — CWE-89]** SQL injection in `snowflake_ingestor.py`: `LIMIT`/`OFFSET` parameterized; `ORDER BY` regex-validated; `WHERE` clauses containing semicolons rejected.
  - **[HIGH — CWE-611]** XXE in `rdf_parser.py`: `defusedxml.defuse_stdlib()` before all RDF/XML parsing.
  - **[HIGH — CWE-346/200]** Missing security headers in `server.py`: `CORSMiddleware`, `X-Content-Type-Options`, `X-Frame-Options`, HSTS, generic 500 handler.
  - **[HIGH — CWE-346/400]** Overpermissive CORS in `explorer/app.py`: methods/headers narrowed; 64 KB WebSocket frame cap.
  - **[MEDIUM — CWE-20]** Algorithm param unconstrained in `graph.py`: enum-validated `bfs|dijkstra` only.
  - **[MEDIUM — CWE-434]** RDF upload without extension check in `vocabulary.py`: `.ttl/.rdf/.owl/.xml/.jsonld` allowlist enforced.
  - **[MEDIUM — CWE-1336]** Prompt injection in `llm_extraction.py`: user-supplied content wrapped in `json.dumps()`.
  - **[MEDIUM — CWE-95]** Dynamic `__import__()` in `pipeline_validator.py`: replaced with proper module-level import.
  - **[MEDIUM — CWE-1333]** ReDoS in `enrich.py`: whitespace-normalize then split on literal `" AND "`.
  - **[LOW — CWE-22]** Path traversal in `server.py` SPA route: `Path.resolve().relative_to()` guard; 400 on escape.
  - **[LOW — CWE-400]** Unbounded SPARQL in `sparql.py`: 5 000-row cap, 30 s `asyncio.wait_for` timeout, `Semaphore(4)` concurrency cap; `SparqlResponse.truncated` field added.
  - **[LOW — CWE-434]** Import upload in `export_import.py`: 50 MB cap; `{.json,.csv}` allowlist.
  - CodeQL `paths-ignore` for `cookbook/**/*.html` to suppress false-positive JS alerts #15–18.
- **SSRF in Ontology Hub** (PR #518 follow-up): `_validate_fetch_url()` rejects non-http/https schemes and resolves hostname via `socket.getaddrinfo`, blocking loopback/private/link-local/multicast addresses.

---

## [0.4.0] - 2026-04-08

### Added

**Temporal Intelligence** (@KaifAhmad1, PRs #396–#402)

- **Core Temporal Data Model** (PR #396) — `semantica.kg.temporal_model` with shared parsing/normalization/serialization helpers; `TemporalBound` and `BiTemporalFact` exported from `semantica.kg`; valid-time and transaction-time filtering; `TemporalValidationError` on invalid inputs; history-preserving revisions in `TemporalVersionManager.apply_revision()` with supersession semantics.
- **Point-in-Time Query Engine** (PR #397) — `TemporalGraphQuery.reconstruct_at_time(graph, at_time)` builds consistent point-in-time subgraphs without mutating source; `TemporalConsistencyReport` detects inverted intervals, relationships outside entity lifetimes, overlapping same-type relationships, and temporal gaps; sequence/cycle pattern detection; calendar-aligned evolution bucketing via `temporal_granularity`; causal ordering controls on `find_temporal_paths()` (strict/overlap/loose).
- **Deterministic Temporal Reasoning Engine** (PR #398) — `semantica.kg.temporal_reasoning`; full Allen interval algebra via `IntervalRelation` (all 13 relations); `TemporalReasoningEngine` with interval merging, gap analysis, coverage calculation, timelines, retroactive coverage; zero LLM calls; circular import risk between `semantica.reasoning` and `semantica.kg` eliminated.
- **Temporal Awareness in ContextGraph** (PR #399) — `Decision` dataclass gains `valid_from`/`valid_until`; superseded decisions remain in graph (immutable history); `find_precedents_by_scenario(include_superseded, as_of)`; `ContextGraph.state_at(timestamp)` serializable snapshot; `CausalChainAnalyzer.trace_at_time(event_id, at_time)`; `AgentContext.checkpoint(label)`, `diff_checkpoints()`, `flush_checkpoint()`.
- **Temporal Metadata Extraction from Text** (PR #400):
  - `extract_relations_llm(extract_temporal_bounds=True)` — each `Relation` gains `valid_from`, `valid_until`, `temporal_confidence` (0.0–1.0), `temporal_source_text`; default `False` is 100% backward-compatible.
  - Calibrated confidence anchors: 1.00 = full ISO date → 0.00 = no temporal signal.
  - `TemporalNormalizer` (zero LLM calls, pure regex + dateutil): `normalize(value)` → UTC datetime tuple or `None`; `normalize_phrase(phrase)` → metadata dict or `None`; 13-domain default phrase map; `TemporalAmbiguityWarning` for ambiguous DD/MM/YYYY inputs (never silently guesses locale).
- **Temporal Provenance & OWL-Time Export** (PR #401):
  - `ProvenanceTracker.track_entity()` auto-stamps `recorded_at` on every new record.
  - `query_recorded_between(start, end)`, `revision_history(fact_id)`, `export_audit_log(fact_ids, format)` (JSON/CSV).
  - `RDFExporter.export_to_rdf(include_temporal=True, time_axis="valid|transaction|both")` — emits OWL-Time triples for all temporally-annotated relationships.
  - `create_snapshot()` stamps `"format_version": "1.0"`; `validate_snapshot()` and `migrate_snapshot()` for stable snapshot lifecycle.
- **Temporal GraphRAG Integration** (PR #402) — `TemporalGraphRetriever` filters retrieved context to a point in time; `ContextRetriever.query_with_reasoning(at_time, header_template)` prepends structured temporal header; `TemporalQueryRewriter` extracts temporal intent (before/after/at/during/between) from natural language; regex-only by default, optional LLM-assisted mode.

**Ontology** (@KaifAhmad1 @ZohaibHassan16)

- **SHACL Shape Generation & Validation** (PR #318) — `SHACLGenerator` derives SHACL node/property shapes from any ontology dict; three quality tiers (basic/standard/strict); Turtle/JSON-LD/N-Triples output; iterative multi-level inheritance propagation, cycle-safe; `OntologyEngine.to_shacl()`, `export_shacl()`, `validate_graph(explain=True)`; `SHACLValidationReport` with plain-English explanations for all 7 constraint types. `pip install semantica[shacl]`.
- **SKOS Vocabulary Module** (PR #319) — `TripletStore.add_skos_concept()` / `get_skos_concepts(scheme_uri)`; `OntologyEngine.list_vocabularies()`, `list_concepts()`, `search_concepts()`; `NamespaceManager.get_skos_uri()` / `build_concept_scheme_uri()`; SPARQL injection hardened.
- **Ontology Alignment API** (PR #361) — `OntologyEngine.create_alignment()`, `get_alignments()`, `list_alignments()`; OWL/SKOS standard predicates (`owl:equivalentClass`, all five `skos:*Match`); `ReuseManager.suggest_alignments()`; `QueryEngine.expand_entity_uri(use_alignments=True)` with SPARQL `VALUES` clause injection; SPARQL injection hardened.
- **Ontology Diff & Migration** (PR #367) — `VersionManager.diff_ontologies()` covering classes/properties/individuals/axioms; `ChangeLogAnalyzer.analyze()` classifying CRITICAL/HIGH/MEDIUM/INFO impact; `ImpactReport`, `generate_change_report()`; `OntologyEngine.compare_versions()` end-to-end orchestrator with optional validation and graph-instance checks.

**Knowledge Explorer API** (@ZohaibHassan16 @KaifAhmad1)

- **Full FastAPI backend** (PR #384) — `semantica.explorer` package with graph, analytics, decisions, temporal, enrichment, export/import, annotations routes; 12 export formats; WebSocket progress for import; 99 integration tests. `pip install semantica[explorer]`; CLI: `semantica-explorer --graph my_graph.json`.
- **Thread safety** (PR #385) — `ContextGraph` and `GraphSession` protected with `threading.RLock`; 8 analytics components lazily initialized under lock.
- **In-memory fallbacks** (PR #386) — All 7 `DecisionQuery` and 4 `DecisionRecorder` methods have `ContextGraph` fallback paths for in-memory usage without a graph DB.
- **Snapshot schema compatibility** (PR #393) — accepts both `nodes`/`edges` and `entities`/`relationships` snapshot schemas transparently; metadata counts always accurate.
- **Audit trail & rollback protection** (PR #394) — mutation-level audit tracking, named version tags, `restore_snapshot()` requires explicit confirmation, `get_node_history()`, `diff()` Git-like alias.
- **SKOS Vocabulary REST API** (PR #426) — `GET /api/vocabulary/schemes`, `GET /api/vocabulary/hierarchy?scheme=<uri>` with cycle detection, `POST /api/vocabulary/import` (.ttl/.rdf/.owl; HTTP 422 on invalid).
- **O(N) → O(limit) Pagination** (PR #431) — `find_nodes`/`find_edges` use `itertools.islice` on generators; ghost-node fix (accepts `source_id`/`target_id` and `source`/`target` key names); deterministic page boundaries via `sorted()`; `stats()` applies same validity filters as pagination.
- **Named graph support** (PR #432, @Sameer6305) — `enable_named_graphs` flag forwarded correctly through `TripletStore.execute_query()`; duplicate `FROM`/`FROM NAMED` clauses prevented; graph URIs percent-encoded in DROP statements.

**Integrations**

- **Agno Agentic Framework** (Issue #249, @KaifAhmad1) — 5 components, all degrading gracefully when `agno` is not installed:
  - `AgnoContextStore` — graph-backed agent memory implementing `agno.memory.db.base.MemoryDb`.
  - `AgnoKnowledgeGraph` — multi-hop GraphRAG knowledge base implementing `agno.knowledge.base.AgentKnowledge`.
  - `AgnoDecisionKit` — 6 decision-intelligence tools (record_decision, find_precedents, trace_causal_chain, analyze_impact, check_policy, get_decision_summary).
  - `AgnoKGToolkit` — 7 KG pipeline tools (extract_entities, extract_relations, add_to_graph, query_graph, find_related, infer_facts, export_subgraph).
  - `AgnoSharedContext` — team coordinator with single shared `ContextGraph`; `bind_agent(role)` returns role-scoped view; thread-safe via `RLock`.
  - 110 integration tests; 3 cookbook notebooks. `pip install semantica[agno]`.
- **Novita AI Provider** (PR #374, @Alex-wuhu) — OpenAI-compatible; default model `deepseek/deepseek-v3.2`; `NOVITA_API_KEY`; `create_provider("novita")`.

**Reasoning**

- **Native Datalog Reasoning Engine** (PR #371, @ZohaibHassan16) — pure-Python bottom-up semi-naive fixpoint with guaranteed termination; recursive Horn clause rules (e.g. `ancestor(X,Y) :- parent(X,Z), ancestor(Z,Y).`); O(1) delta-index lookup; `load_from_graph(ContextGraph)`; `query("pred(?X, ?Y)")` with optional `bindings=`; `DatalogReasoner`, `DatalogFact`, `DatalogRule` exported from `semantica.reasoning`.

### Fixed

- **Pattern Matcher restored** (PR #387, @ZohaibHassan16) — dead code silently overwrote `_match_pattern` regex (pre-bound variable embedding, repeated-variable backreferences) with `re.escape`, breaking transitivity/symmetry/self-join rules; removed. `re.error` now surfaced instead of swallowed.
- **OllamaProvider base_url ignored** (PR #408, @AlexeyMyslin) — `ollama.Client(host=self.base_url)` instead of raw module assignment; remote Ollama servers now reachable.
- **spaCy runtime fallback** — `NERExtractor` now catches runtime initialization failures, not just missing-model errors.
- **CentralityCalculator crash** — `_build_adjacency()` handles both ContextGraph dataclass edges (`source_id`/`target_id`) and plain dicts.
- **`find_path` always used BFS** (PR #384) — algorithm query param now correctly dispatched to `dijkstra_shortest_path` or `bfs_shortest_path`.
- **Event loop blocked in `/api/enrich/links`** (PR #385) — `score_link` scoring loop wrapped in `asyncio.to_thread`.
- **Temp file leak in `export_graph`** (PR #384) — `try/finally` cleanup for all error paths.
- **`ChangeCategory` enum typo** (PR #367) — `"potenitally_breaking"` → `"potentially_breaking"`.
- **DecisionQuery/DecisionRecorder fallbacks** (PR #386) — `type()` guard instead of `isinstance()` for Mock safety; flat property storage in `_store_decision_node`; spurious `properties={}` kwarg removed; tz-aware/naive datetime mismatch resolved; `find_edges()` hoisted out of BFS loop (O(nodes×edges) → O(1) per call).
- **Snapshot schema** (PR #393) — silent restore failures when `nodes`/`edges` schema didn't match legacy `entities`/`relationships` expectations.
- **Context explainability** (@KaifAhmad1) — decision nodes now store full `scenario`/`reasoning` text; causal/precedent reconstruction returns enriched `Decision` objects; `PolicyEngine.get_affected_decisions()` consistent across Cypher and fallback branches.

### Security

- **CWE-312/359/532** — Removed `api_key` debug `print` blocks from `relation_extractor.py` and `triplet_extractor.py`.
- **CWE-20** — URL sanitization: `"url" in urls` replaced with `any(url == "url" for url in urls)`, eliminating substring match.
- **CI overpermissions** — `permissions: contents: read` added to `benchmark.yml` and `security.yml`.
- **SHACL path traversal** (PR #318) — replaced `len < 500 and "\n" not in s` heuristic with `os.path.exists()`.
- **SHACL inheritance mutation** (PR #318) — `_propagate_inheritance` uses `dataclasses.replace()` instead of appending parent `PropertyShape` objects by reference.
- **SPARQL injection** (PR #361) — `search_concepts`, `list_alignments`, `build_values_clause` fully hardened.

---

## [0.3.0] - 2026-03-10

### Added

- **Context Graph Feature Completeness** (@KaifAhmad1):
  - `ContextNode` / `ContextEdge` gain `valid_from` / `valid_until` with `is_active(at_time) -> bool`.
  - `ContextGraph.find_active_nodes(node_type, at_time)` — temporal node filtering.
  - `get_neighbors(min_weight)` — confidence-filtered BFS (default 0.0 passes all edges).
  - `link_graph()` / `navigate_to()` / `resolve_links(registry)` — cross-graph navigation with full save/load round-trip.
  - `graph_id` UUID field persisted to JSON.

### Fixed

- `is_active()` tz-aware/naive datetime normalization.
- `valid_from`/`valid_until` serialization in `add_nodes()`, `add_edges()`, `to_dict()`, `from_dict()`.
- Cross-graph link phantom-node prevention in `link_graph()`.
- `pipeline_builder.add_step()` return type annotation.
- `test_hybrid_search_performance` timing computation; threshold raised to < 5.0 s.
- **ProvenanceTracker** added to `semantica/kg/__init__.py` exports.
- Duplicate relation creation in `_parse_relation_result` — orphaned legacy block removed.
- `extraction_method` parameter added; typed path now correctly sets `"llm_typed"`.
- Cross-test cache pollution in `test_retry_logic.py` — `_result_cache.clear()` added to `setUp()`.
- 14 tests in `tests/context/test_cross_graph_navigation.py`; 85 real-world tests in `tests/test_030_realworld_comprehensive.py`.

---

## [0.3.0-beta] - 2026-03-07

### Added

- **Multi-Founder LLM Extraction** (PR #354, @KaifAhmad1):
  - `_parse_relation_result`: unmatched subjects/objects produce a synthetic `UNKNOWN` entity instead of being silently dropped.
  - `_match_pattern` rewritten: splits on `?var` placeholders, pre-bound variable resolution, repeated-variable backreferences.
- **TTL Export Aliases** (PR #355, @KaifAhmad1) — `format="ttl"/"nt"/"xml"/"rdf"/"json-ld"` resolve correctly before format validation; 8 tests in `tests/export/test_rdf_exporter.py`.
- **Incremental/Delta Processing** (PR #349, @ZohaibHassan16) — native delta computation between graph snapshots via SPARQL, delta-aware pipeline execution (`delta_mode`), snapshot retention with `prune_versions()`, significant performance improvements for near real-time pipelines.
- **Deduplication v2**:
  - **Candidate Generation v2** (PR #338, @ZohaibHassan16) — multi-key blocking, phonetic (Soundex) blocking, deterministic candidate budgeting; 63.6% faster (0.259 s → 0.094 s for 100 entities).
  - **Two-Stage Scoring Prefilter** (PR #339, @ZohaibHassan16) — type mismatch, length ratio, token overlap gates; 18–25% faster batch processing.
  - **Semantic Relationship Deduplication v2** (PR #340, @ZohaibHassan16) — predicate synonym mapping (`works_for` → `employed_by`), O(1) hash matching, weighted scoring (60% predicate + 40% object); 6.98x speedup (~83 ms vs ~579 ms).
  - **Migration Guide** (PR #344, @ZohaibHassan16) — comprehensive MIGRATION_V2.md; critical infinite recursion bug in `dedup_triplets()` fixed.
- **ArangoDB AQL Export** (PR #342, @tibisabau) — AQL INSERT generation, configurable collections, batch processing (default 1 000), `.aql` auto-detection, 17 tests.
- **Apache Parquet Export** (PR #343, @tibisabau) — columnar storage, configurable compression (snappy/gzip/brotli/zstd/lz4/none), explicit Arrow schemas, `.parquet` auto-detection, 25 tests.

### Fixed

- **Test Suite Fixes** (@KaifAhmad1):
  - Context: entity extraction gated on `use_hybrid_search=True`; `_extract_entities_from_query` uses `word[0].isupper()`; added `expand_context` BFS method; `hybrid_retrieval` and `multi_hop_context_assembly` corrected; vector result fallback to `metadata["content"]`.
  - KG: `calculate_pagerank` aliases; `community_detector._to_networkx` no longer silently loses edges; `_build_adjacency` handles both `"edges"` and `"relationships"` keys; 9 tracking methods added to `AlgorithmTrackerWithProvenance`.
  - Pipeline: retry loop honours `max_retries`; `FailureHandler.handle_failure()` added; `add_step` return type fixed; `validate` alias added; error message standardized.
  - Tests: emoji replaced with ASCII for Windows cp1252 compatibility.
- `NameError`: missing `Type` import in `utils/helpers.py`.

---

## [0.3.0-alpha] - 2026-02-19

### Added

- **Decision Tracking System** — complete lifecycle management (record → analyze → query → precedent → influence) with audit trails and provenance tracking.
- **Advanced KG Algorithms** — Node2Vec embeddings, centrality analysis, community detection for decision insights.
- **Enhanced Context Module** — unified `AgentContext` with granular feature flags for decision tracking, KG algorithms, and vector store features.
- **Vector Store Features** — hybrid search combining semantic, structural, and category similarity.
- **Policy Management** — versioning, compliance checking, and exception handling.
- **Context Engineering Enhancement** (PR #307, @KaifAhmad1) — full decision tracking, hybrid search, `PolicyException` model, `GraphStore` validation, explainable AI features, 9 critical bug fixes, 100% test coverage (9/9).
- **PgVector Store Support** (PR #303, @Sameer6305 @KaifAhmad1) — HNSW/IVFFlat indexing, JSONB metadata filtering, psycopg3/psycopg2 fallback, SQL injection protection via `psycopg_sql.SQL()`, 36+ tests.
- **Apache AGE Backend** (PR #311, @Sameer6305) — `AgeStore` with `GraphStore` API compatibility, SQL injection protection.
- **Improved Vector Store for Decision Tracking** (PR #293, @KaifAhmad1) — `DecisionEmbeddingPipeline`, `HybridSimilarityCalculator` (0.7 semantic + 0.3 structural), `DecisionContext`, `ContextRetriever` with multi-hop reasoning; 34+ tests.
- **Improved Graph Algorithms** (PR #292, @KaifAhmad1) — 30+ algorithms across 7 categories (Node2Vec, Dijkstra, A*, PageRank, Louvain, Leiden, etc.), unified provenance tracking with `GraphBuilderWithProvenance` / `AlgorithmTrackerWithProvenance`.
- **ResourceScheduler Deadlock Fix** (PRs #299 #301, @d4ndr4d3 @KaifAhmad1) — `threading.Lock` → `threading.RLock`; allocation validation; leak prevention on failure; 6 regression tests.
- **Dependabot & Security Automation** — bi-weekly security updates, automated Bandit/Safety/Semgrep scans, security-critical package grouping.

### Fixed

- Context Graphs decision tracking bugs (PR #315, @KaifAhmad1): empty/`None` decision ID, `None` metadata, causal chain depth logic, nonexistent node handling, `to_dict`/`from_dict` round-trip.
- `PolicyEngine` latest version selection; `AgentContext` fallback robustness and secure logging.
- Import issues in test suite (ProvenanceTracker location); causal analyzer `max_depth` bounds.

---

## [0.2.7] - 2026-02-09

### Added

- **Snowflake Connector** (PR #276, @Sameer6305) — multi-auth (password/OAuth/key-pair/SSO), table and query ingestion, SQL injection prevention, progress tracking, 24 tests. `pip install semantica[db-snowflake]`.
- **Apache Arrow Export** (PR #273, @Sameer6305) — explicit Arrow schemas, entity/relationship export, Pandas/DuckDB compatible, 20 tests.
- **Benchmark Suite** (PR #289, @ZohaibHassan16 @KaifAhmad1) — 137+ benchmarks across all 10 modules, Z-score statistical regression detection, GitHub Actions workflow. CLI: `python benchmarks/benchmark_runner.py`.

---

## [0.2.6] - 2026-02-03

### Added

- **W3C PROV-O Provenance Tracking** (Issues #254 #246, @KaifAhmad1):
  - Comprehensive provenance across all 17 Semantica modules; InMemory/SQLite backends; SHA-256 integrity.
  - FDA 21 CFR Part 11, SOX, HIPAA, TNFD compliance infrastructure.
  - 237 tests; opt-in (`provenance=False` by default).
- **Enhanced Change Management** (Issues #248 #243, @KaifAhmad1):
  - `TemporalVersionManager` and `OntologyVersionManager` with SQLite/in-memory backends; SHA-256 checksums; detailed diffs.
  - 104 tests; 17.6 ms for 10 k entities; 510+ ops/sec concurrent.
- **CSV Ingestion Enhancements** (PR #244, @saloni0318) — auto-detect encoding (chardet) and delimiter (csv.Sniffer); tolerant decoding; optional chunked reading.
- **Ingest Unit Tests** (Issues #239 #232, @Mohammed2372) — file, web, and feed ingestors; 998 lines of tests; 80–86% coverage.
- TextNormalizer comprehensive unit tests (PR #242, @ZohaibHassan16).

### Fixed

- **Temperature Compatibility** (Issues #256 #252, @F0rt1s @IGES-Institut) — `temperature=None` now omits parameter so APIs use model defaults; `_add_if_set` helper applied to all 5 providers; 10 tests.
- **JenaStore Empty Graph** (Issues #257 #258, @ZohaibHassan16) — `if self.graph is None:` replaces implicit falsy check in 5 methods.

---

## [0.2.5] - 2026-01-27

### Added

- **Pinecone Vector Store** (closes #219 #220) — serverless and pod-based indexes, namespace support, metadata filtering, unified `VectorStore` integration.
- **Configurable LLM Retry Logic** — `max_retries` parameter (default 3) in `NERExtractor`, `RelationExtractor`, `TripletExtractor`, and all `extract_*_llm` methods.
- **Bring Your Own Model (BYOM)** — custom HuggingFace models in all extractors; custom tokenizer support; runtime `model=` overrides config defaults.
- **Enhanced NER** — configurable aggregation strategies (simple/first/average/max); IOB/BILOU parsing for raw model outputs; confidence scoring.
- **Relation Extraction** — entity marker technique (`<subj>`/`<obj>` tags) for sequence classification models; structured output parsing.
- **Triplet Extraction** — Seq2Seq model support (REBEL) for direct structured triplet generation from text.

### Fixed

- LLM extraction: strict `max_retries` enforcement prevents infinite retry loops.
- Model parameter precedence: runtime arguments now correctly override config defaults in HuggingFace extractors.
- Circular imports in test suites.

---

## [0.2.4] - 2026-01-22

### Added

- **Ontology Ingestion Module** — `OntologyIngestor` for Turtle/RDF-XML/JSON-LD/N3 files; `ingest_ontology()` convenience function; recursive directory scanning; `OntologyData` dataclass; integrated into `ingest(source_type="ontology")`.

---

## [0.2.3] - 2026-01-20

### Added

- Amazon Neptune dev environment — CloudFormation template; `cfn-lint` in pre-commit.
- Vector Store high-performance ingestion — `VectorStore.add_documents()` with batching and parallel processing (`max_workers=6`); `VectorStore.embed_batch()` helper.
- LLM relation extraction tests (mocked and Groq integration).

### Changed

- Simplified relation extraction parameter interface; improved error handling and verbose logging.
- Standardized `VectorStore` concurrency defaults; implicit `max_workers=6` in examples.

### Fixed

- **LLM Relation Extraction Parsing** — normalized typed responses to consistent dict format before parsing; structured JSON fallback; extra kwargs removed from internals.
- **Pipeline Circular Import** (Issues #192 #193) — lazy-loaded `PipelineValidator` inside `PipelineBuilder.__init__`; `TYPE_CHECKING` guard.
- **JupyterLab Progress** (Issue #181) — `SEMANTICA_DISABLE_JUPYTER_PROGRESS` env var suppresses rich progress tables.

---

## [0.2.2] - 2026-01-15

### Added

- **Parallel Extraction Engine** — `concurrent.futures.ThreadPoolExecutor` across all extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticNetworkExtractor`); `max_workers` parameter; thread-safe `ProgressTracker`.
- Semantic extract regression suite; real-use-case benchmark script.

### Changed

- **Gemini SDK Migration** — `google-genai` SDK with `google.generativeai` fallback.
- Pinned `opentelemetry-api`/`-sdk` to 1.37.0; updated `protobuf`/`grpcio` constraints.
- Entity filtering applied only to LLM prompt construction, not non-LLM flows.
- Raised global `optimization.max_workers` default to 8.

### Security

- **Credential sanitization** — hardcoded API keys removed from 8 notebooks; `ExtractionCache` excludes `api_key`/`token`/`password` from cache keys; cache key hashing upgraded MD5 → SHA-256.

### Performance

- ~1.89× speedup via parallel extraction (Groq `llama-3.3-70b-versatile`, standard datasets).
- Optimized entity matching: exact/substring/word-boundary fast paths before embedding similarity.

---

## [0.2.1] - 2026-01-12

### Fixed

- **LLM Output Stability** (Bug #176) — correct `max_tokens` propagation; automatic chunk-halving and retry on context/output limit errors.
- Removed hardcoded `max_length` constraints from `Entity`, `Relation`, `Triplet`.
- Orchestrator lazy property initialization and configuration normalization.
- `AssertionError` in orchestrator tests (mock alignment).
- Pinned `protobuf>=5.29.1,<7.0`, `grpcio>=1.71.2`; added `GitPython` and `chardet` to `pyproject.toml`.

### Changed

- Increased default `max_text_length` to 64 000 characters for all major providers.
- Standardized Groq defaults: `llama-3.3-70b-versatile`, 64 k context, native `max_tokens`/`max_completion_tokens`.

---

## [0.2.0] - 2026-01-10

### Added

- **Amazon Neptune Support** — `AmazonNeptuneStore` via Bolt/OpenCypher; `NeptuneAuthTokenManager` with AWS IAM SigV4 signing; retry/backoff. `pip install semantica[graph-amazon-neptune]`.
- **Docling Integration** — `DoclingParser` for PDF/DOCX/PPTX/XLSX/HTML/image parsing; OCR support; Markdown/HTML/JSON export.
- **Robust Extraction Fallbacks** — ML/LLM → Pattern → Last Resort chains across all extractors.
- **Provenance & Tracking** — `batch_index` and `document_id` metadata on all extracted items.
- **Semantic Extract** — auto-chunking for long text; `silent_fail` parameter; JSON parsing with 3-attempt exponential backoff.
- End-to-end KG pipeline integration tests; `TextEmbedder` model switching tests.

### Changed

- Removed internal dedup logic from extractors (deferred to `semantica/conflicts`).
- Standardized batch processing across all extractors using unified `extract`/`analyze`/`resolve` pattern.
- Clarified weighted confidence scoring (50% Method Confidence + 50% Type Similarity).

### Fixed

- `NameError` in `extraction_validator.py` (missing `Union` import).
- Extractors returning empty lists for valid input when primary methods fail.
- Model switching bug in `TextEmbedder` (state not cleared on model switch). (Issue #160)
- `TypeError: unhashable type: 'Entity'` in `GraphAnalyzer`. (Issue #159)
- Pinned `protobuf==4.25.3`, `grpcio==1.67.1`.
- `TripletExtractor.validate_triplets` shadowed by internal attribute.
- Incorrect `TextSplitter` import path.

---

## [0.1.1] - 2026-01-05

### Added

- Exported `DoclingParser` and `DoclingMetadata` from `semantica.parse`.
- Windows-specific troubleshooting note for PyTorch DLL issues.

### Fixed

- `DoclingParser` import/export across platforms (Windows, Linux, Google Colab).
- Error messaging when optional `docling` dependency is missing.
- Versioning inconsistencies across the framework.

---

## [0.1.0] - 2025-12-31

### Added

- Command-line interface (`semantica` CLI) with knowledge base building and info commands.
- FastAPI-based REST API server for remote access.
- Background worker component for scalable task processing.
- Framework-level versioning configuration for PyPI distribution.
- Automated release workflow with Trusted Publishing support.

### Changed

- Updated versioning across the framework to 0.1.0.
- Refined entry point configurations in `pyproject.toml`.
- Improved lazy module loading for core components.

---

## [0.0.5] - 2025-11-26

### Changed

- Configured Trusted Publishing for secure automated PyPI deployments.

---

## [0.0.4] - 2025-11-26

### Changed

- Fixed PyPI deployment issues from v0.0.3.

---

## [0.0.3] - 2025-11-25

### Added

- Comprehensive issue templates (Bug, Feature, Documentation, Support, Grant/Partnership).
- Updated pull request template with clear guidelines.
- Community support documentation (`SUPPORT.md`).
- Funding and sponsorship configuration (`FUNDING.yml`).
- 10+ domain-specific cookbook examples (Finance, Healthcare, Cybersecurity, etc.).

### Changed

- Simplified CI/CD workflows — removed failing tests and strict linting.
- Combined release and PyPI publishing into single workflow.
- Simplified security scanning to weekly pip-audit only.

### Removed

- Redundant scripts folder (8 shell/PowerShell scripts).
- Unnecessary automation workflows (label-issues, mark-answered).
- Excessive issue templates.

---

## [0.0.2] - 2025-11-25

### Changed

- Updated README with streamlined content and better examples.
- Added more notebooks to cookbook.
- Improved documentation structure.

---

## [0.0.1] - 2024-01-XX

### Added

- Core framework architecture.
- Universal data ingestion (multiple file formats).
- Semantic intelligence engine (NER, relation extraction, event detection).
- Knowledge graph construction with entity resolution.
- 6-stage ontology generation pipeline.
- GraphRAG engine for hybrid retrieval.
- Multi-agent system infrastructure.
- Production-ready quality assurance modules.
- Comprehensive documentation with MkDocs.
- Cookbook with interactive tutorials.
- Multiple vector store backends (Weaviate, Qdrant, FAISS).
- Multiple graph database backends (Neo4j, NetworkX, RDFLib).
- Temporal knowledge graph support.
- Conflict detection and resolution; deduplication and entity merging.
- Schema template enforcement; seed data management.
- Multi-format export (RDF, JSON-LD, CSV, GraphML).
- Visualization tools; pipeline orchestration.
- Streaming support (Kafka, RabbitMQ, Kinesis).
- Context engineering for AI agents; reasoning and inference engine.

---

## Types of Changes

| Label | Meaning |
|-------|---------|
| **Added** | New features |
| **Changed** | Changes in existing functionality |
| **Deprecated** | Soon-to-be removed features |
| **Removed** | Removed features |
| **Fixed** | Bug fixes |
| **Security** | Vulnerability fixes |
| **Performance** | Performance improvements |

---

For detailed release notes, see [GitHub Releases](https://github.com/Hawksight-AI/semantica/releases).
